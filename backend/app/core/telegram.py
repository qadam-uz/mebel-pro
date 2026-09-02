"""Thin Telegram Bot API client.

Infrastructure, not domain: the `access` module drives the sign-in conversation
through it and `support` delivers order notifications through it. One external
integration, no polling process and no queue (`docs/architecture.md`) — every
send is a single HTTPS call made from the request that caused it (webhook
replies) or from a best-effort post-commit task (notifications).
"""

from typing import Any

import httpx
from structlog import get_logger

from app.core.config import settings

logger = get_logger(__name__)

_UNCONFIGURED = {"", "{{change-me}}"}


class TelegramApiError(Exception):
    """The Bot API refused or could not be reached."""


class TelegramForbiddenError(TelegramApiError):
    """403 from the Bot API — the user blocked the bot or never started it."""


def bot_configured() -> bool:
    return settings.TELEGRAM_BOT_TOKEN not in _UNCONFIGURED


def deep_link(token: str) -> str:
    """The `t.me` link the login page renders as a QR / button."""
    return f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={token}"


def http_client() -> httpx.AsyncClient:
    """The one place a Bot API connection is opened — the seam tests replace."""
    return httpx.AsyncClient(timeout=settings.TELEGRAM_API_TIMEOUT_SECONDS)


async def call(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST one Bot API method, raising `TelegramApiError` on any failure."""
    if not bot_configured():
        raise TelegramApiError("telegram_bot_unconfigured")
    url = f"{settings.TELEGRAM_API_BASE_URL.rstrip('/')}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"
    try:
        async with http_client() as http:
            response = await http.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise TelegramApiError(str(exc)) from exc
    if response.status_code == httpx.codes.FORBIDDEN:
        raise TelegramForbiddenError(_describe(response))
    if response.status_code >= httpx.codes.BAD_REQUEST:
        raise TelegramApiError(_describe(response))
    body = response.json()
    if not isinstance(body, dict) or body.get("ok") is not True:
        raise TelegramApiError(str(body))
    result = body.get("result")
    return result if isinstance(result, dict) else {}


async def send_message(
    *,
    chat_id: int,
    text: str,
    reply_markup: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    await call("sendMessage", payload)


async def answer_callback_query(*, callback_query_id: str, text: str | None = None) -> None:
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text is not None:
        payload["text"] = text
    await call("answerCallbackQuery", payload)


def _describe(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    description = body.get("description") if isinstance(body, dict) else None
    return f"HTTP {response.status_code}: {description or body}"
