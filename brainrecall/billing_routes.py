"""Telegram Stars billing, subscriptions (Start 499 XTR / Pro 1099 XTR), cancel/refund, and Free downgrade active-set selection (D27-D29, Dev Spec v1.14 Section 10)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from brainrecall.analytics import analytics
from brainrecall.config import PLAN_LIMITS, settings
from brainrecall.db import get_session
from brainrecall.materials_ai_routes import ensure_or_get_entitlement
from brainrecall.models import (
    Entitlement,
    Habit,
    KnowledgeItem,
    PaymentOrder,
    Topic,
    User,
)
from brainrecall.security import get_current_user
from brainrecall.telegram_api import tg_client

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


class SubscribeRequest(BaseModel):
    plan_code: str = Field(..., pattern="^(start|pro)$")
    confirm_immediately_in_dev: bool = False


class ChangePlanRequest(BaseModel):
    desired_next_plan: str = Field(..., pattern="^(start|pro|free)$")


class RefundRequest(BaseModel):
    order_id: str | None = None
    reason: str = Field(default="", max_length=500)


class SelectActiveSetRequest(BaseModel):
    active_topic_ids: list[str] = Field(default_factory=list, max_length=3)
    active_habit_ids: list[str] = Field(default_factory=list, max_length=3)


async def _check_downgrade_selection_needed(
    session: AsyncSession,
    user: User,
    ent: Entitlement,
) -> tuple[bool, int, int]:
    active_topics_res = await session.execute(
        select(func.count(Topic.id)).where(
            Topic.owner_id == user.id,
            Topic.status == "active",
        )
    )
    active_habits_res = await session.execute(
        select(func.count(Habit.id)).where(
            Habit.owner_id == user.id,
            Habit.status == "active",
        )
    )
    active_topics = int(active_topics_res.scalar() or 0)
    active_habits = int(active_habits_res.scalar() or 0)

    free_limits = PLAN_LIMITS["free"]
    needs_selection = ent.plan_code == "free" and (
        active_topics > free_limits["topics"] or active_habits > free_limits["habits"]
    )
    if needs_selection != ent.downgrade_selection_required:
        ent.downgrade_selection_required = needs_selection
        await session.flush()

    return needs_selection, active_topics, active_habits


def _serialize_entitlement(ent: Entitlement, active_topics: int, active_habits: int, total_items: int) -> dict[str, Any]:
    plan_limits = PLAN_LIMITS.get(ent.plan_code, PLAN_LIMITS["free"])
    return {
        "plan_code": ent.plan_code,
        "status": ent.status,
        "trial_used": ent.trial_used,
        "trial_eligible": (not ent.trial_used) and ent.plan_code == "free",
        "period_id": ent.period_id,
        "period_start": ent.period_start.isoformat() if ent.period_start else None,
        "period_end": ent.period_end.isoformat() if ent.period_end else None,
        "auto_renew": ent.auto_renew,
        "desired_next_plan": ent.desired_next_plan,
        "downgrade_selection_required": ent.downgrade_selection_required,
        "usage": {
            "active_topics": active_topics,
            "topics_limit": plan_limits["topics"],
            "active_habits": active_habits,
            "habits_limit": plan_limits["habits"],
            "total_items": total_items,
            "items_limit": plan_limits["items"],
            "import_tokens": {
                "used": ent.import_tokens_used,
                "reserved": ent.import_tokens_reserved,
                "limit": ent.import_tokens_limit,
                "remaining": max(0, ent.import_tokens_limit - ent.import_tokens_used - ent.import_tokens_reserved),
            },
            "ai_checks": {
                "used": ent.ai_checks_used,
                "reserved": ent.ai_checks_reserved,
                "limit": ent.ai_checks_limit,
                "remaining": max(0, ent.ai_checks_limit - ent.ai_checks_used - ent.ai_checks_reserved),
            },
            "ai_cases": {
                "used": ent.ai_cases_used,
                "reserved": ent.ai_cases_reserved,
                "limit": ent.ai_cases_limit,
                "remaining": max(0, ent.ai_cases_limit - ent.ai_cases_used - ent.ai_cases_reserved),
            },
            "ai_plans": {
                "used": ent.ai_plans_used,
                "reserved": ent.ai_plans_reserved,
                "limit": ent.ai_plans_limit,
                "remaining": max(0, ent.ai_plans_limit - ent.ai_plans_used - ent.ai_plans_reserved),
            },
            "ai_reviews": {
                "used": ent.ai_reviews_used,
                "reserved": ent.ai_reviews_reserved,
                "limit": ent.ai_reviews_limit,
                "remaining": max(0, ent.ai_reviews_limit - ent.ai_reviews_used - ent.ai_reviews_reserved),
            },
        },
    }


@router.get("/plans")
async def get_plans_and_entitlement_d27(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """D27: Returns all plans (Free, Trial, Start 499 XTR, Pro 1099 XTR) and current user entitlement & quotas."""
    ent = await ensure_or_get_entitlement(session, user)
    _, active_topics, active_habits = await _check_downgrade_selection_needed(session, user, ent)

    items_res = await session.execute(
        select(func.count(KnowledgeItem.id)).where(
            KnowledgeItem.owner_id == user.id,
            KnowledgeItem.status != "archived",
        )
    )
    total_items = int(items_res.scalar() or 0)

    orders_res = await session.execute(
        select(PaymentOrder)
        .where(PaymentOrder.owner_id == user.id)
        .order_by(PaymentOrder.created_at.desc())
        .limit(10)
    )
    orders = [
        {
            "id": o.id,
            "product_type": o.product_type,
            "plan_code": o.plan_code,
            "amount_xtr": o.amount_xtr,
            "status": o.status,
            "created_at": o.created_at.isoformat(),
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        }
        for o in orders_res.scalars().all()
    ]

    await session.commit()
    return {
        "entitlement": _serialize_entitlement(ent, active_topics, active_habits, total_items),
        "plans": {
            "free": PLAN_LIMITS["free"],
            "trial": PLAN_LIMITS["trial"],
            "start": PLAN_LIMITS["start"],
            "pro": PLAN_LIMITS["pro"],
        },
        "orders": orders,
        "support_contact": settings.support_contact,
    }


@router.post("/subscribe")
async def subscribe_plan_d28(
    payload: SubscribeRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    D28: Creates a Telegram Stars subscription invoice link (`subscription_period=2592000`, 30 days)
    for Start (499 XTR) or Pro (1099 XTR).
    In development/test mode or when `confirm_immediately_in_dev=True`, can also activate immediately.
    """
    plan_code = payload.plan_code
    limits = PLAN_LIMITS[plan_code]
    amount_xtr = int(limits["price_xtr"])
    sub_period = int(limits.get("subscription_period") or 2_592_000)

    inv_payload = json.dumps({"kind": "subscription", "plan": plan_code, "uid": user.id})
    title = f"BrainRecall {plan_code.capitalize()} (30d)"
    desc = f"BrainRecall {plan_code.capitalize()} — {limits['import_tokens']:,} AI import tokens, {limits['topics']} topics, {limits['habits']} habits"

    inv_resp = await tg_client.create_invoice_link(
        title=title,
        description=desc,
        payload=inv_payload,
        stars_amount=amount_xtr,
        subscription_period=sub_period,
    )
    invoice_link = inv_resp.get("result")

    now = datetime.now(timezone.utc)
    order = PaymentOrder(
        owner_id=user.id,
        telegram_user_id=user.telegram_id,
        product_type=f"plan_{plan_code}",
        plan_code=plan_code,
        amount_xtr=amount_xtr,
        currency="XTR",
        is_recurring=True,
        invoice_payload=f"sub-{plan_code}-{uuid.uuid4()}",
        invoice_link=invoice_link,
        status="pending",
    )
    session.add(order)
    await session.flush()

    ent = await ensure_or_get_entitlement(session, user)
    if payload.confirm_immediately_in_dev and settings.app_env != "production":
        charge_id = f"dev-charge-{uuid.uuid4().hex[:12]}"
        order.status = "paid"
        order.paid_at = now
        order.telegram_payment_charge_id = charge_id
        await _activate_paid_subscription(session, user, ent, plan_code, charge_id, now)

    await analytics.track(
        session,
        event_name="subscription_checkout_created",
        user=user,
        properties={"plan_code": plan_code, "amount_xtr": amount_xtr, "order_id": order.id},
    )
    await session.commit()
    return {
        "ok": True,
        "order_id": order.id,
        "plan_code": plan_code,
        "amount_xtr": amount_xtr,
        "subscription_period": sub_period,
        "invoice_link": invoice_link,
        "status": order.status,
    }


async def _activate_paid_subscription(
    session: AsyncSession,
    user: User,
    ent: Entitlement,
    plan_code: str,
    charge_id: str,
    now: datetime,
) -> None:
    limits = PLAN_LIMITS[plan_code]
    ent.plan_code = plan_code
    ent.status = "active"
    ent.period_id = f"{plan_code}-{int(now.timestamp())}"
    ent.period_start = now
    ent.period_end = now + timedelta(days=30)
    ent.auto_renew = True
    ent.desired_next_plan = None
    ent.telegram_charge_id = charge_id
    ent.downgrade_selection_required = False

    ent.import_tokens_limit = limits["import_tokens"]
    ent.import_tokens_used = 0
    ent.import_tokens_reserved = 0
    ent.ai_checks_limit = limits["ai_checks"]
    ent.ai_checks_used = 0
    ent.ai_checks_reserved = 0
    ent.ai_cases_limit = limits["ai_cases"]
    ent.ai_cases_used = 0
    ent.ai_cases_reserved = 0
    ent.ai_plans_limit = limits["ai_plans"]
    ent.ai_plans_used = 0
    ent.ai_plans_reserved = 0
    ent.ai_reviews_limit = limits["ai_reviews"]
    ent.ai_reviews_used = 0
    ent.ai_reviews_reserved = 0

    # Re-activate any readonly topics/habits up to the new plan's limit
    ro_topics = (
        await session.execute(
            select(Topic).where(Topic.owner_id == user.id, Topic.status == "readonly")
        )
    ).scalars().all()
    for t_obj in ro_topics:
        t_obj.status = "active"

    ro_habits = (
        await session.execute(
            select(Habit).where(Habit.owner_id == user.id, Habit.status == "readonly")
        )
    ).scalars().all()
    for h_obj in ro_habits:
        h_obj.status = "active"

    await session.flush()


@router.post("/cancel")
async def cancel_subscription_d28(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    D28: Cancels auto-renewal via `editUserStarSubscription(is_canceled=True)` while keeping
    current plan entitlements active until `period_end` (Section 10.2).
    """
    ent = await ensure_or_get_entitlement(session, user)
    if ent.plan_code not in ("start", "pro"):
        raise HTTPException(status_code=400, detail="No active paid subscription to cancel.")

    if ent.telegram_charge_id:
        await tg_client.edit_user_star_subscription(
            user_id=user.telegram_id,
            telegram_payment_charge_id=ent.telegram_charge_id,
            is_canceled=True,
        )

    ent.auto_renew = False
    ent.desired_next_plan = "free"
    await analytics.track(
        session,
        event_name="subscription_auto_renew_cancelled",
        user=user,
        properties={"plan_code": ent.plan_code, "period_end": ent.period_end.isoformat() if ent.period_end else None},
    )
    await session.commit()
    return {
        "ok": True,
        "plan_code": ent.plan_code,
        "auto_renew": ent.auto_renew,
        "period_end": ent.period_end.isoformat() if ent.period_end else None,
    }


@router.post("/change-plan")
async def schedule_plan_change_d28(
    payload: ChangePlanRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """D28: Records `desired_next_plan` for the next billing cycle."""
    ent = await ensure_or_get_entitlement(session, user)
    ent.desired_next_plan = payload.desired_next_plan
    await session.commit()
    return {
        "ok": True,
        "plan_code": ent.plan_code,
        "desired_next_plan": ent.desired_next_plan,
    }


@router.post("/refund")
async def request_refund_d28(
    payload: RefundRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    D28: Refunds a Telegram Stars payment via `refundStarPayment` if 0 AI quota was used in the current period,
    reverting the user's entitlement to `free` and triggering `D29` active-set selection if >3 topics/habits exist.
    """
    ent = await ensure_or_get_entitlement(session, user)
    total_ai_used = (
        ent.import_tokens_used
        + ent.ai_checks_used
        + ent.ai_cases_used
        + ent.ai_plans_used
        + ent.ai_reviews_used
    )
    if total_ai_used > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "REFUND_QUOTA_ALREADY_USED",
                "message": "Automatic refund requires 0 used AI quota in the current billing period. Please contact /paysupport.",
            },
        )

    order_stmt = select(PaymentOrder).where(
        PaymentOrder.owner_id == user.id,
        PaymentOrder.status == "paid",
    )
    if payload.order_id:
        order_stmt = order_stmt.where(PaymentOrder.id == payload.order_id)
    order_stmt = order_stmt.order_by(PaymentOrder.paid_at.desc()).limit(1)
    order = (await session.execute(order_stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="No eligible paid order found for refund.")

    if order.telegram_payment_charge_id:
        await tg_client.refund_star_payment(
            user_id=user.telegram_id,
            telegram_payment_charge_id=order.telegram_payment_charge_id,
        )

    now = datetime.now(timezone.utc)
    order.status = "refunded"
    order.refunded_at = now

    ent.plan_code = "free"
    ent.status = "active"
    ent.auto_renew = False
    ent.period_end = None
    ent.import_tokens_limit = 0
    ent.ai_checks_limit = 0
    ent.ai_cases_limit = 0
    ent.ai_plans_limit = 0
    ent.ai_reviews_limit = 0

    needs_sel, active_topics, active_habits = await _check_downgrade_selection_needed(session, user, ent)
    await session.commit()
    return {
        "ok": True,
        "refunded_order_id": order.id,
        "plan_code": ent.plan_code,
        "downgrade_selection_required": needs_sel,
        "active_topics": active_topics,
        "active_habits": active_habits,
    }


@router.get("/downgrade-options")
async def get_downgrade_options_d29(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """D29: Lists all user topics and habits so they can choose up to 3 active topics and 3 active habits on Free."""
    topics_res = await session.execute(
        select(Topic)
        .where(Topic.owner_id == user.id, Topic.status.in_(("active", "readonly")))
        .order_by(Topic.created_at.asc())
    )
    habits_res = await session.execute(
        select(Habit)
        .where(Habit.owner_id == user.id, Habit.status.in_(("active", "readonly")))
        .order_by(Habit.created_at.asc())
    )
    topics = [
        {"id": t_obj.id, "title": t_obj.title, "goal": t_obj.goal, "status": t_obj.status}
        for t_obj in topics_res.scalars().all()
    ]
    habits = [
        {"id": h_obj.id, "title": h_obj.title, "status": h_obj.status}
        for h_obj in habits_res.scalars().all()
    ]
    return {
        "max_active_topics": PLAN_LIMITS["free"]["topics"],
        "max_active_habits": PLAN_LIMITS["free"]["habits"],
        "topics": topics,
        "habits": habits,
    }


@router.post("/select-active-set")
async def select_active_set_on_free_d29(
    payload: SelectActiveSetRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    D29: Applies user's choice of up to 3 active topics and 3 active habits after downgrade/expiry to Free.
    Remaining topics and habits transition to `readonly` (still viewable and exportable, never deleted).
    """
    max_t = PLAN_LIMITS["free"]["topics"]
    max_h = PLAN_LIMITS["free"]["habits"]
    if len(payload.active_topic_ids) > max_t or len(payload.active_habit_ids) > max_h:
        raise HTTPException(
            status_code=400,
            detail=f"Free plan allows at most {max_t} active topics and {max_h} active habits.",
        )

    keep_topics = set(payload.active_topic_ids)
    keep_habits = set(payload.active_habit_ids)

    topics_res = await session.execute(
        select(Topic).where(Topic.owner_id == user.id, Topic.status.in_(("active", "readonly")))
    )
    all_topics = list(topics_res.scalars().all())
    for idx, t_obj in enumerate(all_topics):
        if keep_topics:
            t_obj.status = "active" if t_obj.id in keep_topics else "readonly"
        else:
            t_obj.status = "active" if idx < max_t else "readonly"

    habits_res = await session.execute(
        select(Habit).where(Habit.owner_id == user.id, Habit.status.in_(("active", "readonly")))
    )
    all_habits = list(habits_res.scalars().all())
    for idx, h_obj in enumerate(all_habits):
        if keep_habits:
            h_obj.status = "active" if h_obj.id in keep_habits else "readonly"
        else:
            h_obj.status = "active" if idx < max_h else "readonly"

    ent = await ensure_or_get_entitlement(session, user)
    ent.downgrade_selection_required = False
    await session.commit()

    return {
        "ok": True,
        "active_topics_count": sum(1 for t_obj in all_topics if t_obj.status == "active"),
        "readonly_topics_count": sum(1 for t_obj in all_topics if t_obj.status == "readonly"),
        "active_habits_count": sum(1 for h_obj in all_habits if h_obj.status == "active"),
        "readonly_habits_count": sum(1 for h_obj in all_habits if h_obj.status == "readonly"),
    }
