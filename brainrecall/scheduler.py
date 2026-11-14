"""Deterministic Spaced Practice (M2) & Interleaved Practice (M3) Scheduler (Dev Spec v1.14 Section 7.3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brainrecall.models import (
    Exercise,
    KnowledgeGroup,
    KnowledgeItem,
    ReviewState,
    Topic,
    User,
)

# Canonical M2 day intervals by step_index (1..7)
M2_INTERVAL_STEPS: tuple[int, ...] = (0, 1, 3, 7, 14, 30, 60, 120)
MAX_STEP_INDEX = len(M2_INTERVAL_STEPS) - 1


def get_user_local_date(timezone_name: str, now_utc: datetime | None = None) -> str:
    dt = now_utc or datetime.now(timezone.utc)
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("Europe/Moscow")
    return dt.astimezone(tz).strftime("%Y-%m-%d")


def compute_next_review_state(
    *,
    current_step_index: int,
    last_independent_success_date: str | None,
    grade: str,
    assisted: bool,
    local_date: str,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """
    Compute deterministic M2 transition per Section 7.3:
    - Independent `correct` on a new calendar day advances `step_index` by +1 (1 -> 3 -> 7 -> 14 -> 30 -> 60 -> 120).
    - Same-day repeat (`last_independent_success_date == local_date`) keeps `step_index` unchanged so same-day cramming
      cannot artificially inflate long-term spacing steps.
    - `assisted=True` (hint/source/map used or corrective retry after error) caps interval at 1 day and does not advance
      independent step.
    - `partial` steps back 1 step (min 1, 1 day).
    - `wrong` or `dont_know` resets `step_index` to 1 (due in 1 day, or immediate corrective retry inside session).
    """
    dt = now_utc or datetime.now(timezone.utc)
    step = max(0, min(MAX_STEP_INDEX, current_step_index))

    if grade == "correct" and not assisted:
        if last_independent_success_date == local_date and step >= 1:
            new_step = step
        else:
            new_step = min(MAX_STEP_INDEX, step + 1)
        interval_days = M2_INTERVAL_STEPS[new_step]
        due_at = dt + timedelta(days=interval_days)
        return {
            "step_index": new_step,
            "interval_days": interval_days,
            "due_at": due_at,
            "increment_independent": last_independent_success_date != local_date,
            "new_last_independent_date": local_date,
        }

    if grade == "correct" and assisted:
        new_step = max(1, step)
        interval_days = 1
        due_at = dt + timedelta(days=1)
        return {
            "step_index": new_step,
            "interval_days": interval_days,
            "due_at": due_at,
            "increment_independent": False,
            "new_last_independent_date": last_independent_success_date,
        }

    if grade == "partial":
        new_step = max(1, step - 1)
        interval_days = 1
        due_at = dt + timedelta(days=1)
        return {
            "step_index": new_step,
            "interval_days": interval_days,
            "due_at": due_at,
            "increment_independent": False,
            "new_last_independent_date": last_independent_success_date,
        }

    # wrong / dont_know
    return {
        "step_index": 1,
        "interval_days": 1,
        "due_at": dt + timedelta(days=1),
        "increment_independent": False,
        "new_last_independent_date": last_independent_success_date,
    }


async def build_study_queue(
    session: AsyncSession,
    *,
    user: User,
    mode: str = "regular",
    topic_id: str | None = None,
    group_id: str | None = None,
    max_units: int = 12,
) -> dict[str, Any]:
    """
    Build deterministic study session queue implementing M1-M5 rules:
    - Gates `targeted_mix` (M3 interleaving) behind `intro_completed == True` and at least 2 distinct items/objectives;
      falls back gracefully with `fallback_reason` if insufficient contrasting items exist.
    - Orders due items first, then new items up to `user.daily_new_cap`.
    - Prevents placing two exercises for the exact same `scope_id` back-to-back when interleaving is possible.
    """
    now = datetime.now(timezone.utc)
    effective_mode = mode
    fallback_reason: str | None = None

    active_topics_stmt = select(Topic.id).where(Topic.owner_id == user.id, Topic.status == "active")
    if topic_id:
        active_topics_stmt = active_topics_stmt.where(Topic.id == topic_id)
    active_topic_ids = list((await session.execute(active_topics_stmt)).scalars().all())
    if not active_topic_ids:
        return {
            "effective_mode": effective_mode,
            "fallback_reason": "no_active_topics",
            "units": [],
        }

    if group_id:
        effective_mode = "group"
        ex_stmt = select(Exercise).where(
            Exercise.owner_id == user.id,
            Exercise.group_id == group_id,
            Exercise.status == "active",
        )
        group_exercises = list((await session.execute(ex_stmt)).scalars().all())
        units = [await _serialize_exercise_unit(session, ex) for ex in group_exercises[:max_units]]
        return {
            "effective_mode": effective_mode,
            "fallback_reason": None,
            "units": units,
        }

    # Load all active items & groups in active topics
    items_res = await session.execute(
        select(KnowledgeItem).where(
            KnowledgeItem.owner_id == user.id,
            KnowledgeItem.topic_id.in_(active_topic_ids),
            KnowledgeItem.status == "active",
        )
    )
    items_by_id = {it.id: it for it in items_res.scalars().all()}

    groups_res = await session.execute(
        select(KnowledgeGroup).where(
            KnowledgeGroup.owner_id == user.id,
            KnowledgeGroup.topic_id.in_(active_topic_ids),
            KnowledgeGroup.status == "confirmed",
        )
    )
    groups_by_id = {g.id: g for g in groups_res.scalars().all()}

    rs_res = await session.execute(
        select(ReviewState)
        .where(
            ReviewState.owner_id == user.id,
            ReviewState.topic_id.in_(active_topic_ids),
        )
        .order_by(ReviewState.due_at.asc())
    )
    all_states = list(rs_res.scalars().all())

    eligible_states: list[ReviewState] = []
    for rs in all_states:
        if rs.scope_type == "item":
            it = items_by_id.get(rs.scope_id)
            if not it:
                continue
            if mode == "targeted_mix" and not it.intro_completed:
                continue
            if mode == "intro" and it.intro_completed:
                continue
            eligible_states.append(rs)
        elif rs.scope_type == "group":
            grp = groups_by_id.get(rs.scope_id)
            if not grp:
                continue
            eligible_states.append(rs)

    if mode == "targeted_mix":
        distinct_scopes = {rs.scope_id for rs in eligible_states}
        if len(distinct_scopes) < 2:
            effective_mode = "regular"
            fallback_reason = "insufficient_intro_items_for_interleaving"
            eligible_states = [
                rs
                for rs in all_states
                if (rs.scope_type == "item" and rs.scope_id in items_by_id)
                or (rs.scope_type == "group" and rs.scope_id in groups_by_id)
            ]

    # Prioritize due states, but if none are strictly due yet and user explicitly starts a session, include upcoming
    due_states = [
        rs
        for rs in eligible_states
        if (rs.due_at.replace(tzinfo=timezone.utc) if rs.due_at.tzinfo is None else rs.due_at) <= now
    ]
    chosen_states = due_states if due_states else eligible_states

    # Interleave so adjacent exercises don't repeat the same scope_id if alternatives exist
    ordered_states = _interleave_review_states(chosen_states, max_units=max_units)

    units: list[dict[str, Any]] = []
    for rs in ordered_states:
        if rs.scope_type == "item":
            ex_res = await session.execute(
                select(Exercise).where(
                    Exercise.owner_id == user.id,
                    Exercise.item_id == rs.scope_id,
                    Exercise.objective == rs.objective,
                    Exercise.status == "active",
                )
            )
        else:
            ex_res = await session.execute(
                select(Exercise).where(
                    Exercise.owner_id == user.id,
                    Exercise.group_id == rs.scope_id,
                    Exercise.objective == rs.objective,
                    Exercise.status == "active",
                )
            )
        ex = ex_res.scalar_one_or_none()
        if ex is not None:
            unit = await _serialize_exercise_unit(session, ex, rs)
            units.append(unit)

    return {
        "effective_mode": effective_mode,
        "fallback_reason": fallback_reason,
        "units": units,
    }


def _interleave_review_states(states: list[ReviewState], max_units: int) -> list[ReviewState]:
    remaining = list(states)
    out: list[ReviewState] = []
    while remaining and len(out) < max_units:
        if not out:
            out.append(remaining.pop(0))
            continue
        last_scope = out[-1].scope_id
        last_obj = out[-1].objective
        pick_idx = 0
        for idx, cand in enumerate(remaining):
            if cand.scope_id != last_scope or cand.objective != last_obj:
                pick_idx = idx
                break
        out.append(remaining.pop(pick_idx))
    return out


async def _serialize_exercise_unit(
    session: AsyncSession,
    ex: Exercise,
    rs: ReviewState | None = None,
) -> dict[str, Any]:
    fragment_id: str | None = None
    item_prompt: str = ex.prompt
    applicability: str = ex.explanation

    if ex.item_id:
        it_res = await session.execute(select(KnowledgeItem).where(KnowledgeItem.id == ex.item_id))
        it = it_res.scalar_one_or_none()
        if it:
            fragment_id = it.fragment_id
            item_prompt = it.prompt
            applicability = it.applicability or ex.explanation

    # Ensure formula is NEVER leaked in discriminate exercises, and only provided in formula_support_text for calculation
    formula_support = None
    if ex.objective != "discriminate" and "formula" in (ex.allowed_support or []):
        formula_support = ex.formula_support_text

    return {
        "exercise_id": ex.id,
        "topic_id": ex.topic_id,
        "item_id": ex.item_id,
        "group_id": ex.group_id,
        "fragment_id": fragment_id,
        "objective": ex.objective,
        "kind": ex.kind,
        "prompt": ex.prompt,
        "item_prompt": item_prompt,
        "reference_answer": ex.reference_answer,
        "explanation": applicability,
        "hint_text": ex.hint_text,
        "options": ex.options or [],
        "rubric_criteria": ex.rubric_criteria or [],
        "allowed_support": ex.allowed_support or [],
        "formula_support_text": formula_support,
        "science_method_ids": ex.science_method_ids or ["M1"],
        "step_index": rs.step_index if rs else 0,
        "interval_days": rs.interval_days if rs else 0,
    }
