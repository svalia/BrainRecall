"""Study Session & Exercise Loop API routes (D10-D13, D42 integration, M1-M5 grading & rubric retry)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brainrecall.analytics import analytics
from brainrecall.db import get_session
from brainrecall.i18n import resolve_user_locale
from brainrecall.models import (
    Attempt,
    Exercise,
    KnowledgeGroup,
    KnowledgeItem,
    ReviewState,
    StudySession,
    User,
    UserMethodIntro,
)
from brainrecall.scheduler import (
    build_study_queue,
    compute_next_review_state,
    get_user_local_date,
)
from brainrecall.science_catalog import OBJECTIVE_TO_METHOD, SCIENCE_CATALOG
from brainrecall.security import get_current_user

router = APIRouter(prefix="/api/v1/sessions", tags=["study"])


class StartSessionRequest(BaseModel):
    mode: str = Field(default="regular", pattern="^(regular|intro|targeted_mix|group)$")
    topic_id: str | None = None
    group_id: str | None = None
    max_units: int = Field(default=10, ge=1, le=30)


class SaveDraftRequest(BaseModel):
    draft_answer: str = Field(default="", max_length=4000)
    support_seen: list[str] = Field(default_factory=list)


class SubmitAttemptRequest(BaseModel):
    idempotency_key: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exercise_id: str
    phase: str = Field(default="first_attempt", pattern="^(first_attempt|corrective)$")
    answer_text: str = Field(default="", max_length=4000)
    answer_mode: str = Field(default="written", pattern="^(written|aloud|choice)$")
    grading_mode: str = Field(default="self_check", pattern="^(exact|self_check|ai_rubric)$")
    self_grade: str | None = Field(default=None, pattern="^(correct|partial|wrong|dont_know)$")
    rubric_checked_indices: list[int] | None = None
    hint_used: bool = False
    source_seen: bool = False
    map_seen: bool = False
    elapsed_ms: int = Field(default=0, ge=0)


class DisputeAttemptRequest(BaseModel):
    override_grade: str = Field(default="correct", pattern="^(correct|partial)$")
    dispute_note: str = Field(default="", max_length=500)


def _estimate_tokens(text: str) -> int:
    # Conservative token estimate (~1 token per 3.5 chars in RU/EN)
    return max(1, len(text.strip()) // 3)


async def _find_unseen_method_intro(
    session: AsyncSession,
    user: User,
    units: list[dict[str, Any]],
) -> str | None:
    if not units:
        return None
    res = await session.execute(select(UserMethodIntro).where(UserMethodIntro.owner_id == user.id))
    intro_map = {row.method_id: row for row in res.scalars().all()}

    for u in units:
        for mid in u.get("science_method_ids", ["M1"]):
            row = intro_map.get(mid)
            ver = SCIENCE_CATALOG.get(mid, {}).get("content_version")
            if row is None or row.status == "unseen":
                return mid
            if row.status == "acknowledged" and row.acknowledged_content_version != ver:
                return mid
    return None


async def _serialize_session(session: AsyncSession, study_session: StudySession, user: User) -> dict[str, Any]:
    units = study_session.units or []
    idx = study_session.current_index
    current_unit = units[idx] if 0 <= idx < len(units) else None
    recommended_intro_method = await _find_unseen_method_intro(session, user, units)

    attempts_res = await session.execute(
        select(Attempt)
        .where(Attempt.session_id == study_session.id)
        .order_by(Attempt.created_at.asc())
    )
    attempts = list(attempts_res.scalars().all())

    by_objective: dict[str, dict[str, int]] = {}
    independent_ok = 0
    assisted_ok = 0
    needs_repeat = 0

    for att in attempts:
        if att.phase != "first_attempt":
            continue
        obj_stats = by_objective.setdefault(
            att.objective,
            {"total": 0, "independent_ok": 0, "assisted_ok": 0, "missed": 0},
        )
        obj_stats["total"] += 1
        if att.grade == "correct" and not att.assisted:
            obj_stats["independent_ok"] += 1
            independent_ok += 1
        elif att.grade in ("correct", "partial"):
            obj_stats["assisted_ok"] += 1
            assisted_ok += 1
        else:
            obj_stats["missed"] += 1
            needs_repeat += 1

    return {
        "id": study_session.id,
        "topic_id": study_session.topic_id,
        "group_id": study_session.group_id,
        "mode": study_session.mode,
        "effective_mode": study_session.effective_mode,
        "fallback_reason": study_session.fallback_reason,
        "status": study_session.status,
        "total_units": len(units),
        "current_index": idx,
        "current_phase": study_session.current_phase,
        "current_unit": current_unit,
        "draft_answer": study_session.draft_answer,
        "draft_support_seen": study_session.draft_support_seen or [],
        "recommended_intro_method": recommended_intro_method,
        "summary": {
            "total_first_attempts": independent_ok + assisted_ok + needs_repeat,
            "independent_ok": independent_ok,
            "assisted_ok": assisted_ok,
            "needs_repeat": needs_repeat,
            "by_objective": by_objective,
        },
        "local_date": study_session.local_date,
        "started_at": study_session.started_at.isoformat(),
        "completed_at": study_session.completed_at.isoformat() if study_session.completed_at else None,
    }


@router.get("/active")
async def get_active_session(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(StudySession)
        .where(
            StudySession.owner_id == user.id,
            StudySession.status == "active",
        )
        .order_by(StudySession.updated_at.desc())
        .limit(1)
    )
    active = res.scalar_one_or_none()
    if active is None:
        return {"active_session": None}
    return {"active_session": await _serialize_session(session, active, user)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def start_study_session(
    payload: StartSessionRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    # Resume existing active session if matching topic/group and not empty
    existing_res = await session.execute(
        select(StudySession)
        .where(
            StudySession.owner_id == user.id,
            StudySession.status == "active",
            StudySession.topic_id == payload.topic_id,
            StudySession.group_id == payload.group_id,
        )
        .order_by(StudySession.updated_at.desc())
        .limit(1)
    )
    existing = existing_res.scalar_one_or_none()
    if existing and existing.current_index < len(existing.units or []):
        return {"session": await _serialize_session(session, existing, user), "resumed": True}

    queue_data = await build_study_queue(
        session,
        user=user,
        mode=payload.mode,
        topic_id=payload.topic_id,
        group_id=payload.group_id,
        max_units=payload.max_units,
    )
    units = queue_data["units"]
    local_date = get_user_local_date(user.timezone)

    study_session = StudySession(
        owner_id=user.id,
        topic_id=payload.topic_id,
        group_id=payload.group_id,
        mode=payload.mode,
        effective_mode=queue_data["effective_mode"],
        fallback_reason=queue_data["fallback_reason"],
        units=units,
        current_index=0,
        current_phase="attempt",
        draft_answer="",
        draft_support_seen=[],
        status="active" if units else "completed",
        local_date=local_date,
        completed_at=datetime.now(timezone.utc) if not units else None,
    )
    session.add(study_session)
    await session.flush()

    await analytics.track(
        session,
        event_name="study_session_started",
        user=user,
        properties={
            "session_id": study_session.id,
            "mode": study_session.mode,
            "effective_mode": study_session.effective_mode,
            "units_count": len(units),
        },
    )
    await session.commit()
    await session.refresh(study_session)
    return {"session": await _serialize_session(session, study_session, user), "resumed": False}


@router.get("/{session_id}")
async def get_study_session(
    session_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(StudySession).where(
            StudySession.id == session_id,
            StudySession.owner_id == user.id,
        )
    )
    study_session = res.scalar_one_or_none()
    if study_session is None:
        raise HTTPException(status_code=404, detail="Study session not found")
    return {"session": await _serialize_session(session, study_session, user)}


@router.patch("/{session_id}/draft")
async def save_session_draft(
    session_id: str,
    payload: SaveDraftRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Preserves active session input draft across navigation per Section 3.14 exception."""
    res = await session.execute(
        select(StudySession).where(
            StudySession.id == session_id,
            StudySession.owner_id == user.id,
        )
    )
    study_session = res.scalar_one_or_none()
    if study_session is None:
        raise HTTPException(status_code=404, detail="Study session not found")

    study_session.draft_answer = payload.draft_answer
    merged_support = list(set((study_session.draft_support_seen or []) + payload.support_seen))
    study_session.draft_support_seen = merged_support
    await session.commit()
    return {
        "ok": True,
        "draft_answer": study_session.draft_answer,
        "draft_support_seen": study_session.draft_support_seen,
    }


@router.post("/{session_id}/attempts")
async def submit_session_attempt(
    session_id: str,
    payload: SubmitAttemptRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(StudySession).where(
            StudySession.id == session_id,
            StudySession.owner_id == user.id,
        )
    )
    study_session = res.scalar_one_or_none()
    if study_session is None:
        raise HTTPException(status_code=404, detail="Study session not found")

    # Idempotency check
    existing_att_res = await session.execute(
        select(Attempt).where(Attempt.idempotency_key == payload.idempotency_key)
    )
    existing_att = existing_att_res.scalar_one_or_none()
    if existing_att is not None:
        return {
            "attempt": _serialize_attempt(existing_att),
            "session": await _serialize_session(session, study_session, user),
        }

    ex_res = await session.execute(
        select(Exercise).where(
            Exercise.id == payload.exercise_id,
            Exercise.owner_id == user.id,
        )
    )
    ex = ex_res.scalar_one_or_none()
    if ex is None:
        raise HTTPException(status_code=404, detail="Exercise not found")

    # Enforce 300-token answer limit for AI rubric grading (Section 7.3)
    if payload.grading_mode == "ai_rubric" and _estimate_tokens(payload.answer_text) > 300:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ANSWER_TOO_LONG_FOR_AI",
                "message": "Written answer exceeds the 300-token limit for AI grading. Shorten your explanation or use self-check by criteria.",
                "max_tokens": 300,
            },
        )

    criteria_list = list(ex.rubric_criteria or [])
    if not criteria_list and ex.reference_answer:
        criteria_list = [ex.reference_answer[:160]]

    # Evaluate rubric criteria & grade
    rubric_results: list[dict[str, Any]] = []
    gap_summary: str | None = None

    if payload.rubric_checked_indices is not None and criteria_list:
        checked_set = set(payload.rubric_checked_indices)
        missed_criteria: list[str] = []
        for c_idx, crit_text in enumerate(criteria_list):
            passed = c_idx in checked_set
            rubric_results.append({"index": c_idx, "criterion": crit_text, "passed": passed})
            if not passed:
                missed_criteria.append(crit_text)

        if len(checked_set) == len(criteria_list):
            grade = "correct"
        elif len(checked_set) > 0:
            grade = "partial"
            gap_summary = "; ".join(missed_criteria)
        else:
            grade = "wrong"
            gap_summary = "; ".join(missed_criteria)
    elif payload.self_grade:
        grade = payload.self_grade
        for c_idx, crit_text in enumerate(criteria_list):
            passed = grade == "correct" or (grade == "partial" and c_idx == 0)
            rubric_results.append({"index": c_idx, "criterion": crit_text, "passed": passed})
        if grade != "correct" and criteria_list:
            gap_summary = criteria_list[-1]
    else:
        # Automatic comparison for exact/free_text/choice
        ans_clean = payload.answer_text.strip().lower()
        ref_clean = ex.reference_answer.strip().lower()
        if not ans_clean:
            grade = "dont_know"
        elif ans_clean == ref_clean or (len(ans_clean) >= 4 and ans_clean in ref_clean):
            grade = "correct"
        else:
            grade = "partial" if any(w in ans_clean for w in ref_clean.split()[:3] if len(w) > 3) else "wrong"

        for c_idx, crit_text in enumerate(criteria_list):
            passed = grade == "correct" or (crit_text.lower()[:12] in ans_clean)
            rubric_results.append({"index": c_idx, "criterion": crit_text, "passed": passed})
        missed = [r["criterion"] for r in rubric_results if not r["passed"]]
        if missed:
            gap_summary = "; ".join(missed)

    support_seen = set(study_session.draft_support_seen or [])
    hint_used = payload.hint_used or ("hint" in support_seen)
    source_seen = payload.source_seen or ("source" in support_seen)
    map_seen = payload.map_seen or ("map" in support_seen)
    assisted = bool(hint_used or source_seen or map_seen or payload.phase == "corrective")

    local_date = get_user_local_date(user.timezone)
    now = datetime.now(timezone.utc)

    attempt = Attempt(
        idempotency_key=payload.idempotency_key,
        session_id=study_session.id,
        owner_id=user.id,
        topic_id=ex.topic_id,
        item_id=ex.item_id,
        group_id=ex.group_id,
        exercise_id=ex.id,
        objective=ex.objective,
        phase=payload.phase,
        answer_text=payload.answer_text,
        answer_mode=payload.answer_mode,
        grading_mode=payload.grading_mode,
        grade=grade,
        assisted=assisted,
        hint_used=hint_used,
        source_seen=source_seen,
        map_seen=map_seen,
        rubric_results=rubric_results,
        gap_summary=gap_summary,
        elapsed_ms=payload.elapsed_ms,
        local_date=local_date,
    )
    session.add(attempt)
    await session.flush()

    # Update ReviewState (M2 spacing) on first_attempt or when finishing corrective attempt
    scope_type = "group" if ex.group_id else "item"
    scope_id = ex.group_id or ex.item_id or ""
    rs_res = await session.execute(
        select(ReviewState).where(
            ReviewState.owner_id == user.id,
            ReviewState.scope_type == scope_type,
            ReviewState.scope_id == scope_id,
            ReviewState.objective == ex.objective,
        )
    )
    rs = rs_res.scalar_one_or_none()
    if rs is None and scope_id:
        rs = ReviewState(
            owner_id=user.id,
            topic_id=ex.topic_id,
            scope_type=scope_type,
            scope_id=scope_id,
            objective=ex.objective,
            step_index=0,
            interval_days=0,
            due_at=now,
        )
        session.add(rs)
        await session.flush()

    if rs is not None and payload.phase == "first_attempt":
        transition = compute_next_review_state(
            current_step_index=rs.step_index,
            last_independent_success_date=rs.last_independent_success_date,
            grade=grade,
            assisted=assisted,
            local_date=local_date,
            now_utc=now,
        )
        rs.step_index = transition["step_index"]
        rs.interval_days = transition["interval_days"]
        rs.due_at = transition["due_at"]
        rs.total_attempts += 1
        if transition["increment_independent"]:
            rs.independent_successes += 1
        rs.last_independent_success_date = transition["new_last_independent_date"]
        rs.last_outcome = grade
        rs.last_assisted = assisted
        rs.last_reviewed_at = now

    if ex.item_id:
        it_res = await session.execute(select(KnowledgeItem).where(KnowledgeItem.id == ex.item_id))
        it = it_res.scalar_one_or_none()
        if it and not it.intro_completed and grade in ("correct", "partial"):
            it.intro_completed = True

    # Determine whether corrective retry is required (M4 explain / M5 relate gap)
    needs_corrective = bool(
        payload.phase == "first_attempt"
        and grade != "correct"
        and ex.objective in ("explain", "relate", "recall")
    )

    study_session.draft_answer = ""
    study_session.draft_support_seen = []

    if needs_corrective:
        study_session.current_phase = "corrective"
    else:
        study_session.current_phase = "attempt"
        study_session.current_index += 1
        if study_session.current_index >= len(study_session.units or []):
            study_session.status = "completed"
            study_session.completed_at = now

    await analytics.track(
        session,
        event_name="exercise_attempt_submitted",
        user=user,
        properties={
            "session_id": study_session.id,
            "exercise_id": ex.id,
            "objective": ex.objective,
            "phase": payload.phase,
            "grade": grade,
            "assisted": assisted,
        },
    )
    await session.commit()
    await session.refresh(study_session)

    return {
        "attempt": _serialize_attempt(attempt, rs),
        "needs_corrective": needs_corrective,
        "session": await _serialize_session(session, study_session, user),
    }


@router.post("/{session_id}/advance")
async def advance_session_unit(
    session_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Explicitly advance to next unit (e.g. if user skips corrective retry)."""
    res = await session.execute(
        select(StudySession).where(
            StudySession.id == session_id,
            StudySession.owner_id == user.id,
        )
    )
    study_session = res.scalar_one_or_none()
    if study_session is None:
        raise HTTPException(status_code=404, detail="Study session not found")

    study_session.current_phase = "attempt"
    study_session.draft_answer = ""
    study_session.draft_support_seen = []
    study_session.current_index += 1
    if study_session.current_index >= len(study_session.units or []):
        study_session.status = "completed"
        study_session.completed_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(study_session)
    return {"session": await _serialize_session(session, study_session, user)}


@router.post("/attempts/{attempt_id}/dispute")
async def dispute_attempt_grade(
    attempt_id: str,
    payload: DisputeAttemptRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(Attempt).where(
            Attempt.id == attempt_id,
            Attempt.owner_id == user.id,
        )
    )
    attempt = res.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")

    attempt.disputed = True
    attempt.dispute_note = payload.dispute_note.strip()
    attempt.grade = payload.override_grade

    scope_type = "group" if attempt.group_id else "item"
    scope_id = attempt.group_id or attempt.item_id or ""
    rs_res = await session.execute(
        select(ReviewState).where(
            ReviewState.owner_id == user.id,
            ReviewState.scope_type == scope_type,
            ReviewState.scope_id == scope_id,
            ReviewState.objective == attempt.objective,
        )
    )
    rs = rs_res.scalar_one_or_none()
    if rs and payload.override_grade == "correct" and not attempt.assisted:
        transition = compute_next_review_state(
            current_step_index=rs.step_index,
            last_independent_success_date=None,
            grade="correct",
            assisted=False,
            local_date=attempt.local_date,
        )
        rs.step_index = transition["step_index"]
        rs.interval_days = transition["interval_days"]
        rs.due_at = transition["due_at"]
        rs.last_outcome = "correct"

    await session.commit()
    return {"ok": True, "attempt": _serialize_attempt(attempt, rs)}


def _serialize_attempt(att: Attempt, rs: ReviewState | None = None) -> dict[str, Any]:
    return {
        "id": att.id,
        "session_id": att.session_id,
        "exercise_id": att.exercise_id,
        "objective": att.objective,
        "phase": att.phase,
        "answer_text": att.answer_text,
        "answer_mode": att.answer_mode,
        "grading_mode": att.grading_mode,
        "grade": att.grade,
        "assisted": att.assisted,
        "hint_used": att.hint_used,
        "source_seen": att.source_seen,
        "map_seen": att.map_seen,
        "rubric_results": att.rubric_results or [],
        "gap_summary": att.gap_summary,
        "disputed": att.disputed,
        "next_interval_days": rs.interval_days if rs else None,
        "next_step_index": rs.step_index if rs else None,
    }
