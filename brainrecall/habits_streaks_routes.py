"""Daily Plan ('Today' D03), Atomic Habits (D19-D23), Streaks, Achievements & Freeze Protection (D36-D39) (Dev Spec v1.14 Sections 7.1, 7.2)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from brainrecall.analytics import analytics
from brainrecall.config import PLAN_LIMITS, settings
from brainrecall.db import get_session
from brainrecall.i18n import resolve_user_locale, t
from brainrecall.models import (
    AchievementGrant,
    Attempt,
    CelebrationInbox,
    DayPlan,
    Entitlement,
    FreezeLedger,
    Habit,
    HabitOccurrence,
    PaymentOrder,
    ProtectedDate,
    ProtectionInterval,
    ReturnNotice,
    ReviewState,
    RewardCycle,
    StreakAggregate,
    StudySession,
    Topic,
    User,
)
from brainrecall.scheduler import get_user_local_date
from brainrecall.security import get_current_user
from brainrecall.telegram_api import tg_client

router = APIRouter(prefix="/api/v1", tags=["habits_streaks"])

MILESTONE_THRESHOLDS: tuple[int, ...] = (1, 3, 7, 14, 30, 60, 100, 180, 365)
MAX_FREEZE_STOCK = 2
ROLLING_PROTECTED_CAP_30D = 7


class HabitCreateRequest(BaseModel):
    habit_kind: str = Field(default="build", pattern="^(build|replace)$")
    title: str = Field(..., min_length=1, max_length=200)
    signal: str = Field(..., min_length=1, max_length=250)
    action: str = Field(..., min_length=1, max_length=250)
    minimum_version: str = Field(..., min_length=1, max_length=250)
    environment_prep: str = Field(default="", max_length=500)
    attractiveness: str = Field(default="", max_length=500)
    reward: str = Field(default="", max_length=500)
    obstacle: str = Field(default="", max_length=500)
    fallback_plan: str = Field(default="", max_length=500)
    unwanted_need: str = Field(default="", max_length=500)
    days_of_week: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7])
    reminder_time: str | None = Field(default=None, max_length=16)
    topic_id: str | None = None
    linked_item_id: str | None = None


class HabitUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    signal: str | None = None
    action: str | None = None
    minimum_version: str | None = None
    environment_prep: str | None = None
    attractiveness: str | None = None
    reward: str | None = None
    obstacle: str | None = None
    fallback_plan: str | None = None
    unwanted_need: str | None = None
    days_of_week: list[int] | None = None
    reminder_time: str | None = None
    status: str | None = Field(default=None, pattern="^(active|paused|archived)$")


class HabitCheckinRequest(BaseModel):
    local_date: str | None = None  # YYYY-MM-DD, defaults to today in user's timezone
    outcome: str = Field(..., pattern="^(full_done|minimum_done|skipped|no_opportunity)$")
    reason_note: str = Field(default="", max_length=500)


class HabitAiPlanRequest(BaseModel):
    goal_description: str = Field(..., min_length=3, max_length=500)
    habit_kind: str = Field(default="build", pattern="^(build|replace)$")


class FreezeToggleRequest(BaseModel):
    freeze_auto_enabled: bool


class FreezeApplyDayRequest(BaseModel):
    local_date: str | None = None


class FreezePurchaseRequest(BaseModel):
    kind: str = Field(..., pattern="^(freeze_day|freeze_week)$")
    start_date: str | None = None  # Required for freeze_week (tomorrow .. +30d)


async def get_freeze_stock(session: AsyncSession, user_id: str) -> int:
    res = await session.execute(
        select(FreezeLedger)
        .where(FreezeLedger.owner_id == user_id)
        .order_by(FreezeLedger.created_at.desc())
        .limit(1)
    )
    latest = res.scalar_one_or_none()
    if latest is None:
        return 0
    return max(0, min(MAX_FREEZE_STOCK, latest.balance_after))


async def get_protected_dates_last_30d(session: AsyncSession, user_id: str, today_str: str) -> list[str]:
    today_dt = date.fromisoformat(today_str)
    start_dt = (today_dt - timedelta(days=29)).isoformat()
    res = await session.execute(
        select(ProtectedDate.local_date).where(
            ProtectedDate.owner_id == user_id,
            ProtectedDate.local_date >= start_dt,
            ProtectedDate.local_date <= today_str,
        )
    )
    return sorted(res.scalars().all())


async def _issue_free_freeze_grant_if_eligible(
    session: AsyncSession,
    user: User,
    local_date: str,
) -> bool:
    """
    Section 7.2 Free Freeze Grant Rules:
    - 1 free starter freeze on the user's 1st lifetime earned day.
    - +1 free freeze every 7 lifetime earned days (7, 14, 21, ...).
    - Max stock is 2. If stock is already 2/2 when a threshold is reached, log `skipped_at_cap` (no hidden queue).
    """
    rc_res = await session.execute(select(RewardCycle).where(RewardCycle.owner_id == user.id))
    rc = rc_res.scalar_one_or_none()
    if rc is None:
        rc = RewardCycle(owner_id=user.id, earned_total=0, starter_grant_issued=False, last_processed_threshold=0)
        session.add(rc)
        await session.flush()

    rc.earned_total += 1
    current_stock = await get_freeze_stock(session, user.id)
    granted = False

    # 1. Starter grant on 1st earned day
    if not rc.starter_grant_issued and rc.earned_total >= 1:
        rc.starter_grant_issued = True
        entry_key = f"starter_grant:{user.id}"
        existing = (
            await session.execute(select(FreezeLedger).where(FreezeLedger.entry_key == entry_key))
        ).scalar_one_or_none()
        if existing is None:
            if current_stock < MAX_FREEZE_STOCK:
                current_stock += 1
                session.add(
                    FreezeLedger(
                        owner_id=user.id,
                        entry_key=entry_key,
                        kind="grant",
                        origin_kind="free",
                        amount_delta=1,
                        balance_after=current_stock,
                        source_id="starter_1st_earned",
                        local_date=local_date,
                        note="Starter free freeze on 1st earned day",
                    )
                )
                granted = True
            else:
                session.add(
                    FreezeLedger(
                        owner_id=user.id,
                        entry_key=entry_key,
                        kind="skipped_at_cap",
                        origin_kind="free",
                        amount_delta=0,
                        balance_after=current_stock,
                        source_id="starter_1st_earned",
                        local_date=local_date,
                        note="Skipped starter freeze at cap 2/2",
                    )
                )

    # 2. Every 7 earned days reward cycle
    if rc.earned_total >= 7 and rc.earned_total % 7 == 0 and rc.last_processed_threshold < rc.earned_total:
        threshold = rc.earned_total
        rc.last_processed_threshold = threshold
        entry_key = f"cycle_grant:{user.id}:{threshold}"
        existing = (
            await session.execute(select(FreezeLedger).where(FreezeLedger.entry_key == entry_key))
        ).scalar_one_or_none()
        if existing is None:
            if current_stock < MAX_FREEZE_STOCK:
                current_stock += 1
                session.add(
                    FreezeLedger(
                        owner_id=user.id,
                        entry_key=entry_key,
                        kind="grant",
                        origin_kind="free",
                        amount_delta=1,
                        balance_after=current_stock,
                        source_id=f"earned_{threshold}",
                        local_date=local_date,
                        note=f"Free freeze for {threshold} earned days",
                    )
                )
                granted = True
            else:
                session.add(
                    FreezeLedger(
                        owner_id=user.id,
                        entry_key=entry_key,
                        kind="skipped_at_cap",
                        origin_kind="free",
                        amount_delta=0,
                        balance_after=current_stock,
                        source_id=f"earned_{threshold}",
                        local_date=local_date,
                        note=f"Skipped cycle freeze at cap 2/2 ({threshold} earned days)",
                    )
                )

    return granted


async def _ensure_or_reconcile_day_plan(
    session: AsyncSession,
    user: User,
    local_date: str | None = None,
) -> DayPlan:
    today_str = local_date or get_user_local_date(user.timezone)
    today_dt = date.fromisoformat(today_str)
    weekday_iso = today_dt.isoweekday()  # 1=Mon..7=Sun

    dp_res = await session.execute(
        select(DayPlan).where(
            DayPlan.owner_id == user.id,
            DayPlan.local_date == today_str,
        )
    )
    dp = dp_res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if dp is None:
        # Snapshot due reviews and scheduled habits for today
        due_rs_res = await session.execute(
            select(ReviewState).where(
                ReviewState.owner_id == user.id,
                ReviewState.due_at <= now,
            )
        )
        due_states = list(due_rs_res.scalars().all())
        req_item_ids = list({rs.scope_id for rs in due_states})

        habits_res = await session.execute(
            select(Habit).where(
                Habit.owner_id == user.id,
                Habit.status == "active",
            )
        )
        scheduled_habits = [
            h for h in habits_res.scalars().all() if weekday_iso in (h.days_of_week or [1, 2, 3, 4, 5, 6, 7])
        ]
        req_habit_ids = [h.id for h in scheduled_habits]

        initial_state = "pending" if (req_item_ids or req_habit_ids) else "neutral"
        dp = DayPlan(
            owner_id=user.id,
            local_date=today_str,
            timezone_snapshot=user.timezone,
            required_reviews_total=len(req_item_ids),
            required_reviews_done=0,
            required_habits_total=len(req_habit_ids),
            required_habits_done=0,
            required_item_ids=req_item_ids,
            completed_item_ids=[],
            required_habit_ids=req_habit_ids,
            completed_habit_ids=[],
            day_state=initial_state,
        )
        session.add(dp)
        await session.flush()

    # Reconcile today's completions
    atts_res = await session.execute(
        select(Attempt).where(
            Attempt.owner_id == user.id,
            Attempt.local_date == today_str,
        )
    )
    today_attempts = list(atts_res.scalars().all())
    done_scopes = {att.group_id or att.item_id for att in today_attempts if (att.group_id or att.item_id)}

    occ_res = await session.execute(
        select(HabitOccurrence).where(
            HabitOccurrence.owner_id == user.id,
            HabitOccurrence.local_date == today_str,
        )
    )
    today_occs = list(occ_res.scalars().all())
    done_habits = {
        occ.habit_id
        for occ in today_occs
        if occ.outcome in ("full_done", "minimum_done")
    }
    neutral_habits = {
        occ.habit_id
        for occ in today_occs
        if occ.outcome in ("no_opportunity", "planned_pause")
    }

    # Also include newly created habits today in required_habit_ids if not yet tracked
    active_habits_res = await session.execute(
        select(Habit).where(Habit.owner_id == user.id, Habit.status == "active")
    )
    for h in active_habits_res.scalars().all():
        if weekday_iso in (h.days_of_week or [1, 2, 3, 4, 5, 6, 7]):
            if h.id not in (dp.required_habit_ids or []):
                dp.required_habit_ids = list(dp.required_habit_ids or []) + [h.id]

    effective_req_habits = [hid for hid in (dp.required_habit_ids or []) if hid not in neutral_habits]
    comp_habits = [hid for hid in effective_req_habits if hid in done_habits]

    comp_items = [iid for iid in (dp.required_item_ids or []) if iid in done_scopes]
    voluntary_done = bool(len(done_scopes) > 0 or len(done_habits) > 0)

    dp.required_reviews_total = len(dp.required_item_ids or [])
    dp.required_reviews_done = len(comp_items)
    dp.completed_item_ids = comp_items
    dp.required_habits_total = len(effective_req_habits)
    dp.required_habits_done = len(comp_habits)
    dp.completed_habit_ids = comp_habits
    dp.voluntary_practice_done = voluntary_done

    was_earned = dp.day_state == "earned"

    # Check if date is protected by Freeze
    prot_res = await session.execute(
        select(ProtectedDate).where(
            ProtectedDate.owner_id == user.id,
            ProtectedDate.local_date == today_str,
        )
    )
    is_protected = prot_res.scalar_one_or_none() is not None

    total_required = dp.required_reviews_total + dp.required_habits_total
    total_done = dp.required_reviews_done + dp.required_habits_done

    if total_required > 0 and total_done >= total_required:
        dp.day_state = "earned"
    elif total_required == 0 and voluntary_done:
        dp.day_state = "earned"
    elif is_protected:
        dp.day_state = "frozen"
    elif total_required == 0:
        dp.day_state = "neutral"
    else:
        dp.day_state = "pending"

    if dp.day_state == "earned" and not was_earned:
        await _on_user_day_earned(session, user, today_str)

    await session.flush()
    return dp


async def _on_user_day_earned(
    session: AsyncSession,
    user: User,
    local_date: str,
) -> None:
    agg_res = await session.execute(
        select(StreakAggregate).where(
            StreakAggregate.owner_id == user.id,
            StreakAggregate.scope_type == "user",
            StreakAggregate.scope_id == user.id,
        )
    )
    agg = agg_res.scalar_one_or_none()
    if agg is None:
        agg = StreakAggregate(
            owner_id=user.id,
            scope_type="user",
            scope_id=user.id,
            current_streak=0,
            best_streak=0,
        )
        session.add(agg)
        await session.flush()

    if agg.last_earned_date != local_date:
        agg.current_streak += 1
        if agg.current_streak > agg.best_streak:
            agg.best_streak = agg.current_streak
        agg.last_earned_date = local_date
        agg.as_of_date = local_date

    free_freeze_granted = await _issue_free_freeze_grant_if_eligible(session, user, local_date)

    # Check milestone badges (1, 3, 7, 14, 30, 60, 100, 180, 365)
    new_grants: list[dict[str, Any]] = []
    for thresh in MILESTONE_THRESHOLDS:
        if agg.current_streak >= thresh:
            ex_grant = (
                await session.execute(
                    select(AchievementGrant).where(
                        AchievementGrant.owner_id == user.id,
                        AchievementGrant.scope_type == "user",
                        AchievementGrant.scope_id == user.id,
                        AchievementGrant.threshold == thresh,
                    )
                )
            ).scalar_one_or_none()
            if ex_grant is None:
                grant = AchievementGrant(
                    owner_id=user.id,
                    scope_type="user",
                    scope_id=user.id,
                    scope_title_snapshot="BrainRecall",
                    threshold=thresh,
                    status="active",
                )
                session.add(grant)
                new_grants.append({"scope_type": "user", "threshold": thresh, "title": "BrainRecall"})

    if new_grants or free_freeze_granted:
        highest = max([g["threshold"] for g in new_grants] or [agg.current_streak])
        session.add(
            CelebrationInbox(
                owner_id=user.id,
                grants_payload=new_grants,
                highest_threshold=highest,
                free_freeze_granted=free_freeze_granted,
            )
        )


async def _recompute_habit_streak(session: AsyncSession, user: User, habit: Habit) -> StreakAggregate:
    occ_res = await session.execute(
        select(HabitOccurrence)
        .where(
            HabitOccurrence.habit_id == habit.id,
            HabitOccurrence.owner_id == user.id,
        )
        .order_by(HabitOccurrence.local_date.asc())
    )
    occs = list(occ_res.scalars().all())

    cur = 0
    best = 0
    last_earned: str | None = None
    for occ in occs:
        if occ.outcome in ("full_done", "minimum_done"):
            cur += 1
            if cur > best:
                best = cur
            last_earned = occ.local_date
        elif occ.outcome == "skipped":
            cur = 0
        # no_opportunity / planned_pause leaves `cur` unchanged (neutral)

    agg_res = await session.execute(
        select(StreakAggregate).where(
            StreakAggregate.owner_id == user.id,
            StreakAggregate.scope_type == "habit",
            StreakAggregate.scope_id == habit.id,
        )
    )
    agg = agg_res.scalar_one_or_none()
    if agg is None:
        agg = StreakAggregate(
            owner_id=user.id,
            scope_type="habit",
            scope_id=habit.id,
            current_streak=cur,
            best_streak=best,
            last_earned_date=last_earned,
        )
        session.add(agg)
    else:
        agg.current_streak = cur
        agg.best_streak = max(agg.best_streak, best)
        agg.last_earned_date = last_earned
    await session.flush()
    return agg


def _serialize_habit(
    habit: Habit,
    streak: StreakAggregate | None = None,
    today_occ: HabitOccurrence | None = None,
    recent_occurrences: list[HabitOccurrence] | None = None,
) -> dict[str, Any]:
    return {
        "id": habit.id,
        "habit_kind": habit.habit_kind,
        "title": habit.title,
        "signal": habit.signal,
        "action": habit.action,
        "minimum_version": habit.minimum_version,
        "environment_prep": habit.environment_prep,
        "attractiveness": habit.attractiveness,
        "reward": habit.reward,
        "obstacle": habit.obstacle,
        "fallback_plan": habit.fallback_plan,
        "unwanted_need": habit.unwanted_need,
        "days_of_week": habit.days_of_week or [1, 2, 3, 4, 5, 6, 7],
        "reminder_time": habit.reminder_time,
        "topic_id": habit.topic_id,
        "linked_item_id": habit.linked_item_id,
        "status": habit.status,
        "current_streak": streak.current_streak if streak else 0,
        "best_streak": streak.best_streak if streak else 0,
        "today_outcome": today_occ.outcome if today_occ else None,
        "recent_occurrences": [
            {
                "local_date": o.local_date,
                "outcome": o.outcome,
                "reason_note": o.reason_note,
            }
            for o in (recent_occurrences or [])
        ],
    }


@router.get("/today")
async def get_today_plan_d03(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    today_str = get_user_local_date(user.timezone)
    dp = await _ensure_or_reconcile_day_plan(session, user, today_str)

    # User streak
    agg_res = await session.execute(
        select(StreakAggregate).where(
            StreakAggregate.owner_id == user.id,
            StreakAggregate.scope_type == "user",
            StreakAggregate.scope_id == user.id,
        )
    )
    user_streak = agg_res.scalar_one_or_none()

    # Active study session if any
    sess_res = await session.execute(
        select(StudySession)
        .where(StudySession.owner_id == user.id, StudySession.status == "active")
        .order_by(StudySession.updated_at.desc())
        .limit(1)
    )
    active_sess = sess_res.scalar_one_or_none()

    # Today's habits
    habits_res = await session.execute(
        select(Habit).where(Habit.owner_id == user.id, Habit.status == "active").order_by(Habit.created_at.asc())
    )
    habits = list(habits_res.scalars().all())
    habits_payload: list[dict[str, Any]] = []
    for h in habits:
        occ_res = await session.execute(
            select(HabitOccurrence).where(
                HabitOccurrence.habit_id == h.id,
                HabitOccurrence.local_date == today_str,
            )
        )
        t_occ = occ_res.scalar_one_or_none()
        h_stk = await _recompute_habit_streak(session, user, h)
        habits_payload.append(_serialize_habit(h, h_stk, t_occ))

    # Pending celebration (D38) or return notice (D37)
    cel_res = await session.execute(
        select(CelebrationInbox)
        .where(CelebrationInbox.owner_id == user.id, CelebrationInbox.seen_at.is_(None))
        .order_by(CelebrationInbox.created_at.desc())
        .limit(1)
    )
    cel = cel_res.scalar_one_or_none()

    ret_res = await session.execute(
        select(ReturnNotice)
        .where(ReturnNotice.owner_id == user.id, ReturnNotice.seen_at.is_(None))
        .order_by(ReturnNotice.created_at.desc())
        .limit(1)
    )
    ret_notice = ret_res.scalar_one_or_none()

    freeze_stock = await get_freeze_stock(session, user.id)
    await session.commit()

    return {
        "local_date": today_str,
        "day_plan": {
            "day_state": dp.day_state,
            "required_reviews_total": dp.required_reviews_total,
            "required_reviews_done": dp.required_reviews_done,
            "required_habits_total": dp.required_habits_total,
            "required_habits_done": dp.required_habits_done,
            "voluntary_practice_done": dp.voluntary_practice_done,
        },
        "streak": {
            "current": user_streak.current_streak if user_streak else 0,
            "best": user_streak.best_streak if user_streak else 0,
            "freeze_stock": freeze_stock,
            "freeze_max": MAX_FREEZE_STOCK,
        },
        "active_session_id": active_sess.id if active_sess else None,
        "habits": habits_payload,
        "celebration": (
            {
                "id": cel.id,
                "highest_threshold": cel.highest_threshold,
                "grants": cel.grants_payload,
                "free_freeze_granted": cel.free_freeze_granted,
            }
            if cel
            else None
        ),
        "return_notice": (
            {
                "id": ret_notice.id,
                "previous_streak": ret_notice.previous_streak,
                "best_streak": ret_notice.best_streak,
            }
            if ret_notice
            else None
        ),
    }


@router.post("/celebrations/{celebration_id}/ack")
async def acknowledge_celebration_d38(
    celebration_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(CelebrationInbox).where(
            CelebrationInbox.id == celebration_id,
            CelebrationInbox.owner_id == user.id,
        )
    )
    cel = res.scalar_one_or_none()
    if cel:
        cel.seen_at = datetime.now(timezone.utc)
        await session.commit()
    return {"ok": True}


@router.get("/habits")
async def list_habits_d19(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    today_str = get_user_local_date(user.timezone)
    res = await session.execute(
        select(Habit).where(Habit.owner_id == user.id, Habit.status != "archived").order_by(Habit.created_at.desc())
    )
    habits = list(res.scalars().all())

    out: list[dict[str, Any]] = []
    for h in habits:
        occ_res = await session.execute(
            select(HabitOccurrence).where(
                HabitOccurrence.habit_id == h.id,
                HabitOccurrence.local_date == today_str,
            )
        )
        t_occ = occ_res.scalar_one_or_none()
        stk = await _recompute_habit_streak(session, user, h)
        out.append(_serialize_habit(h, stk, t_occ))

    ent_res = await session.execute(select(Entitlement).where(Entitlement.owner_id == user.id))
    ent = ent_res.scalar_one_or_none()
    plan_code = ent.plan_code if (ent and ent.status == "active") else "free"
    limits = PLAN_LIMITS.get(plan_code, PLAN_LIMITS["free"])
    active_count = sum(1 for h in habits if h.status == "active")

    await session.commit()
    return {
        "habits": out,
        "active_count": active_count,
        "active_limit": limits["habits"],
        "plan": plan_code,
    }


@router.post("/habits", status_code=status.HTTP_201_CREATED)
async def create_habit_d20(
    payload: HabitCreateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    ent_res = await session.execute(select(Entitlement).where(Entitlement.owner_id == user.id))
    ent = ent_res.scalar_one_or_none()
    plan_code = ent.plan_code if (ent and ent.status == "active") else "free"
    limits = PLAN_LIMITS.get(plan_code, PLAN_LIMITS["free"])

    active_res = await session.execute(
        select(func.count(Habit.id)).where(
            Habit.owner_id == user.id,
            Habit.status == "active",
        )
    )
    if int(active_res.scalar() or 0) >= limits["habits"]:
        raise HTTPException(
            status_code=403,
            detail={"code": "HABIT_LIMIT_REACHED", "plan": plan_code, "limit": limits["habits"]},
        )

    habit = Habit(
        owner_id=user.id,
        topic_id=payload.topic_id,
        linked_item_id=payload.linked_item_id,
        habit_kind=payload.habit_kind,
        title=payload.title.strip(),
        signal=payload.signal.strip(),
        action=payload.action.strip(),
        minimum_version=payload.minimum_version.strip(),
        environment_prep=payload.environment_prep.strip(),
        attractiveness=payload.attractiveness.strip(),
        reward=payload.reward.strip(),
        obstacle=payload.obstacle.strip(),
        fallback_plan=payload.fallback_plan.strip(),
        unwanted_need=payload.unwanted_need.strip(),
        days_of_week=payload.days_of_week or [1, 2, 3, 4, 5, 6, 7],
        reminder_time=payload.reminder_time,
        status="active",
    )
    session.add(habit)
    await session.flush()

    stk = await _recompute_habit_streak(session, user, habit)
    await analytics.track(
        session,
        event_name="habit_created",
        user=user,
        properties={"habit_id": habit.id, "habit_kind": habit.habit_kind},
    )
    await session.commit()
    await session.refresh(habit)
    return {"habit": _serialize_habit(habit, stk, None)}


@router.get("/habits/{habit_id}")
async def get_habit_detail_d21(
    habit_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(Habit).where(Habit.id == habit_id, Habit.owner_id == user.id)
    )
    habit = res.scalar_one_or_none()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    today_str = get_user_local_date(user.timezone)
    occs_res = await session.execute(
        select(HabitOccurrence)
        .where(HabitOccurrence.habit_id == habit.id)
        .order_by(HabitOccurrence.local_date.desc())
        .limit(30)
    )
    occs = list(occs_res.scalars().all())
    today_occ = next((o for o in occs if o.local_date == today_str), None)
    stk = await _recompute_habit_streak(session, user, habit)
    await session.commit()
    return {"habit": _serialize_habit(habit, stk, today_occ, occs)}


@router.patch("/habits/{habit_id}")
async def update_habit(
    habit_id: str,
    payload: HabitUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(
        select(Habit).where(Habit.id == habit_id, Habit.owner_id == user.id)
    )
    habit = res.scalar_one_or_none()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    if payload.title is not None:
        habit.title = payload.title.strip()
    if payload.signal is not None:
        habit.signal = payload.signal.strip()
    if payload.action is not None:
        habit.action = payload.action.strip()
    if payload.minimum_version is not None:
        habit.minimum_version = payload.minimum_version.strip()
    if payload.environment_prep is not None:
        habit.environment_prep = payload.environment_prep.strip()
    if payload.attractiveness is not None:
        habit.attractiveness = payload.attractiveness.strip()
    if payload.reward is not None:
        habit.reward = payload.reward.strip()
    if payload.obstacle is not None:
        habit.obstacle = payload.obstacle.strip()
    if payload.fallback_plan is not None:
        habit.fallback_plan = payload.fallback_plan.strip()
    if payload.unwanted_need is not None:
        habit.unwanted_need = payload.unwanted_need.strip()
    if payload.days_of_week is not None:
        habit.days_of_week = payload.days_of_week
    if payload.reminder_time is not None:
        habit.reminder_time = payload.reminder_time
    if payload.status is not None:
        habit.status = payload.status

    stk = await _recompute_habit_streak(session, user, habit)
    await session.commit()
    await session.refresh(habit)
    return {"habit": _serialize_habit(habit, stk, None)}


@router.post("/habits/{habit_id}/checkin")
async def checkin_habit_d22(
    habit_id: str,
    payload: HabitCheckinRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Record or correct a habit occurrence (D22):
    - Supports `full_done`, `minimum_done`, `skipped`, `no_opportunity`.
    - Allows retroactive correction up to 7 local days back (Section 7.1), recalculating streaks deterministically.
    """
    res = await session.execute(
        select(Habit).where(Habit.id == habit_id, Habit.owner_id == user.id)
    )
    habit = res.scalar_one_or_none()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    today_str = get_user_local_date(user.timezone)
    target_date_str = payload.local_date or today_str
    try:
        target_dt = date.fromisoformat(target_date_str)
        today_dt = date.fromisoformat(today_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid local_date format") from exc

    delta_days = (today_dt - target_dt).days
    if delta_days < 0 or delta_days > 7:
        raise HTTPException(
            status_code=400,
            detail="Habit occurrences can only be recorded or corrected for today or up to 7 days back.",
        )

    occ_res = await session.execute(
        select(HabitOccurrence).where(
            HabitOccurrence.habit_id == habit.id,
            HabitOccurrence.local_date == target_date_str,
        )
    )
    occ = occ_res.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if occ is None:
        occ = HabitOccurrence(
            habit_id=habit.id,
            owner_id=user.id,
            local_date=target_date_str,
            timezone_snapshot=user.timezone,
            planned_opportunity=(payload.outcome != "no_opportunity"),
            outcome=payload.outcome,
            reason_note=payload.reason_note.strip(),
        )
        session.add(occ)
    else:
        occ.outcome = payload.outcome
        occ.planned_opportunity = payload.outcome != "no_opportunity"
        occ.reason_note = payload.reason_note.strip()
        occ.corrected_at = now

    await session.flush()
    stk = await _recompute_habit_streak(session, user, habit)
    dp = await _ensure_or_reconcile_day_plan(session, user, target_date_str)

    await analytics.track(
        session,
        event_name="habit_checkin_recorded",
        user=user,
        properties={
            "habit_id": habit.id,
            "local_date": target_date_str,
            "outcome": payload.outcome,
            "day_state": dp.day_state,
        },
    )
    await session.commit()
    return {
        "ok": True,
        "habit": _serialize_habit(habit, stk, occ),
        "day_state": dp.day_state,
    }


@router.post("/habits/ai-draft")
async def generate_habit_ai_draft_d23(
    payload: HabitAiPlanRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Generates a structured 4-law Atomic Habit draft (D23) while preserving the D20 wizard state."""
    loc = resolve_user_locale(
        locale_override=user.locale if user.locale_override else None,
        saved_locale=user.locale,
    )
    goal = payload.goal_description.strip()
    if loc == "en":
        draft = {
            "habit_kind": payload.habit_kind,
            "title": goal[:80],
            "signal": "Right after morning coffee / sitting at my desk",
            "action": f" spend 15 minutes on: {goal[:100]}",
            "minimum_version": f"2-minute minimum: open notes and do 1 small step of {goal[:60]}",
            "environment_prep": "Keep materials open on the desk the evening before",
            "obstacle": "Fatigue or busy schedule in the evening",
            "fallback_plan": "If short on time, complete the 2-minute minimum version immediately",
        }
    else:
        draft = {
            "habit_kind": payload.habit_kind,
            "title": goal[:80],
            "signal": "Сразу после утреннего кофе / когда открываю рабочий стол",
            "action": f"Уделить 15 минут задаче: {goal[:100]}",
            "minimum_version": f"Минимум на 2 минуты: сделать 1 микро-шаг по «{goal[:60]}»",
            "environment_prep": "Приготовить всё необходимое на видном месте с вечера",
            "obstacle": "Усталость вечером или срочные дела",
            "fallback_plan": "Если мало времени — выполнить программу-минимум за 2 минуты",
        }
    return {"draft": draft}


@router.get("/streaks")
async def get_streaks_and_protection_d36_d39(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    today_str = get_user_local_date(user.timezone)
    await _ensure_or_reconcile_day_plan(session, user, today_str)

    agg_res = await session.execute(
        select(StreakAggregate).where(
            StreakAggregate.owner_id == user.id,
            StreakAggregate.scope_type == "user",
            StreakAggregate.scope_id == user.id,
        )
    )
    user_streak = agg_res.scalar_one_or_none()

    rc_res = await session.execute(select(RewardCycle).where(RewardCycle.owner_id == user.id))
    rc = rc_res.scalar_one_or_none()
    earned_total = rc.earned_total if rc else 0
    days_until_next_free_freeze = 1 if earned_total == 0 else (7 - (earned_total % 7))

    stock = await get_freeze_stock(session, user.id)
    protected_30d = await get_protected_dates_last_30d(session, user.id, today_str)

    pi_res = await session.execute(
        select(ProtectionInterval).where(
            ProtectionInterval.owner_id == user.id,
            ProtectionInterval.status == "active",
        )
    )
    active_intervals = [
        {
            "id": pi.id,
            "start_date": pi.start_date,
            "end_date_exclusive": pi.end_date_exclusive,
            "status": pi.status,
        }
        for pi in pi_res.scalars().all()
    ]

    grants_res = await session.execute(
        select(AchievementGrant)
        .where(AchievementGrant.owner_id == user.id, AchievementGrant.status == "active")
        .order_by(AchievementGrant.threshold.asc())
    )
    granted_thresholds = {g.threshold for g in grants_res.scalars().all()}

    badges = [
        {
            "threshold": th,
            "unlocked": th in granted_thresholds,
        }
        for th in MILESTONE_THRESHOLDS
    ]

    # Last 14 days calendar states
    today_dt = date.fromisoformat(today_str)
    start_cal_str = (today_dt - timedelta(days=13)).isoformat()
    dp_res = await session.execute(
        select(DayPlan).where(
            DayPlan.owner_id == user.id,
            DayPlan.local_date >= start_cal_str,
        )
    )
    dp_map = {d.local_date: d.day_state for d in dp_res.scalars().all()}
    prot_set = set(protected_30d)

    calendar_days: list[dict[str, Any]] = []
    for offset in range(13, -1, -1):
        d_str = (today_dt - timedelta(days=offset)).isoformat()
        st = "frozen" if d_str in prot_set else dp_map.get(d_str, "neutral")
        calendar_days.append({"date": d_str, "state": st})

    await session.commit()
    return {
        "current_streak": user_streak.current_streak if user_streak else 0,
        "best_streak": user_streak.best_streak if user_streak else 0,
        "earned_total": earned_total,
        "days_until_next_free_freeze": days_until_next_free_freeze,
        "freeze": {
            "stock": stock,
            "max_stock": MAX_FREEZE_STOCK,
            "auto_enabled": user.freeze_auto_enabled,
            "protected_30d_used": len(protected_30d),
            "protected_30d_cap": ROLLING_PROTECTED_CAP_30D,
            "price_day_xtr": settings.freeze_day_price_xtr,
            "price_week_xtr": settings.freeze_week_price_xtr,
            "active_intervals": active_intervals,
        },
        "badges": badges,
        "calendar": calendar_days,
    }


@router.patch("/streaks/freeze-settings")
async def update_freeze_settings_d39(
    payload: FreezeToggleRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    user.freeze_auto_enabled = payload.freeze_auto_enabled
    await session.commit()
    return {"ok": True, "freeze_auto_enabled": user.freeze_auto_enabled}


@router.post("/streaks/freeze-apply")
async def apply_single_day_freeze_d39(
    payload: FreezeApplyDayRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    today_str = get_user_local_date(user.timezone)
    target_date = payload.local_date or today_str

    existing_prot = (
        await session.execute(
            select(ProtectedDate).where(
                ProtectedDate.owner_id == user.id,
                ProtectedDate.local_date == target_date,
            )
        )
    ).scalar_one_or_none()
    if existing_prot is not None:
        return {"ok": True, "already_protected": True, "local_date": target_date}

    protected_30d = await get_protected_dates_last_30d(session, user.id, today_str)
    if len(protected_30d) >= ROLLING_PROTECTED_CAP_30D:
        raise HTTPException(
            status_code=400,
            detail="Rolling 30-day protection cap (7 days out of 30) reached.",
        )

    stock = await get_freeze_stock(session, user.id)
    if stock <= 0:
        raise HTTPException(status_code=400, detail="No single-day freeze in stock.")

    new_stock = stock - 1
    ledger = FreezeLedger(
        owner_id=user.id,
        entry_key=f"consume:{user.id}:{target_date}",
        kind="consume",
        origin_kind="free",
        amount_delta=-1,
        balance_after=new_stock,
        source_id="manual_or_auto",
        local_date=target_date,
        note=f"Protected date {target_date}",
    )
    session.add(ledger)
    await session.flush()

    session.add(
        ProtectedDate(
            owner_id=user.id,
            local_date=target_date,
            source_type="day_stock",
            source_id=ledger.id,
            streak_saved=1,
        )
    )

    dp = await _ensure_or_reconcile_day_plan(session, user, target_date)
    if dp.day_state != "earned":
        dp.day_state = "frozen"

    await session.commit()
    return {"ok": True, "local_date": target_date, "stock_after": new_stock, "day_state": dp.day_state}


@router.post("/streaks/freeze-purchase")
async def purchase_freeze_d39(
    payload: FreezePurchaseRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    today_str = get_user_local_date(user.timezone)
    today_dt = date.fromisoformat(today_str)
    protected_30d = await get_protected_dates_last_30d(session, user.id, today_str)

    if payload.kind == "freeze_day":
        stock = await get_freeze_stock(session, user.id)
        if stock >= MAX_FREEZE_STOCK:
            raise HTTPException(
                status_code=400,
                detail="Freeze stock is already at maximum (2/2).",
            )
        if len(protected_30d) >= ROLLING_PROTECTED_CAP_30D:
            raise HTTPException(
                status_code=400,
                detail="Rolling 30-day protection cap (7/30) reached.",
            )
        stars_amount = settings.freeze_day_price_xtr
        inv_payload = f'{{"kind":"freeze_day","uid":"{user.id}"}}'
        inv_resp = await tg_client.create_invoice_link(
            title="BrainRecall — Freeze (1 day)",
            description="Single-day Streak Freeze protection",
            payload=inv_payload,
            stars_amount=stars_amount,
        )
        invoice_link = inv_resp.get("result")

        # In development/test mode or if invoice link isn't opened, also record a pending order
        order = PaymentOrder(
            owner_id=user.id,
            telegram_user_id=user.telegram_id,
            product_type="freeze_day",
            amount_xtr=stars_amount,
            invoice_payload=f"fday-{uuid.uuid4()}",
            invoice_link=invoice_link,
            status="pending",
        )
        session.add(order)
        await session.commit()
        return {
            "ok": True,
            "kind": "freeze_day",
            "amount_xtr": stars_amount,
            "invoice_link": invoice_link,
            "order_id": order.id,
        }

    # freeze_week: 7-day protection interval starting tomorrow .. +30 days
    start_str = payload.start_date or (today_dt + timedelta(days=1)).isoformat()
    try:
        start_dt = date.fromisoformat(start_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid start_date") from exc

    days_ahead = (start_dt - today_dt).days
    if days_ahead < 1 or days_ahead > 30:
        raise HTTPException(
            status_code=400,
            detail="7-day protection must start between tomorrow and 30 days ahead.",
        )

    existing_pi = (
        await session.execute(
            select(ProtectionInterval).where(
                ProtectionInterval.owner_id == user.id,
                ProtectionInterval.status.in_(("pending", "active")),
            )
        )
    ).scalar_one_or_none()
    if existing_pi is not None:
        raise HTTPException(
            status_code=400,
            detail="You already have an active or scheduled 7-day protection interval.",
        )

    if len(protected_30d) > 0:
        raise HTTPException(
            status_code=400,
            detail="7-day week protection requires 7 available days within the 30-day protection cap.",
        )

    end_str = (start_dt + timedelta(days=7)).isoformat()
    stars_amount = settings.freeze_week_price_xtr
    inv_payload = f'{{"kind":"freeze_week","start_date":"{start_str}","end_date":"{end_str}"}}'
    inv_resp = await tg_client.create_invoice_link(
        title="BrainRecall — 7-Day Pause",
        description=f"Streak protection from {start_str} to {end_str}",
        payload=inv_payload,
        stars_amount=stars_amount,
    )
    invoice_link = inv_resp.get("result")

    order = PaymentOrder(
        owner_id=user.id,
        telegram_user_id=user.telegram_id,
        product_type="freeze_week",
        amount_xtr=stars_amount,
        week_start_date=start_str,
        invoice_payload=f"fweek-{uuid.uuid4()}",
        invoice_link=invoice_link,
        status="pending",
    )
    session.add(order)
    await session.commit()
    return {
        "ok": True,
        "kind": "freeze_week",
        "start_date": start_str,
        "end_date_exclusive": end_str,
        "amount_xtr": stars_amount,
        "invoice_link": invoice_link,
        "order_id": order.id,
    }
