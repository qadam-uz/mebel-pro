"""Telegram delivery of client order notifications.

The inbox is the source of truth; the bot message is a pointer to it. So the
tests here pin the two things that would actually hurt: who gets skipped, and
that a 403 stops the platform re-sending into a blocked chat forever.
"""

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.core.config import settings
from app.models import Base
from app.models.enums import AuthenticatedPrincipalType, UserStatus
from app.modules.access.contracts import Client
from app.modules.sales.contracts import Order
from app.modules.support.api import (
    PendingTelegramMessage,
    deliver_client_telegram_message,
    queue_client_order_message,
    render_order_message,
)
from app.modules.support.contracts import Notification
from app.modules.support.telegram_delivery import PENDING_KEY
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.test_sales_api import _auth, _placed_order

ORDER_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")


@pytest.fixture(autouse=True)
def _bot_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(settings, "CLIENT_APP_BASE_URL", "https://app.mebel-pro.uz")


def _mock_bot_api(
    monkeypatch: pytest.MonkeyPatch,
    handler: "httpx._types.SyncHandler",  # type: ignore[name-defined]
) -> list[httpx.Request]:
    """Replace the Bot API connection, keeping the real response handling."""
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(wrapped))

    monkeypatch.setattr("app.core.telegram.http_client", factory)
    return seen


def _make_client(
    *,
    phone: str = "+998901234567",
    telegram_user_id: int | None = 5150,
    unreachable: bool = False,
) -> Client:
    return Client(
        phone=phone,
        name="Ali Valiyev",
        status=UserStatus.ACTIVE,
        telegram_user_id=telegram_user_id,
        telegram_unreachable_at=datetime.now(UTC) if unreachable else None,
    )


async def _seed_client(db: AsyncSession, **kwargs: Any) -> Client:
    row = _make_client(**kwargs)
    db.add(row)
    await db.flush()
    return row


@pytest.fixture
async def delivery_db(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A committed, file-backed DB.

    Delivery runs *after* the producing transaction, so the 403 write-back
    opens a session of its own — which only means anything against a database
    that outlives one transaction.
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'delivery.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _committed_client(sessions: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with sessions() as session:
        row = _make_client()
        session.add(row)
        await session.commit()
        return row.id


async def _stored_client(
    sessions: async_sessionmaker[AsyncSession], client_id: uuid.UUID
) -> Client:
    async with sessions() as session:
        row = await session.get(Client, client_id)
        assert row is not None
        return row


def test_the_bot_message_is_the_inbox_sentence_plus_an_order_link() -> None:
    text = render_order_message(event_code="order.ready", order_number="A-1042", order_id=ORDER_ID)

    assert text == (
        f"Buyurtma tayyor — Buyurtma № A-1042\nhttps://app.mebel-pro.uz/c/orders/{ORDER_ID}"
    )
    # An event with no client-facing sentence delivers nothing at all.
    assert (
        render_order_message(event_code="order.cutting", order_number="A-1", order_id=ORDER_ID)
        is None
    )


@pytest.mark.parametrize(
    ("telegram_user_id", "unreachable", "queued"),
    [
        pytest.param(5150, False, True, id="linked-and-reachable"),
        pytest.param(None, False, False, id="never-signed-in"),
        pytest.param(5150, True, False, id="blocked-the-bot"),
    ],
)
async def test_only_linked_reachable_clients_are_queued(
    db_session: AsyncSession,
    telegram_user_id: int | None,
    unreachable: bool,
    queued: bool,
) -> None:
    person = await _seed_client(
        db_session, telegram_user_id=telegram_user_id, unreachable=unreachable
    )

    await queue_client_order_message(
        db_session,
        client_id=person.id,
        event_code="order.confirmed",
        order_id=ORDER_ID,
        order_number="A-7",
    )

    assert bool(db_session.info.get(PENDING_KEY)) is queued


async def test_nothing_is_queued_while_the_bot_is_unconfigured(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "")
    person = await _seed_client(db_session)

    await queue_client_order_message(
        db_session,
        client_id=person.id,
        event_code="order.confirmed",
        order_id=ORDER_ID,
        order_number="A-7",
    )

    assert db_session.info.get(PENDING_KEY) is None


async def test_a_403_marks_the_client_unreachable_so_delivery_stops(
    delivery_db: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The client blocked the bot. No retry queue — just stop until they return."""
    client_id = await _committed_client(delivery_db)
    requests = _mock_bot_api(
        monkeypatch,
        lambda request: httpx.Response(403, json={"ok": False, "description": "bot was blocked"}),
    )

    await deliver_client_telegram_message(
        PendingTelegramMessage(client_id=client_id, telegram_user_id=5150, text="hi"),
        sessions=delivery_db,
    )

    assert len(requests) == 1
    assert requests[0].url.path.endswith("/sendMessage")
    assert (await _stored_client(delivery_db, client_id)).telegram_unreachable_at is not None


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(httpx.Response(500, text="boom"), id="server-error"),
        pytest.param(httpx.Response(200, json={"ok": False, "description": "nope"}), id="not-ok"),
    ],
)
async def test_a_non_403_failure_is_swallowed_and_leaves_the_link_intact(
    delivery_db: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    response: httpx.Response,
) -> None:
    """A transient Bot API failure must not read as "the client blocked us"."""
    client_id = await _committed_client(delivery_db)
    _mock_bot_api(monkeypatch, lambda request: response)

    await deliver_client_telegram_message(
        PendingTelegramMessage(client_id=client_id, telegram_user_id=5150, text="hi"),
        sessions=delivery_db,
    )

    assert (await _stored_client(delivery_db, client_id)).telegram_unreachable_at is None


async def test_a_successful_send_leaves_the_client_alone(
    delivery_db: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_id = await _committed_client(delivery_db)
    requests = _mock_bot_api(
        monkeypatch, lambda request: httpx.Response(200, json={"ok": True, "result": {}})
    )

    await deliver_client_telegram_message(
        PendingTelegramMessage(client_id=client_id, telegram_user_id=5150, text="Buyurtma tayyor"),
        sessions=delivery_db,
    )

    assert json.loads(requests[0].content) == {"chat_id": 5150, "text": "Buyurtma tayyor"}
    assert (await _stored_client(delivery_db, client_id)).telegram_unreachable_at is None


async def test_an_order_status_change_queues_the_same_sentence_as_the_inbox_row(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The wiring proof: one real transition, one inbox row, one queued message."""
    order, _, owner_access, _, _, _ = await _placed_order(client, db_session)
    placed = await db_session.get(Order, uuid.UUID(str(order["id"])))
    assert placed is not None
    order_client = await db_session.get(Client, placed.client_id)
    assert order_client is not None
    order_client.telegram_user_id = 777001
    await db_session.flush()

    approved = await client.post(
        f"/api/v1/workshop/orders/{order['id']}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )

    assert approved.status_code == 200
    row = await db_session.scalar(
        select(Notification).where(
            Notification.recipient_type == AuthenticatedPrincipalType.CLIENT,
            Notification.entity_id == uuid.UUID(order["id"]),
        )
    )
    assert row is not None and row.event_code == "order.confirmed"
    pending: list[Any] = db_session.info[PENDING_KEY]
    assert len(pending) == 1
    assert pending[0].telegram_user_id == 777001
    assert pending[0].text.startswith(
        f"Buyurtma tayyorlanmoqda — Buyurtma № {row.payload['order_number']}"
    )
