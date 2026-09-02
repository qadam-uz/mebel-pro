"""Telegram Bot API webhook.

The only unauthenticated write surface in the app, so it is gated on the shared
`secret_token` Telegram echoes back in a header — the same mechanism the Bot API
documents for exactly this. Updates arrive through the prod edge; there is no
polling process and no queue.
"""

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Header, status

from app.api.deps import Session
from app.core.config import settings
from app.core.errors import APIError
from app.modules.access.api import handle_telegram_update

router = APIRouter(prefix="/telegram", tags=["telegram"])

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"  # noqa: S105 - header name, not a secret


@router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def telegram_webhook(
    update: dict[str, Any],
    db: Session,
    secret_token: Annotated[str | None, Header(alias=SECRET_HEADER)] = None,
) -> None:
    """Handle one update, committing before the 2xx Telegram reads as delivered.

    Telegram retries anything that isn't a 2xx, so the response must not be sent
    before the handshake state is durable — which the request-scoped session
    already guarantees (`app/api/deps.py`).
    """
    _require_webhook_secret(secret_token)
    await handle_telegram_update(db, update)


def _require_webhook_secret(secret_token: str | None) -> None:
    configured = settings.TELEGRAM_WEBHOOK_SECRET
    # An unset secret means the webhook is not configured; refuse rather than
    # accept everything (the fail-safe direction for security config).
    if (
        configured in {"", "{{change-me}}"}
        or secret_token is None
        or not hmac.compare_digest(secret_token, configured)
    ):
        raise APIError(
            "invalid_webhook_secret",
            "Invalid webhook secret",
            status_code=status.HTTP_403_FORBIDDEN,
        )
