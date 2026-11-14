from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from brainrecall.config import settings
from brainrecall.i18n import t

logger = logging.getLogger(__name__)


class TelegramClient:
    """Persistent Keep-Alive HTTP client for Telegram Bot API (Dev Spec Section 11.4)."""

    def __init__(self) -> None:
        self._rpc_client: httpx.AsyncClient | None = None
        self._file_client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        return f"https://api.telegram.org/bot{settings.telegram_bot_token}"

    @property
    def file_base_url(self) -> str:
        return f"https://api.telegram.org/file/bot{settings.telegram_bot_token}"

    def _get_rpc_client(self) -> httpx.AsyncClient:
        if self._rpc_client is None or self._rpc_client.is_closed:
            self._rpc_client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=3.0, read=6.0, write=5.0, pool=3.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50, keepalive_expiry=60.0),
                http2=False,
            )
        return self._rpc_client

    def _get_file_client(self) -> httpx.AsyncClient:
        if self._file_client is None or self._file_client.is_closed:
            self._file_client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=45.0, write=30.0, pool=5.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=60.0),
            )
        return self._file_client

    async def close(self) -> None:
        if self._rpc_client and not self._rpc_client.is_closed:
            await self._rpc_client.aclose()
        if self._file_client and not self._file_client.is_closed:
            await self._file_client.aclose()

    async def call(self, method: str, payload: dict[str, Any] | None = None, retries: int = 2) -> dict[str, Any]:
        if not settings.telegram_bot_token:
            logger.warning("Telegram bot token not configured; skipping %s", method)
            return {"ok": False, "description": "No bot token configured"}

        client = self._get_rpc_client()
        url = f"{self.base_url}/{method}"
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = await client.post(url, json=payload or {})
                data = resp.json()
                if not data.get("ok"):
                    logger.warning("Telegram API %s returned not ok: %s", method, data.get("description"))
                return data
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_err = exc
                if attempt < retries:
                    await asyncio.sleep(0.35 * (attempt + 1))
        logger.error("Telegram API %s failed after retries: %s", method, last_err)
        return {"ok": False, "description": str(last_err)}

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        parse_mode: str = "HTML",
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self.call("sendMessage", payload)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id, "show_alert": show_alert}
        if text:
            payload["text"] = text
        return await self.call("answerCallbackQuery", payload, retries=1)

    async def answer_pre_checkout_query(
        self,
        pre_checkout_query_id: str,
        ok: bool = True,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"pre_checkout_query_id": pre_checkout_query_id, "ok": ok}
        if not ok and error_message:
            payload["error_message"] = error_message
        return await self.call("answerPreCheckoutQuery", payload, retries=1)

    async def create_invoice_link(
        self,
        *,
        title: str,
        description: str,
        payload: str,
        stars_amount: int,
        subscription_period: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "title": title,
            "description": description,
            "payload": payload,
            "currency": "XTR",
            "prices": [{"label": title, "amount": stars_amount}],
        }
        if subscription_period:
            body["subscription_period"] = subscription_period
        return await self.call("createInvoiceLink", body)

    async def edit_user_star_subscription(
        self,
        *,
        user_id: int,
        telegram_payment_charge_id: str,
        is_canceled: bool,
    ) -> dict[str, Any]:
        return await self.call(
            "editUserStarSubscription",
            {
                "user_id": user_id,
                "telegram_payment_charge_id": telegram_payment_charge_id,
                "is_canceled": is_canceled,
            },
        )

    async def refund_star_payment(
        self,
        *,
        user_id: int,
        telegram_payment_charge_id: str,
    ) -> dict[str, Any]:
        return await self.call(
            "refundStarPayment",
            {
                "user_id": user_id,
                "telegram_payment_charge_id": telegram_payment_charge_id,
            },
        )

    async def register_commands_and_menu(self) -> None:
        if not settings.telegram_bot_token:
            return
        for lang_code in ("ru", "en", None):
            loc = lang_code or "ru"
            commands = [
                {"command": "start", "description": t("bot.commands.start", loc)},
                {"command": "lang", "description": t("bot.commands.lang", loc)},
                {"command": "help", "description": t("bot.commands.help", loc)},
                {"command": "paysupport", "description": t("bot.commands.paysupport", loc)},
            ]
            body: dict[str, Any] = {"commands": commands}
            if lang_code:
                body["language_code"] = lang_code
            await self.call("setMyCommands", body)

        await self.call(
            "setChatMenuButton",
            {
                "menu_button": {
                    "type": "web_app",
                    "text": "BrainRecall",
                    "web_app": {"url": settings.miniapp_url},
                }
            },
        )


tg_client = TelegramClient()
