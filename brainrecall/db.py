"""Async SQLAlchemy database engine and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from brainrecall.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        cfg = get_settings()
        if cfg.database_url.startswith("sqlite"):
            Path("./storage").mkdir(parents=True, exist_ok=True)
        kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
        if cfg.database_url.startswith("postgresql"):
            kwargs["pool_size"] = 10
            kwargs["max_overflow"] = 10
        _engine = create_async_engine(cfg.database_url, **kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


get_session = get_db


async def init_db() -> None:
    import brainrecall.models  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
