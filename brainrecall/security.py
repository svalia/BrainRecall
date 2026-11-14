from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brainrecall.config import PLAN_LIMITS, settings
from brainrecall.db import get_session
from brainrecall.i18n import resolve_user_locale
from brainrecall.models import Entitlement, ReminderPreference, RewardCycle, User


def validate_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict[str, Any] | None:
    if not init_data or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    auth_date_str = pairs.get("auth_date", "0")
    try:
        auth_date = int(auth_date_str)
    except ValueError:
        return None

    if max_age_seconds > 0 and (int(time.time()) - auth_date) > max_age_seconds:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    user_raw = pairs.get("user")
    user_data = json.loads(user_raw) if user_raw else {}
    return {
        "auth_date": auth_date,
        "user": user_data,
        "query_id": pairs.get("query_id"),
        "start_param": pairs.get("start_param"),
    }


def create_session_token(user_id: str, tg_user_id: int, ttl_seconds: int = 86400 * 7) -> str:
    payload = {
        "uid": str(user_id),
        "tg": int(tg_user_id),
        "exp": int(time.time()) + ttl_seconds,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(settings.app_secret_key.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def verify_session_token(token: str) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    b64, sig = token.rsplit(".", 1)
    expected_sig = hmac.new(settings.app_secret_key.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        return None
    padding = "=" * (-len(b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(b64 + padding).decode("utf-8"))
    except Exception:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


def create_signed_estimate_token(payload: dict[str, Any], ttl_seconds: int = 1800) -> str:
    data = {**payload, "exp": int(time.time()) + ttl_seconds}
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(settings.app_secret_key.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def verify_signed_estimate_token(token: str) -> dict[str, Any] | None:
    return verify_session_token(token)


async def get_or_create_tg_user(
    session: AsyncSession,
    *,
    tg_user_id: int,
    username: str | None = None,
    first_name: str | None = None,
    language_code: str | None = None,
    accept_language: str | None = None,
) -> User:
    stmt = select(User).where(User.telegram_id == tg_user_id)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()

    if user is None:
        resolved_loc = resolve_user_locale(
            telegram_language_code=language_code,
            accept_language=accept_language,
        )
        user = User(
            telegram_id=tg_user_id,
            username=username,
            first_name=first_name,
            locale=resolved_loc,
            locale_override=False,
        )
        session.add(user)
        await session.flush()

        free_limits = PLAN_LIMITS["free"]
        ent = Entitlement(
            owner_id=user.id,
            plan_code="free",
            status="active",
            import_tokens_limit=free_limits["import_tokens"],
            ai_checks_limit=free_limits["ai_checks"],
            ai_cases_limit=free_limits["ai_cases"],
            ai_plans_limit=free_limits["ai_plans"],
            ai_reviews_limit=free_limits["ai_reviews"],
        )
        session.add(ent)

        rem = ReminderPreference(owner_id=user.id)
        session.add(rem)

        rc = RewardCycle(owner_id=user.id)
        session.add(rc)

        await session.commit()
        await session.refresh(user)
    else:
        changed = False
        if username and user.username != username:
            user.username = username
            changed = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if not user.locale_override and language_code:
            new_loc = resolve_user_locale(telegram_language_code=language_code)
            if user.locale != new_loc:
                user.locale = new_loc
                changed = True
        if changed:
            await session.commit()
            await session.refresh(user)

    return user


async def get_current_user_optional(
    request: Request,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
    x_telegram_init_data: str | None = Header(default=None),
    x_demo_user_id: str | None = Header(default=None),
) -> User | None:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        payload = verify_session_token(token)
        if payload and "uid" in payload:
            res = await session.execute(select(User).where(User.id == str(payload["uid"])))
            user = res.scalar_one_or_none()
            if user and user.status == "active":
                return user

    if x_telegram_init_data:
        parsed = validate_telegram_init_data(x_telegram_init_data, settings.telegram_bot_token)
        if parsed and parsed.get("user", {}).get("id"):
            tg_u = parsed["user"]
            return await get_or_create_tg_user(
                session,
                tg_user_id=int(tg_u["id"]),
                username=tg_u.get("username"),
                first_name=tg_u.get("first_name"),
                language_code=tg_u.get("language_code"),
                accept_language=request.headers.get("accept-language"),
            )

    if x_demo_user_id and settings.app_env != "production":
        try:
            tg_id = int(x_demo_user_id)
        except ValueError:
            tg_id = 999000111
        return await get_or_create_tg_user(
            session,
            tg_user_id=tg_id,
            username="demo_user",
            first_name="Demo",
            accept_language=request.headers.get("accept-language"),
        )

    return None


async def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram Mini App authentication is required.",
        )
    return user
