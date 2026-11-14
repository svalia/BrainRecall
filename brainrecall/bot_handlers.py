from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brainrecall.config import PLAN_LIMITS, settings
from brainrecall.i18n import SUPPORTED_LOCALES, resolve_user_locale, t
from brainrecall.models import Entitlement, FreezeLedger, PaymentOrder, ProtectionInterval, User
from brainrecall.security import get_or_create_tg_user
from brainrecall.telegram_api import tg_client

logger = logging.getLogger(__name__)


def build_welcome_keyboard(locale: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": f"🚀 {t('bot.welcome.open_app', locale)}",
                    "web_app": {"url": settings.miniapp_url},
                }
            ],
            [
                {"text": t("bot.welcome.change_lang", locale), "callback_data": "lang:menu"},
                {"text": t("bot.welcome.help_btn", locale), "callback_data": "bot:help"},
            ],
        ]
    }


def build_lang_keyboard() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": t("bot.lang.ru", "ru"), "callback_data": "lang:set:ru"},
                {"text": t("bot.lang.en", "en"), "callback_data": "lang:set:en"},
            ]
        ]
    }


async def handle_telegram_update(session: AsyncSession, update: dict[str, Any]) -> dict[str, Any]:
    if "pre_checkout_query" in update:
        pcq = update["pre_checkout_query"]
        await tg_client.answer_pre_checkout_query(pcq["id"], ok=True)
        return {"handled": "pre_checkout_query"}

    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb["id"]
        data = cb.get("data", "")
        from_user = cb.get("from", {})
        chat_id = cb.get("message", {}).get("chat", {}).get("id") or from_user.get("id")

        user = await get_or_create_tg_user(
            session,
            tg_user_id=int(from_user["id"]),
            username=from_user.get("username"),
            first_name=from_user.get("first_name"),
            language_code=from_user.get("language_code"),
        )
        loc = resolve_user_locale(
            locale_override=user.locale if user.locale_override else None,
            saved_locale=user.locale,
            telegram_language_code=from_user.get("language_code"),
        )

        # Immediately acknowledge callback per Section 11.4
        if data == "lang:menu":
            await tg_client.answer_callback_query(cb_id)
            if chat_id:
                await tg_client.send_message(
                    int(chat_id),
                    t("bot.lang.prompt", loc),
                    reply_markup=build_lang_keyboard(),
                )
            return {"handled": "lang:menu"}

        if data.startswith("lang:set:"):
            target_loc = data.split(":")[-1]
            if target_loc in SUPPORTED_LOCALES:
                user.locale = target_loc
                user.locale_override = True
                await session.commit()
                loc = target_loc
            await tg_client.answer_callback_query(cb_id, text=t("bot.lang.changed", loc))
            if chat_id:
                text = f"{t('bot.welcome.title', loc)}\n\n{t('bot.welcome.body', loc)}"
                await tg_client.send_message(
                    int(chat_id),
                    text,
                    reply_markup=build_welcome_keyboard(loc),
                )
            return {"handled": f"lang:set:{loc}"}

        if data == "bot:help":
            await tg_client.answer_callback_query(cb_id)
            if chat_id:
                text = f"{t('bot.help.title', loc)}\n\n{t('bot.help.body', loc)}"
                await tg_client.send_message(
                    int(chat_id),
                    text,
                    reply_markup=build_welcome_keyboard(loc),
                )
            return {"handled": "bot:help"}

        if data.startswith("rem:snooze:"):
            await tg_client.answer_callback_query(cb_id, text=t("bot.reminder.snoozed", loc))
            return {"handled": "rem:snooze"}

        if data.startswith("rem:skip:"):
            await tg_client.answer_callback_query(cb_id, text=t("bot.reminder.skipped", loc))
            return {"handled": "rem:skip"}

        await tg_client.answer_callback_query(cb_id)
        return {"handled": "callback_other"}

    if "message" in update:
        msg = update["message"]
        from_user = msg.get("from", {})
        chat_id = msg.get("chat", {}).get("id")
        if not from_user or not chat_id:
            return {"handled": "ignored"}

        user = await get_or_create_tg_user(
            session,
            tg_user_id=int(from_user["id"]),
            username=from_user.get("username"),
            first_name=from_user.get("first_name"),
            language_code=from_user.get("language_code"),
        )
        loc = resolve_user_locale(
            locale_override=user.locale if user.locale_override else None,
            saved_locale=user.locale,
            telegram_language_code=from_user.get("language_code"),
        )

        if "successful_payment" in msg:
            sp = msg["successful_payment"]
            await _process_successful_payment(session, user, int(chat_id), loc, sp)
            return {"handled": "successful_payment"}

        text_in = (msg.get("text") or "").strip()
        if text_in.startswith("/start"):
            parts = text_in.split(maxsplit=1)
            if len(parts) > 1 and parts[1].lower() in ("en", "ru"):
                user.locale = parts[1].lower()
                user.locale_override = True
                loc = user.locale
                await session.commit()
            welcome_text = f"{t('bot.welcome.title', loc)}\n\n{t('bot.welcome.body', loc)}"
            await tg_client.send_message(
                int(chat_id),
                welcome_text,
                reply_markup=build_welcome_keyboard(loc),
            )
            return {"handled": "/start"}

        if text_in.startswith("/lang"):
            await tg_client.send_message(
                int(chat_id),
                t("bot.lang.prompt", loc),
                reply_markup=build_lang_keyboard(),
            )
            return {"handled": "/lang"}

        if text_in.startswith("/help"):
            help_text = f"{t('bot.help.title', loc)}\n\n{t('bot.help.body', loc)}"
            await tg_client.send_message(
                int(chat_id),
                help_text,
                reply_markup=build_welcome_keyboard(loc),
            )
            return {"handled": "/help"}

        if text_in.startswith("/paysupport"):
            ps_text = f"{t('bot.paysupport.title', loc)}\n\n{t('bot.paysupport.body', loc)}"
            await tg_client.send_message(
                int(chat_id),
                ps_text,
                reply_markup=build_welcome_keyboard(loc),
            )
            return {"handled": "/paysupport"}

        welcome_text = f"{t('bot.welcome.title', loc)}\n\n{t('bot.welcome.body', loc)}"
        await tg_client.send_message(
            int(chat_id),
            welcome_text,
            reply_markup=build_welcome_keyboard(loc),
        )
        return {"handled": "default_message"}

    return {"handled": "noop"}


async def _process_successful_payment(
    session: AsyncSession,
    user: User,
    chat_id: int,
    locale: str,
    sp: dict[str, Any],
) -> None:
    charge_id = sp.get("telegram_payment_charge_id", "")
    total_amount = int(sp.get("total_amount", 0))
    raw_payload = sp.get("invoice_payload", "{}")
    try:
        payload_data = json.loads(raw_payload)
    except Exception:
        payload_data = {"raw": raw_payload}

    kind = payload_data.get("kind", "subscription")
    plan = payload_data.get("plan", "start")

    if charge_id:
        existing = await session.execute(
            select(PaymentOrder).where(PaymentOrder.telegram_payment_charge_id == charge_id)
        )
        if existing.scalar_one_or_none() is not None:
            return

    now = datetime.now(timezone.utc)
    order = PaymentOrder(
        owner_id=user.id,
        telegram_user_id=user.telegram_id,
        product_type=f"plan_{plan}" if kind == "subscription" else kind,
        plan_code=plan if kind == "subscription" else None,
        amount_xtr=total_amount,
        currency="XTR",
        is_recurring=(kind == "subscription"),
        week_start_date=payload_data.get("start_date"),
        invoice_payload=raw_payload[:120] or str(uuid.uuid4()),
        telegram_payment_charge_id=charge_id or None,
        status="paid",
        paid_at=now,
    )
    session.add(order)

    if kind == "subscription" and plan in ("start", "pro"):
        ent_res = await session.execute(select(Entitlement).where(Entitlement.owner_id == user.id))
        ent = ent_res.scalar_one_or_none()
        period_end = now + timedelta(days=30)
        limits = PLAN_LIMITS[plan]
        if ent is None:
            ent = Entitlement(
                owner_id=user.id,
                plan_code=plan,
                status="active",
                period_id=f"{plan}-{int(now.timestamp())}",
                period_start=now,
                period_end=period_end,
                auto_renew=True,
                telegram_charge_id=charge_id or None,
                import_tokens_limit=limits["import_tokens"],
                ai_checks_limit=limits["ai_checks"],
                ai_cases_limit=limits["ai_cases"],
                ai_plans_limit=limits["ai_plans"],
                ai_reviews_limit=limits["ai_reviews"],
            )
            session.add(ent)
        else:
            ent.plan_code = plan
            ent.status = "active"
            ent.period_id = f"{plan}-{int(now.timestamp())}"
            ent.period_start = now
            ent.period_end = period_end
            ent.auto_renew = True
            ent.telegram_charge_id = charge_id or ent.telegram_charge_id
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

        await session.commit()
        await tg_client.send_message(
            chat_id,
            t("bot.payment.success_plan", locale, plan=plan.upper(), until=period_end.strftime("%Y-%m-%d")),
        )
    elif kind == "freeze_day":
        ledger_entry = FreezeLedger(
            owner_id=user.id,
            entry_key=f"purchase:{charge_id or uuid.uuid4()}",
            kind="purchase",
            origin_kind="paid",
            amount_delta=1,
            balance_after=1,
            source_id=charge_id or "",
            local_date=now.strftime("%Y-%m-%d"),
            note="Single-day freeze purchase",
        )
        session.add(ledger_entry)
        await session.commit()
        await tg_client.send_message(
            chat_id,
            t("bot.payment.success_freeze", locale, kind=kind),
        )
    elif kind == "freeze_week":
        start_d = payload_data.get("start_date") or (now + timedelta(days=1)).strftime("%Y-%m-%d")
        end_d = payload_data.get("end_date") or (now + timedelta(days=8)).strftime("%Y-%m-%d")
        pi = ProtectionInterval(
            owner_id=user.id,
            start_date=start_d,
            end_date_exclusive=end_d,
            timezone_snapshot=user.timezone,
            order_id=order.id,
            status="active",
        )
        session.add(pi)
        await session.commit()
        await tg_client.send_message(
            chat_id,
            t("bot.payment.success_freeze", locale, kind=kind),
        )
    else:
        await session.commit()
