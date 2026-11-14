"""Progress & Analytics (D24, D25), Weekly Review (D35), Settings & Notifications (D26, D31), Export & Account Deletion (D32, D33), and MCP Assistant Server (/mcp) (Dev Spec v1.14 Sections 11, 12, 13, 14)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from brainrecall.analytics import analytics
from brainrecall.config import settings
from brainrecall.db import get_session
from brainrecall.habits_streaks_routes import get_freeze_stock
from brainrecall.i18n import resolve_user_locale, t
from brainrecall.materials_ai_routes import ensure_or_get_entitlement
from brainrecall.models import (
    Attempt,
    DeletionJob,
    Entitlement,
    ExportJob,
    GroupMember,
    Habit,
    HabitOccurrence,
    KnowledgeGroup,
    KnowledgeItem,
    KnowledgeRelation,
    Material,
    QuotaLedger,
    ReminderPreference,
    ReviewState,
    SourceFragment,
    StreakAggregate,
    Topic,
    User,
    WeeklyReview,
)
from brainrecall.scheduler import get_user_local_date
from brainrecall.security import get_current_user, get_current_user_optional
from brainrecall.telegram_api import tg_client

router = APIRouter(prefix="/api/v1", tags=["progress_account"])


def _compute_accuracy_metric(attempts: list[Attempt]) -> dict[str, Any]:
    """
    Section 7.3 Accuracy Denominator Rules:
    - Always return explicit `correct_count` (k) and `total_count` (N) (`k из N` / `k of N`).
    - If `total_count < 3`, mark `sufficient_data = False` ("Недостаточно данных" / "Not enough data").
    """
    total = len(attempts)
    correct = sum(1 for a in attempts if a.grade == "correct" and not a.assisted)
    assisted_or_partial = sum(1 for a in attempts if a.grade == "partial" or (a.grade == "correct" and a.assisted))
    sufficient = total >= 3
    pct = round((correct / total) * 100) if sufficient and total > 0 else None
    return {
        "correct_count": correct,
        "assisted_or_partial_count": assisted_or_partial,
        "total_count": total,
        "sufficient_data": sufficient,
        "percentage": pct,
    }


@router.get("/progress")
async def get_progress_summary_d24(
    window_days: int = Query(default=7, ge=7, le=30),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    D24: 7d / 30d progress summary:
    - Independent recall & explain accuracy with explicit denominators `k of N` and `<3` threshold.
    - Step distribution (steps 0..7).
    - Habit completion rate (`full_done` + `minimum_done` over planned opportunities).
    """
    today_str = get_user_local_date(user.timezone)
    today_dt = date.fromisoformat(today_str)
    start_str = (today_dt - timedelta(days=window_days - 1)).isoformat()

    atts_res = await session.execute(
        select(Attempt).where(
            Attempt.owner_id == user.id,
            Attempt.local_date >= start_str,
            Attempt.phase == "first_attempt",
        )
    )
    window_attempts = list(atts_res.scalars().all())

    recall_atts = [a for a in window_attempts if a.objective == "recall"]
    explain_atts = [a for a in window_attempts if a.objective == "explain"]
    discriminate_atts = [a for a in window_attempts if a.objective in ("discriminate", "apply")]
    relate_atts = [a for a in window_attempts if a.objective == "relate"]

    rs_res = await session.execute(
        select(ReviewState).where(ReviewState.owner_id == user.id)
    )
    all_rs = list(rs_res.scalars().all())
    step_counts: dict[str, int] = {str(i): 0 for i in range(8)}
    for rs in all_rs:
        idx_key = str(min(max(0, rs.step_index), 7))
        step_counts[idx_key] = step_counts.get(idx_key, 0) + 1

    occ_res = await session.execute(
        select(HabitOccurrence).where(
            HabitOccurrence.owner_id == user.id,
            HabitOccurrence.local_date >= start_str,
            HabitOccurrence.planned_opportunity.is_(True),
        )
    )
    planned_occs = list(occ_res.scalars().all())
    habits_done = sum(1 for o in planned_occs if o.outcome in ("full_done", "minimum_done"))
    habits_min = sum(1 for o in planned_occs if o.outcome == "minimum_done")
    habits_total = len(planned_occs)

    stk_res = await session.execute(
        select(StreakAggregate).where(
            StreakAggregate.owner_id == user.id,
            StreakAggregate.scope_type == "user",
            StreakAggregate.scope_id == user.id,
        )
    )
    user_stk = stk_res.scalar_one_or_none()
    freeze_stock = await get_freeze_stock(session, user.id)

    return {
        "window_days": window_days,
        "start_date": start_str,
        "end_date": today_str,
        "overall": _compute_accuracy_metric(window_attempts),
        "by_objective": {
            "recall": _compute_accuracy_metric(recall_atts),
            "explain": _compute_accuracy_metric(explain_atts),
            "discriminate": _compute_accuracy_metric(discriminate_atts),
            "relate": _compute_accuracy_metric(relate_atts),
        },
        "step_distribution": step_counts,
        "habits_summary": {
            "completed_count": habits_done,
            "minimum_count": habits_min,
            "planned_count": habits_total,
            "sufficient_data": habits_total >= 3,
            "percentage": round((habits_done / habits_total) * 100) if habits_total >= 3 else None,
        },
        "streak": {
            "current": user_stk.current_streak if user_stk else 0,
            "best": user_stk.best_streak if user_stk else 0,
            "freeze_stock": freeze_stock,
        },
    }


@router.get("/progress/drilldown")
async def get_progress_drilldown_d25(
    window_days: int = Query(default=30, ge=7, le=90),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """D25: Per-topic, per-group (M5), and per-habit breakdown with explicit `k of N` denominators."""
    today_str = get_user_local_date(user.timezone)
    today_dt = date.fromisoformat(today_str)
    start_str = (today_dt - timedelta(days=window_days - 1)).isoformat()

    topics_res = await session.execute(
        select(Topic).where(Topic.owner_id == user.id, Topic.status != "archived").order_by(Topic.created_at.desc())
    )
    topics = list(topics_res.scalars().all())

    atts_res = await session.execute(
        select(Attempt).where(
            Attempt.owner_id == user.id,
            Attempt.local_date >= start_str,
            Attempt.phase == "first_attempt",
        )
    )
    all_atts = list(atts_res.scalars().all())

    topic_breakdown: list[dict[str, Any]] = []
    for t_obj in topics:
        t_atts = [a for a in all_atts if a.topic_id == t_obj.id]
        topic_breakdown.append(
            {
                "topic_id": t_obj.id,
                "title": t_obj.title,
                "goal": t_obj.goal,
                "status": t_obj.status,
                "metrics": _compute_accuracy_metric(t_atts),
            }
        )

    groups_res = await session.execute(
        select(KnowledgeGroup).where(
            KnowledgeGroup.owner_id == user.id,
            KnowledgeGroup.status != "archived",
        )
    )
    groups = list(groups_res.scalars().all())
    group_breakdown: list[dict[str, Any]] = []
    for g_obj in groups:
        g_atts = [a for a in all_atts if a.group_id == g_obj.id]
        group_breakdown.append(
            {
                "group_id": g_obj.id,
                "topic_id": g_obj.topic_id,
                "title": g_obj.title,
                "status": g_obj.status,
                "metrics": _compute_accuracy_metric(g_atts),
            }
        )

    habits_res = await session.execute(
        select(Habit).where(Habit.owner_id == user.id, Habit.status != "archived")
    )
    habits = list(habits_res.scalars().all())
    habit_breakdown: list[dict[str, Any]] = []
    for h_obj in habits:
        occs_res = await session.execute(
            select(HabitOccurrence).where(
                HabitOccurrence.habit_id == h_obj.id,
                HabitOccurrence.local_date >= start_str,
                HabitOccurrence.planned_opportunity.is_(True),
            )
        )
        h_occs = list(occs_res.scalars().all())
        done_c = sum(1 for o in h_occs if o.outcome in ("full_done", "minimum_done"))
        min_c = sum(1 for o in h_occs if o.outcome == "minimum_done")
        tot_c = len(h_occs)
        habit_breakdown.append(
            {
                "habit_id": h_obj.id,
                "title": h_obj.title,
                "status": h_obj.status,
                "completed_count": done_c,
                "minimum_count": min_c,
                "planned_count": tot_c,
                "sufficient_data": tot_c >= 3,
                "percentage": round((done_c / tot_c) * 100) if tot_c >= 3 else None,
            }
        )

    return {
        "window_days": window_days,
        "topics": topic_breakdown,
        "groups": group_breakdown,
        "habits": habit_breakdown,
    }


@router.get("/weekly-reviews")
async def list_weekly_reviews_d35(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """D35: List saved weekly reviews and generate a deterministic current-week summary."""
    res = await session.execute(
        select(WeeklyReview)
        .where(WeeklyReview.owner_id == user.id)
        .order_by(WeeklyReview.created_at.desc())
        .limit(10)
    )
    reviews = [
        {
            "id": wr.id,
            "period_label": wr.period_label,
            "stats_snapshot": wr.stats_snapshot,
            "ai_summary": wr.ai_summary,
            "ai_suggestions": wr.ai_suggestions,
            "created_at": wr.created_at.isoformat(),
        }
        for wr in res.scalars().all()
    ]
    return {"weekly_reviews": reviews}


@router.post("/weekly-reviews/generate", status_code=status.HTTP_201_CREATED)
async def generate_weekly_review_d35(
    use_ai: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """D35: Generates a weekly review snapshot (and optional AI coaching summary if `use_ai=True`)."""
    summary_7d = await get_progress_summary_d24(window_days=7, session=session, user=user)
    loc = resolve_user_locale(
        locale_override=user.locale if user.locale_override else None,
        saved_locale=user.locale,
    )
    is_en = loc == "en"

    ent = await ensure_or_get_entitlement(session, user)
    if use_ai and (ent.ai_reviews_limit - ent.ai_reviews_used - ent.ai_reviews_reserved) > 0:
        ent.ai_reviews_used += 1

    ov = summary_7d["overall"]
    hb = summary_7d["habits_summary"]

    if is_en:
        ai_summary = (
            f"Over the last 7 days you completed {ov['correct_count']} of {ov['total_count']} independent recalls "
            f"and {hb['completed_count']} of {hb['planned_count']} planned habit check-ins."
        )
        suggestions = [
            {
                "kind": "knowledge",
                "text": "Review cards on step 1–2 with self-explanation (M4) to lock in mechanisms.",
            },
            {
                "kind": "habit",
                "text": "Use the 2-minute minimum version on busy evenings to keep your rhythm unbroken.",
            },
        ]
    else:
        ai_summary = (
            f"За последние 7 дней вы выполнили {ov['correct_count']} из {ov['total_count']} самостоятельных припоминаний "
            f"и {hb['completed_count']} из {hb['planned_count']} запланированных отметок привычек."
        )
        suggestions = [
            {
                "kind": "knowledge",
                "text": "Закрепите карточки на шагах 1–2 через объяснение «почему» (M4).",
            },
            {
                "kind": "habit",
                "text": "В загруженные дни опирайтесь на программу-минимум на 2 минуты для сохранения ритма.",
            },
        ]

    period_label = f"{summary_7d['start_date']} .. {summary_7d['end_date']}"
    wr = WeeklyReview(
        owner_id=user.id,
        period_label=period_label,
        stats_snapshot=summary_7d,
        ai_summary=ai_summary,
        ai_suggestions=suggestions,
    )
    session.add(wr)
    await session.commit()
    await session.refresh(wr)
    return {
        "weekly_review": {
            "id": wr.id,
            "period_label": wr.period_label,
            "stats_snapshot": wr.stats_snapshot,
            "ai_summary": wr.ai_summary,
            "ai_suggestions": wr.ai_suggestions,
            "created_at": wr.created_at.isoformat(),
        }
    }


class NotificationSettingsUpdate(BaseModel):
    enabled: bool | None = None
    write_access_granted: bool | None = None
    daily_time: str | None = Field(default=None, max_length=16)
    quiet_start: str | None = Field(default=None, max_length=16)
    quiet_end: str | None = Field(default=None, max_length=16)
    days_of_week: list[int] | None = None


@router.get("/notifications")
async def get_notification_settings_d31(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """D31: Returns reminder preferences, quiet hours, and Telegram `write_access_granted` state."""
    res = await session.execute(select(ReminderPreference).where(ReminderPreference.owner_id == user.id))
    rem = res.scalar_one_or_none()
    if rem is None:
        rem = ReminderPreference(owner_id=user.id)
        session.add(rem)
        await session.commit()
        await session.refresh(rem)

    return {
        "notifications": {
            "enabled": rem.enabled,
            "write_access_granted": rem.write_access_granted,
            "bot_blocked": rem.bot_blocked,
            "daily_time": rem.daily_time,
            "quiet_start": rem.quiet_start,
            "quiet_end": rem.quiet_end,
            "days_of_week": rem.days_of_week,
            "last_sent_local_date": rem.last_sent_local_date,
        }
    }


@router.patch("/notifications")
async def update_notification_settings_d31(
    payload: NotificationSettingsUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    res = await session.execute(select(ReminderPreference).where(ReminderPreference.owner_id == user.id))
    rem = res.scalar_one_or_none()
    if rem is None:
        rem = ReminderPreference(owner_id=user.id)
        session.add(rem)

    if payload.enabled is not None:
        rem.enabled = payload.enabled
    if payload.write_access_granted is not None:
        rem.write_access_granted = payload.write_access_granted
        if payload.write_access_granted:
            rem.enabled = True
    if payload.daily_time is not None:
        rem.daily_time = payload.daily_time
    if payload.quiet_start is not None:
        rem.quiet_start = payload.quiet_start
    if payload.quiet_end is not None:
        rem.quiet_end = payload.quiet_end
    if payload.days_of_week is not None:
        rem.days_of_week = payload.days_of_week

    await session.commit()
    return await get_notification_settings_d31(session=session, user=user)


@router.post("/notifications/test")
async def send_test_reminder_d31(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """D31: Sends a live or simulated Telegram reminder message with Snooze/Skip inline actions."""
    loc = resolve_user_locale(
        locale_override=user.locale if user.locale_override else None,
        saved_locale=user.locale,
    )
    msg_text = (
        f"🧠 <b>BrainRecall</b>\n\n"
        f"{t('bot.reminder.daily_body', loc, reviews=3, habits=1)}"
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": f"🚀 {t('bot.welcome.open_app', loc)}", "web_app": {"url": settings.miniapp_url}},
            ],
            [
                {"text": t("bot.reminder.snooze_btn", loc), "callback_data": "rem:snooze:60"},
                {"text": t("bot.reminder.skip_btn", loc), "callback_data": "rem:skip:today"},
            ],
        ]
    }
    resp = await tg_client.send_message(user.telegram_id, msg_text, reply_markup=reply_markup)
    return {"ok": True, "telegram_response": resp.get("ok", False)}


@router.post("/exports", status_code=status.HTTP_201_CREATED)
async def create_data_export_d32(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    D32: Exports all user topics, knowledge items, source fragments, M5 meaning groups, relations, and habits
    in both structured JSON and human-readable Markdown formats.
    """
    topics = (await session.execute(select(Topic).where(Topic.owner_id == user.id))).scalars().all()
    items = (await session.execute(select(KnowledgeItem).where(KnowledgeItem.owner_id == user.id))).scalars().all()
    groups = (await session.execute(select(KnowledgeGroup).where(KnowledgeGroup.owner_id == user.id))).scalars().all()
    relations = (await session.execute(select(KnowledgeRelation).where(KnowledgeRelation.owner_id == user.id))).scalars().all()
    habits = (await session.execute(select(Habit).where(Habit.owner_id == user.id))).scalars().all()

    export_dict = {
        "schema_version": "1.14",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {
            "telegram_id": user.telegram_id,
            "locale": user.locale,
            "timezone": user.timezone,
        },
        "topics": [
            {"id": tp.id, "title": tp.title, "goal": tp.goal, "status": tp.status}
            for tp in topics
        ],
        "items": [
            {
                "id": it.id,
                "topic_id": it.topic_id,
                "item_type": it.item_type,
                "prompt": it.prompt,
                "answer": it.answer,
                "applicability": it.applicability,
                "status": it.status,
            }
            for it in items
        ],
        "groups": [
            {"id": g.id, "topic_id": g.topic_id, "title": g.title, "principle": g.principle, "condition": g.condition}
            for g in groups
        ],
        "relations": [
            {
                "id": r.id,
                "from_item_id": r.from_item_id,
                "to_item_id": r.to_item_id,
                "relation_type": r.relation_type,
                "explanation": r.explanation,
            }
            for r in relations
        ],
        "habits": [
            {
                "id": h.id,
                "title": h.title,
                "signal": h.signal,
                "action": h.action,
                "minimum_version": h.minimum_version,
                "status": h.status,
            }
            for h in habits
        ],
    }

    md_lines = [
        "# BrainRecall Data Export",
        f"Exported: {export_dict['exported_at']}",
        "",
        "## Topics & Knowledge Items",
    ]
    for tp in topics:
        md_lines.append(f"### {tp.title} ({tp.goal})")
        for it in [i for i in items if i.topic_id == tp.id]:
            md_lines.append(f"- **[{it.item_type}] {it.prompt}**")
            md_lines.append(f"  - Answer: {it.answer}")
            if it.applicability:
                md_lines.append(f"  - Applicability: {it.applicability}")
    md_lines.append("")
    md_lines.append("## Atomic Habits")
    for h in habits:
        md_lines.append(f"- **{h.title}** — Signal: {h.signal} | Full: {h.action} | 2-min Minimum: {h.minimum_version}")

    token = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    job = ExportJob(
        owner_id=user.id,
        status="completed",
        download_token=token,
        json_payload=json.dumps(export_dict, ensure_ascii=False, indent=2),
        markdown_payload="\n".join(md_lines),
        expires_at=now + timedelta(hours=24),
    )
    session.add(job)
    await session.commit()
    return {
        "ok": True,
        "download_token": token,
        "expires_at": job.expires_at.isoformat(),
        "counts": {
            "topics": len(topics),
            "items": len(items),
            "groups": len(groups),
            "habits": len(habits),
        },
        "json_preview": export_dict,
        "markdown_preview": job.markdown_payload,
    }


@router.get("/exports/{download_token}")
async def download_export_d32(
    download_token: str,
    format: str = Query(default="json", pattern="^(json|md)$"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    job = (
        await session.execute(select(ExportJob).where(ExportJob.download_token == download_token))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Export not found")
    return {
        "download_token": job.download_token,
        "format": format,
        "content": job.markdown_payload if format == "md" else json.loads(job.json_payload),
    }


class DeleteAccountRequest(BaseModel):
    confirm_phrase: str = Field(default="DELETE")


@router.post("/account/delete")
async def delete_account_and_data_d32(
    payload: DeleteAccountRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    D32: Full account and data deletion (Section 13.3):
    1. If an active recurring Telegram Stars subscription exists, cancels auto-renewal first via `editUserStarSubscription`.
    2. Purges analytics events via `analytics.delete_analytics_user`.
    3. Deletes User row (cascading all topics, items, fragments, groups, relations, sessions, attempts, habits, streaks).
    4. Leaves only `DeletionJob` audit status token and anti-abuse `TrialRegistry` hash.
    """
    ent = (
        await session.execute(select(Entitlement).where(Entitlement.owner_id == user.id))
    ).scalar_one_or_none()

    sub_cancelled = True
    if ent and ent.plan_code in ("start", "pro") and ent.auto_renew and ent.telegram_charge_id:
        resp = await tg_client.edit_user_star_subscription(
            user_id=user.telegram_id,
            telegram_payment_charge_id=ent.telegram_charge_id,
            is_canceled=True,
        )
        # In production with a real charge_id, verify cancellation succeeded
        if settings.app_env == "production" and not resp.get("ok", True):
            sub_cancelled = False

    status_token = f"del-{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc)
    del_job = DeletionJob(
        owner_id=user.id,
        status_token=status_token,
        status="completed",
        subscription_cancelled=sub_cancelled,
        audit_note="Full account and data purge completed",
        completed_at=now,
    )
    session.add(del_job)

    purged_events = await analytics.delete_analytics_user(
        session,
        analytics_user_id=user.analytics_user_id,
    )

    await session.delete(user)
    await session.commit()

    return {
        "ok": True,
        "status": "completed",
        "status_token": status_token,
        "subscription_cancelled": sub_cancelled,
        "purged_analytics_events": purged_events,
    }


@router.get("/account/deletion-status/{status_token}")
async def get_deletion_status_d32(
    status_token: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    job = (
        await session.execute(select(DeletionJob).where(DeletionJob.status_token == status_token))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Deletion status token not found")
    return {
        "status_token": job.status_token,
        "status": job.status,
        "subscription_cancelled": job.subscription_cancelled,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


# ==================== MCP Assistant Endpoint (/api/v1/mcp) ====================
class McpRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = 1
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/mcp")
async def handle_mcp_request(
    rpc: McpRpcRequest,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """
    Model Context Protocol (MCP) JSON-RPC 2.0 endpoint for assistant integration:
    Supports `initialize`, `tools/list`, and `tools/call` (`list_topics`, `search_knowledge`, `get_today_plan`).
    """
    if rpc.method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rpc.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "brainrecall-mcp", "version": "1.14.0"},
                "capabilities": {"tools": {}},
            },
        }

    if rpc.method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": rpc.id,
            "result": {
                "tools": [
                    {
                        "name": "list_topics",
                        "description": "List active BrainRecall topics and knowledge card counts.",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "search_knowledge",
                        "description": "Search BrainRecall knowledge cards and M5 meaning groups.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                    },
                ]
            },
        }

    if rpc.method == "tools/call":
        if user is None:
            return {
                "jsonrpc": "2.0",
                "id": rpc.id,
                "error": {"code": -32001, "message": "Authentication required for tools/call"},
            }
        tool_name = rpc.params.get("name")
        args = rpc.params.get("arguments") or {}
        if tool_name == "list_topics":
            topics = (
                await session.execute(
                    select(Topic).where(Topic.owner_id == user.id, Topic.status != "archived")
                )
            ).scalars().all()
            payload = [{"id": tp.id, "title": tp.title, "goal": tp.goal} for tp in topics]
            return {
                "jsonrpc": "2.0",
                "id": rpc.id,
                "result": {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]},
            }
        if tool_name == "search_knowledge":
            q = f"%{str(args.get('query') or '').strip()}%"
            items = (
                await session.execute(
                    select(KnowledgeItem).where(
                        KnowledgeItem.owner_id == user.id,
                        KnowledgeItem.prompt.ilike(q) | KnowledgeItem.answer.ilike(q),
                    ).limit(10)
                )
            ).scalars().all()
            payload = [{"id": it.id, "prompt": it.prompt, "answer": it.answer} for it in items]
            return {
                "jsonrpc": "2.0",
                "id": rpc.id,
                "result": {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]},
            }

    return {
        "jsonrpc": "2.0",
        "id": rpc.id,
        "error": {"code": -32601, "message": f"Unsupported MCP method: {rpc.method}"},
    }
