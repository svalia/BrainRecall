from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from brainrecall.analytics import analytics
from brainrecall.bot_handlers import handle_telegram_update
from brainrecall.config import PLAN_LIMITS, settings
from brainrecall.db import get_session, init_db
from brainrecall.i18n import (
    SUPPORTED_LOCALES,
    get_catalog,
    normalize_locale,
    resolve_user_locale,
    verify_catalog_parity,
)
from brainrecall.billing_routes import router as billing_router
from brainrecall.habits_streaks_routes import router as habits_streaks_router
from brainrecall.knowledge_routes import router as knowledge_router
from brainrecall.materials_ai_routes import router as materials_ai_router
from brainrecall.progress_account_routes import router as progress_account_router
from brainrecall.study_routes import router as study_router
from brainrecall.models import (
    Entitlement,
    Habit,
    KnowledgeItem,
    ReminderPreference,
    Topic,
    User,
    UserMethodIntro,
)
from brainrecall.science_catalog import SCIENCE_CATALOG, get_science_catalog_for_locale
from brainrecall.security import (
    create_session_token,
    get_current_user,
    get_current_user_optional,
    get_or_create_tg_user,
    validate_telegram_init_data,
)
from brainrecall.telegram_api import tg_client

MINIAPP_DIR = Path(__file__).resolve().parent.parent / "miniapp"


@asynccontextmanager
async def lifespan(app: FastAPI):
    ok, parity_errors = verify_catalog_parity()
    if not ok:
        raise RuntimeError(f"i18n catalog parity check failed: {parity_errors}")
    await init_db()
    await tg_client.register_commands_and_menu()
    yield
    await tg_client.close()


app = FastAPI(
    title="BrainRecall API",
    version="1.14.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(knowledge_router)
app.include_router(study_router)
app.include_router(habits_streaks_router)
app.include_router(materials_ai_router)
app.include_router(billing_router)
app.include_router(progress_account_router)


class BootstrapRequest(BaseModel):
    init_data: str | None = None
    locale_hint: str | None = None
    timezone_hint: str | None = None
    anonymous_id: str | None = None
    demo_mode: bool = False


class OnboardingSaveRequest(BaseModel):
    goal_focus: str = Field(default="both", pattern="^(both|knowledge|habits)$")
    daily_study_minutes: int = Field(default=10, ge=5, le=60)
    reminder_window: str = Field(default="evening", pattern="^(morning|afternoon|evening)$")
    timezone: str = Field(default="Europe/Moscow")
    locale_override: str | None = None


class SettingsUpdateRequest(BaseModel):
    locale_override: str | None = None
    timezone: str | None = None
    daily_study_minutes: int | None = None
    reminder_window: str | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    haptics_enabled: bool | None = None
    achievement_effects_enabled: bool | None = None
    notifications_enabled: bool | None = None
    analytics_allowed: bool | None = None


class MethodIntroUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(dismissed|acknowledged)$")


def _window_to_time(window: str) -> str:
    if window == "morning":
        return "09:00"
    if window == "afternoon":
        return "14:00"
    return "20:00"


def _time_to_window(daily_time: str) -> str:
    if daily_time.startswith("09") or daily_time.startswith("08"):
        return "morning"
    if daily_time.startswith("14") or daily_time.startswith("13"):
        return "afternoon"
    return "evening"


def _serialize_user(
    user: User,
    ent: Entitlement | None,
    rem: ReminderPreference | None,
) -> dict[str, Any]:
    plan_code = ent.plan_code if ent else "free"
    onboarding_completed = bool(user.rhythm_configured_at is not None)
    return {
        "id": user.id,
        "tg_user_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "locale": user.locale,
        "locale_override": user.locale if user.locale_override else None,
        "timezone": user.timezone,
        "onboarding_completed": onboarding_completed,
        "goal_focus": "both",
        "daily_study_minutes": user.daily_minutes,
        "reminder_window": _time_to_window(rem.daily_time if rem else "20:00"),
        "quiet_hours_start": rem.quiet_start if rem else "22:00",
        "quiet_hours_end": rem.quiet_end if rem else "08:00",
        "haptics_enabled": user.haptics_enabled,
        "achievement_effects_enabled": user.achievement_effects_enabled,
        "notifications_enabled": rem.enabled if rem else False,
        "bot_write_access": rem.write_access_granted if rem else False,
        "analytics_allowed": user.analytics_consent,
        "plan": plan_code,
        "plan_limits": PLAN_LIMITS.get(plan_code, PLAN_LIMITS["free"]),
        "trial_used": ent.trial_used if ent else False,
    }


async def _get_method_intros_payload(session: AsyncSession, user: User | None, locale: str) -> list[dict[str, Any]]:
    science_list = get_science_catalog_for_locale(locale)
    user_intros: dict[str, UserMethodIntro] = {}
    if user is not None:
        res = await session.execute(select(UserMethodIntro).where(UserMethodIntro.owner_id == user.id))
        for row in res.scalars().all():
            user_intros[row.method_id] = row

    enriched: list[dict[str, Any]] = []
    for item in science_list:
        mid = item["method_id"]
        ver = item["content_version"]
        ui = user_intros.get(mid)
        if ui is None:
            status_val = "unseen"
            is_updated = False
            seen_version = None
        else:
            status_val = ui.status
            seen_version = ui.acknowledged_content_version
            is_updated = bool(seen_version and seen_version != ver)
        enriched.append(
            {
                **item,
                "intro_status": status_val,
                "seen_content_version": seen_version,
                "is_updated": is_updated,
            }
        )
    return enriched


@app.get("/health")
async def health_check() -> dict[str, Any]:
    ok, errors = verify_catalog_parity()
    return {
        "status": "ok" if ok else "degraded",
        "service": "brainrecall",
        "version": "1.14.0",
        "i18n_parity": ok,
        "i18n_errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/i18n")
async def get_i18n_catalog_endpoint(
    request: Request,
    locale: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    resolved = resolve_user_locale(
        locale_override=locale or (user.locale if (user and user.locale_override) else None),
        saved_locale=user.locale if user else None,
        accept_language=request.headers.get("accept-language"),
    )
    return {
        "locale": resolved,
        "supported_locales": list(SUPPORTED_LOCALES),
        "catalog": get_catalog(resolved),
        "science_methods": await _get_method_intros_payload(session, user=user, locale=resolved),
    }


@app.post("/api/v1/auth/bootstrap")
async def auth_bootstrap(
    payload: BootstrapRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    existing_user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    user = existing_user
    inside_telegram = False

    if payload.init_data:
        parsed = validate_telegram_init_data(payload.init_data, settings.telegram_bot_token)
        if parsed and parsed.get("user", {}).get("id"):
            inside_telegram = True
            tg_u = parsed["user"]
            user = await get_or_create_tg_user(
                session,
                tg_user_id=int(tg_u["id"]),
                username=tg_u.get("username"),
                first_name=tg_u.get("first_name"),
                language_code=tg_u.get("language_code"),
                accept_language=request.headers.get("accept-language"),
            )

    if user is None and payload.demo_mode:
        user = await get_or_create_tg_user(
            session,
            tg_user_id=999000111,
            username="demo_explorer",
            first_name="Explorer",
            language_code=payload.locale_hint or "ru",
            accept_language=request.headers.get("accept-language"),
        )

    if user is not None:
        if payload.timezone_hint and user.timezone == "Europe/Moscow":
            try:
                ZoneInfo(payload.timezone_hint)
                user.timezone = payload.timezone_hint
                await session.commit()
            except Exception:
                pass

        loc = resolve_user_locale(
            locale_override=user.locale if user.locale_override else None,
            saved_locale=user.locale,
            telegram_language_code=payload.locale_hint,
            accept_language=request.headers.get("accept-language"),
        )
        ent_res = await session.execute(select(Entitlement).where(Entitlement.owner_id == user.id))
        ent = ent_res.scalar_one_or_none()

        rem_res = await session.execute(select(ReminderPreference).where(ReminderPreference.owner_id == user.id))
        rem = rem_res.scalar_one_or_none()

        topics_res = await session.execute(
            select(Topic).where(Topic.owner_id == user.id, Topic.status == "active")
        )
        topics_count = len(topics_res.scalars().all())

        habits_res = await session.execute(
            select(Habit).where(Habit.owner_id == user.id, Habit.status == "active")
        )
        habits_count = len(habits_res.scalars().all())

        items_res = await session.execute(
            select(KnowledgeItem).where(KnowledgeItem.owner_id == user.id, KnowledgeItem.status == "active")
        )
        items_count = len(items_res.scalars().all())

        await analytics.identify(
            session,
            user=user,
            anonymous_id=payload.anonymous_id,
            traits={"locale": loc, "plan": ent.plan_code if ent else "free"},
        )
        await session.commit()

        token = create_session_token(user.id, user.telegram_id)
        initial_screen = "D03" if user.rhythm_configured_at is not None else "D01"
        return {
            "authenticated": True,
            "inside_telegram": inside_telegram,
            "session_token": token,
            "locale": loc,
            "catalog": get_catalog(loc),
            "user": _serialize_user(user, ent, rem),
            "counts": {
                "topics": topics_count,
                "habits": habits_count,
                "items": items_count,
            },
            "method_intros": await _get_method_intros_payload(session, user, loc),
            "initial_screen": initial_screen,
        }

    # Anonymous / outside Telegram preview state
    loc = resolve_user_locale(
        telegram_language_code=payload.locale_hint,
        accept_language=request.headers.get("accept-language"),
    )
    return {
        "authenticated": False,
        "inside_telegram": False,
        "session_token": None,
        "locale": loc,
        "catalog": get_catalog(loc),
        "user": None,
        "counts": {"topics": 0, "habits": 0, "items": 0},
        "method_intros": await _get_method_intros_payload(session, None, loc),
        "initial_screen": "D01",
    }


@app.post("/api/v1/onboarding")
async def save_onboarding(
    payload: OnboardingSaveRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        ZoneInfo(payload.timezone)
        user.timezone = payload.timezone
    except Exception:
        user.timezone = "Europe/Moscow"

    now = datetime.now(timezone.utc)
    user.daily_minutes = payload.daily_study_minutes
    user.landing_passed_at = user.landing_passed_at or now
    user.rhythm_configured_at = now
    if payload.locale_override in SUPPORTED_LOCALES:
        user.locale = payload.locale_override
        user.locale_override = True

    rem_res = await session.execute(select(ReminderPreference).where(ReminderPreference.owner_id == user.id))
    rem = rem_res.scalar_one_or_none()
    if rem is None:
        rem = ReminderPreference(
            owner_id=user.id,
            daily_time=_window_to_time(payload.reminder_window),
        )
        session.add(rem)
    else:
        rem.daily_time = _window_to_time(payload.reminder_window)

    await analytics.track(
        session,
        event_name="onboarding_completed",
        user=user,
        properties={
            "goal_focus": payload.goal_focus,
            "daily_study_minutes": user.daily_minutes,
            "reminder_window": payload.reminder_window,
            "timezone": user.timezone,
        },
    )
    await session.commit()
    await session.refresh(user)

    ent_res = await session.execute(select(Entitlement).where(Entitlement.owner_id == user.id))
    ent = ent_res.scalar_one_or_none()
    return {
        "ok": True,
        "user": _serialize_user(user, ent, rem),
        "next_screen": "D03",
    }


@app.patch("/api/v1/settings")
async def update_settings(
    payload: SettingsUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if payload.locale_override is not None:
        loc = normalize_locale(payload.locale_override)
        user.locale = loc
        user.locale_override = True
    if payload.timezone is not None:
        try:
            ZoneInfo(payload.timezone)
            user.timezone = payload.timezone
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid IANA timezone") from exc
    if payload.daily_study_minutes is not None:
        user.daily_minutes = max(5, min(60, payload.daily_study_minutes))
    if payload.haptics_enabled is not None:
        user.haptics_enabled = payload.haptics_enabled
    if payload.achievement_effects_enabled is not None:
        user.achievement_effects_enabled = payload.achievement_effects_enabled
    if payload.analytics_allowed is not None:
        user.analytics_consent = payload.analytics_allowed

    rem_res = await session.execute(select(ReminderPreference).where(ReminderPreference.owner_id == user.id))
    rem = rem_res.scalar_one_or_none()
    if rem is None:
        rem = ReminderPreference(owner_id=user.id)
        session.add(rem)

    if payload.reminder_window in ("morning", "afternoon", "evening"):
        rem.daily_time = _window_to_time(payload.reminder_window)
    if payload.quiet_hours_start is not None:
        rem.quiet_start = payload.quiet_hours_start
    if payload.quiet_hours_end is not None:
        rem.quiet_end = payload.quiet_hours_end
    if payload.notifications_enabled is not None:
        rem.enabled = payload.notifications_enabled

    await session.commit()
    await session.refresh(user)

    ent_res = await session.execute(select(Entitlement).where(Entitlement.owner_id == user.id))
    ent = ent_res.scalar_one_or_none()
    loc = resolve_user_locale(
        locale_override=user.locale if user.locale_override else None,
        saved_locale=user.locale,
    )
    return {
        "ok": True,
        "locale": loc,
        "catalog": get_catalog(loc),
        "user": _serialize_user(user, ent, rem),
        "method_intros": await _get_method_intros_payload(session, user, loc),
    }


@app.get("/api/v1/me/method-intros")
async def get_my_method_intros(
    request: Request,
    locale: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    loc = resolve_user_locale(
        locale_override=locale or (user.locale if (user and user.locale_override) else None),
        saved_locale=user.locale if user else None,
        accept_language=request.headers.get("accept-language"),
    )
    return {
        "locale": loc,
        "methods": await _get_method_intros_payload(session, user, loc),
    }


@app.put("/api/v1/me/method-intros/{method_id}")
async def update_my_method_intro(
    method_id: str,
    payload: MethodIntroUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    mid = method_id.upper()
    if mid not in SCIENCE_CATALOG:
        raise HTTPException(status_code=404, detail="Unknown method_id")

    current_version = SCIENCE_CATALOG[mid]["content_version"]
    res = await session.execute(
        select(UserMethodIntro).where(
            UserMethodIntro.owner_id == user.id,
            UserMethodIntro.method_id == mid,
        )
    )
    row = res.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if row is None:
        row = UserMethodIntro(
            owner_id=user.id,
            method_id=mid,
            status=payload.status,
            intro_shown_at=now,
            dismissed_at=now if payload.status == "dismissed" else None,
            acknowledged_content_version=current_version if payload.status == "acknowledged" else None,
            acknowledged_at=now if payload.status == "acknowledged" else None,
        )
        session.add(row)
    else:
        row.status = payload.status
        row.intro_shown_at = row.intro_shown_at or now
        if payload.status == "dismissed":
            row.dismissed_at = now
            row.acknowledged_content_version = None
            row.acknowledged_at = None
        elif payload.status == "acknowledged":
            row.acknowledged_content_version = current_version
            row.acknowledged_at = now

    await analytics.track(
        session,
        event_name=f"method_intro_{payload.status}",
        user=user,
        properties={"method_id": mid, "content_version": current_version},
    )
    await session.commit()
    loc = resolve_user_locale(
        locale_override=user.locale if user.locale_override else None,
        saved_locale=user.locale,
    )
    return {
        "ok": True,
        "method_id": mid,
        "status": row.status,
        "seen_content_version": row.acknowledged_content_version,
        "methods": await _get_method_intros_payload(session, user, loc),
    }


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    update = await request.json()
    res = await handle_telegram_update(session, update)
    return {"ok": True, **res}


if MINIAPP_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(MINIAPP_DIR / "assets")), name="assets")


@app.get("/tokens.css")
async def serve_tokens_css() -> FileResponse:
    return FileResponse(MINIAPP_DIR / "tokens.css", media_type="text/css")


@app.get("/br.css")
async def serve_br_css() -> FileResponse:
    return FileResponse(MINIAPP_DIR / "br.css", media_type="text/css")


@app.get("/app.js")
async def serve_app_js() -> FileResponse:
    return FileResponse(MINIAPP_DIR / "app.js", media_type="application/javascript")


@app.get("/")
@app.get("/miniapp")
@app.get("/miniapp/")
async def serve_miniapp_index() -> FileResponse:
    return FileResponse(MINIAPP_DIR / "index.html", media_type="text/html")
