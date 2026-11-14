"""Configuration settings for BrainRecall."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

PLAN_LIMITS: dict[str, dict[str, Any]] = {
    "free": {
        "price_xtr": 0,
        "period_days": None,
        "topics": 3,
        "habits": 3,
        "items": 500,
        "import_tokens": 0,
        "ai_checks": 0,
        "ai_cases": 0,
        "ai_plans": 0,
        "ai_reviews": 0,
    },
    "trial": {
        "price_xtr": 0,
        "period_days": 7,
        "topics": 10,
        "habits": 10,
        "items": 10_000,
        "import_tokens": 30_000,
        "ai_checks": 20,
        "ai_cases": 5,
        "ai_plans": 1,
        "ai_reviews": 0,
    },
    "start": {
        "price_xtr": 499,
        "period_days": 30,
        "subscription_period": 2_592_000,
        "topics": 10,
        "habits": 10,
        "items": 10_000,
        "import_tokens": 200_000,
        "ai_checks": 200,
        "ai_cases": 20,
        "ai_plans": 5,
        "ai_reviews": 4,
    },
    "pro": {
        "price_xtr": 1099,
        "period_days": 30,
        "subscription_period": 2_592_000,
        "topics": 50,
        "habits": 30,
        "items": 30_000,
        "import_tokens": 600_000,
        "ai_checks": 1_000,
        "ai_cases": 100,
        "ai_plans": 20,
        "ai_reviews": 4,
    },
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./storage/brainrecall.sqlite"
    telegram_bot_token: str = ""
    telegram_bot_username: str = "BrainRecallBot"
    telegram_webhook_secret: str = "brainrecall-webhook-secret-v1"
    telegram_api_base_url: str = "https://api.telegram.org"
    telegram_proxy_url: str | None = None

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    public_base_url: str = "https://owncome.ru/brainrecall"
    session_secret: str = "brainrecall-session-secret-change-in-prod"
    init_data_ttl_seconds: int = 86400
    session_ttl_seconds: int = 86400 * 30

    storage_dir: Path = Path("./storage/files")
    max_upload_bytes: int = 20 * 1024 * 1024  # 20 MiB MVP limit
    max_source_tokens: int = 100_000

    freeze_day_price_xtr: int = 49
    freeze_week_price_xtr: int = 199

    ai_global_kill_switch: bool = False
    ai_daily_user_cap_usd: float = 2.50
    support_contact: str = "@BrainRecallBot"
    default_locale: str = "ru"

    @property
    def app_secret_key(self) -> str:
        return self.session_secret

    @property
    def miniapp_url(self) -> str:
        return self.public_base_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
