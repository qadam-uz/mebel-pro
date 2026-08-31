"""Telegram delivery of client notifications.

Every signed-in client has a bot chat (that is how they signed in), so their
order events land there as well as in the inbox. **The inbox is the source of
truth** — the bot message is a pointer to it, which is what makes best-effort
delivery acceptable: a lost message loses nothing durable.

Mechanics: the producing transaction *queues* an eligible send on its session,
and the send itself runs after that transaction commits. Nothing about the
order transition or the inbox row waits on Telegram, and a Bot API failure can
never roll one back.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session as SyncSession
from structlog import get_logger

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.telegram import TelegramApiError, TelegramForbiddenError, bot_configured, send_message
from app.modules.access.contracts import Client

logger = get_logger(__name__)

# Where queued sends ride between "the row was added" and "the transaction
# committed". Session-scoped, so a rolled-back fan-out delivers nothing.
PENDING_KEY = "telegram_client_deliveries"

# Uzbek-only in v1, like the bot's sign-in copy — the bot has no reliable
# locale channel. These mirror the sentences the inbox row renders.
EVENT_SENTENCES = {
    "order.confirmed": "Buyurtma tayyorlanmoqda",
    "order.ready": "Buyurtma tayyor",
    "order.completed": "Buyurtma topshirildi",
    "order.cancelled": "Buyurtma bekor qilindi",
    "order.updated": "Buyurtma yangilandi",
    # Older rows were written under the previous rule; the code stays mapped.
    "order.status_changed": "Buyurtma holati o'zgardi",
}

# Strong references to in-flight sends: asyncio only holds tasks weakly, so a
# fire-and-forget task can otherwise be garbage-collected mid-flight.
_IN_FLIGHT: set[asyncio.Task[None]] = set()


@dataclass(frozen=True)
class PendingTelegramMessage:
    client_id: uuid.UUID
    telegram_user_id: int
    text: str


def render_order_message(*, event_code: str, order_number: str, order_id: uuid.UUID) -> str | None:
    sentence = EVENT_SENTENCES.get(event_code)
    if sentence is None:
        return None
    link = f"{settings.CLIENT_APP_BASE_URL.rstrip('/')}/c/orders/{order_id}"
    return f"{sentence} — Buyurtma № {order_number}\n{link}"


async def queue_client_order_message(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    event_code: str,
    order_id: uuid.UUID,
    order_number: str,
) -> None:
    """Queue one bot message for this client, to be sent after the commit.

    A client with no linked account, or one known to have blocked the bot, is
    skipped silently — the inbox row still stands on its own.
    """
    if not bot_configured():
        return
    text = render_order_message(event_code=event_code, order_number=order_number, order_id=order_id)
    if text is None:
        return
    client = await db.get(Client, client_id)
    if (
        client is None
        or client.telegram_user_id is None
        or client.telegram_unreachable_at is not None
    ):
        return
    pending: list[PendingTelegramMessage] = db.info.setdefault(PENDING_KEY, [])
    pending.append(
        PendingTelegramMessage(
            client_id=client.id,
            telegram_user_id=client.telegram_user_id,
            text=text,
        )
    )


async def deliver_client_telegram_message(
    message: PendingTelegramMessage,
    *,
    sessions: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Send one queued message. Never raises — failures are logged.

    This runs after the producing transaction has already committed, so the
    403 write-back needs a session of its own (`sessions`, defaulting to the
    app's factory).
    """
    try:
        await send_message(chat_id=message.telegram_user_id, text=message.text)
    except TelegramForbiddenError as exc:
        # The client blocked the bot. Stop delivering until their next `/start`
        # clears the flag; there is no retry queue in v1.
        logger.info(
            "telegram_notification_blocked",
            client_id=str(message.client_id),
            error=str(exc),
        )
        await _mark_unreachable(message.client_id, sessions=sessions or SessionLocal)
    except TelegramApiError as exc:
        logger.warning(
            "telegram_notification_failed",
            client_id=str(message.client_id),
            error=str(exc),
        )


async def _mark_unreachable(
    client_id: uuid.UUID,
    *,
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    try:
        async with sessions() as session:
            client = await session.get(Client, client_id)
            if client is None or client.telegram_unreachable_at is not None:
                return
            client.telegram_unreachable_at = datetime.now(UTC)
            await session.commit()
    except Exception as exc:  # post-response path must never raise
        logger.warning(
            "telegram_unreachable_flag_failed",
            client_id=str(client_id),
            error=str(exc),
        )


def _dispatch(pending: list[PendingTelegramMessage]) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop (a sync script, a CLI command) — nothing to deliver on.
        return
    for message in pending:
        task = loop.create_task(deliver_client_telegram_message(message))
        _IN_FLIGHT.add(task)
        task.add_done_callback(_IN_FLIGHT.discard)


@event.listens_for(SyncSession, "after_commit")
def _send_after_commit(session: SyncSession) -> None:
    pending = session.info.pop(PENDING_KEY, None)
    if pending:
        _dispatch(pending)


@event.listens_for(SyncSession, "after_soft_rollback")
def _drop_after_rollback(session: SyncSession, previous_transaction: object) -> None:
    # The fan-out never happened — its messages must not be sent either.
    session.info.pop(PENDING_KEY, None)
