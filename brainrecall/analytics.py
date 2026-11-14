from __future__ import annotations

from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from brainrecall.models import AnalyticsEvent, User

FORBIDDEN_PII_KEYS = {
    "raw_init_data",
    "init_data",
    "bot_token",
    "deepseek_api_key",
    "file_content",
    "answer_raw_text",
}


def sanitize_analytics_properties(props: dict[str, Any] | None) -> dict[str, Any]:
    if not props:
        return {}
    clean: dict[str, Any] = {}
    for k, v in props.items():
        if k.lower() in FORBIDDEN_PII_KEYS:
            continue
        if isinstance(v, str) and len(v) > 250:
            clean[k] = v[:250]
        else:
            clean[k] = v
    return clean


class AnalyticsFacade:
    """Unified analytics facade implementing Section 14 of Dev Spec v1.14."""

    async def track(
        self,
        session: AsyncSession,
        *,
        event_name: str,
        user: User | None = None,
        anonymous_id: str | None = None,
        source: str = "server",
        properties: dict[str, Any] | None = None,
    ) -> AnalyticsEvent | None:
        if user is not None and not user.analytics_consent:
            return None
        evt = AnalyticsEvent(
            event_name=event_name,
            source=source,
            analytics_user_id=user.analytics_user_id if user else anonymous_id,
            event_properties=sanitize_analytics_properties(properties),
        )
        session.add(evt)
        await session.flush()
        return evt

    async def identify(
        self,
        session: AsyncSession,
        *,
        user: User,
        anonymous_id: str | None = None,
        traits: dict[str, Any] | None = None,
    ) -> None:
        if not user.analytics_consent:
            return
        await self.track(
            session,
            event_name="$identify",
            user=user,
            anonymous_id=anonymous_id,
            properties=traits or {},
        )

    async def set_user_properties(
        self,
        session: AsyncSession,
        *,
        user: User,
        properties: dict[str, Any],
    ) -> None:
        if not user.analytics_consent:
            return
        await self.track(
            session,
            event_name="$set",
            user=user,
            properties=properties,
        )

    async def set_user_properties_once(
        self,
        session: AsyncSession,
        *,
        user: User,
        properties: dict[str, Any],
    ) -> None:
        if not user.analytics_consent:
            return
        await self.track(
            session,
            event_name="$set_once",
            user=user,
            properties=properties,
        )

    async def unset_user_properties(
        self,
        session: AsyncSession,
        *,
        user: User,
        keys: list[str],
    ) -> None:
        if not user.analytics_consent:
            return
        await self.track(
            session,
            event_name="$unset",
            user=user,
            properties={"keys": keys},
        )

    async def set_collection_allowed(
        self,
        session: AsyncSession,
        *,
        user: User,
        allowed: bool,
    ) -> None:
        user.analytics_consent = allowed
        await session.flush()

    async def delete_analytics_user(
        self,
        session: AsyncSession,
        *,
        analytics_user_id: str,
    ) -> int:
        stmt = delete(AnalyticsEvent).where(AnalyticsEvent.analytics_user_id == analytics_user_id)
        res = await session.execute(stmt)
        return int(res.rowcount or 0)


analytics = AnalyticsFacade()
