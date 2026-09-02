"""The bot half of client sign-in, driven through the real webhook.

Every test posts a Telegram update at `/api/v1/telegram/webhook` and asserts on
two things: what the handshake row became, and what the bot said back. The only
faked boundary is the Bot API HTTP call itself.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.core.config import settings
from app.models.enums import TelegramLoginTokenStatus, UserStatus
from app.modules.access.api import create_login_token
from app.modules.access.contracts import Client, TelegramLoginCode, TelegramLoginToken
from app.modules.access.telegram_bot import (
    ASK_CONTACT_TEXT,
    BLOCKED_TEXT,
    CONFIRMED_TEXT,
    DECLINED_TEXT,
    EXPIRED_TEXT,
    FOREIGN_CONTACT_TEXT,
    HELP_TEXT,
    LOGIN_CODE_ACTION,
)
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

WEBHOOK_URL = "/api/v1/telegram/webhook"
SECRET = "webhook-secret"
HEADERS = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
SENDER_ID = 5150
SENDER = {"id": SENDER_ID, "first_name": "Ali", "last_name": "Valiyev"}


@pytest.fixture(autouse=True)
def _bot_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "mebelpro_bot")
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(settings, "TELEGRAM_LOGIN_CODE_PEPPER", "test-pepper")


@pytest.fixture
def bot_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Capture Bot API traffic at the HTTP seam, payload building included."""
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_call(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append((method, payload))
        return {}

    monkeypatch.setattr("app.core.telegram.call", fake_call)
    return calls


def _texts(calls: list[tuple[str, dict[str, Any]]]) -> list[str]:
    return [payload["text"] for method, payload in calls if method == "sendMessage"]


def _last_markup(calls: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    sends = [payload for method, payload in calls if method == "sendMessage"]
    markup = sends[-1].get("reply_markup")
    return markup if isinstance(markup, dict) else {}


def _start(token: str | None = None, *, sender: dict[str, Any] | None = None) -> dict[str, Any]:
    text = f"/start {token}" if token else "/start"
    person = sender or SENDER
    return {
        "message": {"from": person, "chat": {"id": person["id"]}, "text": text},
    }


def _callback(data: str, *, sender: dict[str, Any] | None = None) -> dict[str, Any]:
    person = sender or SENDER
    return {
        "callback_query": {
            "id": "cb-1",
            "from": person,
            "message": {"chat": {"id": person["id"]}},
            "data": data,
        }
    }


def _contact(
    phone: str, *, owner_id: int | None = None, sender: dict[str, Any] | None = None
) -> dict[str, Any]:
    person = sender or SENDER
    return {
        "message": {
            "from": person,
            "chat": {"id": person["id"]},
            "contact": {
                "phone_number": phone,
                "user_id": person["id"] if owner_id is None else owner_id,
            },
        }
    }


async def _seed_client(
    db: AsyncSession,
    *,
    phone: str,
    name: str = "Existing Client",
    telegram_user_id: int | None = None,
    status: UserStatus = UserStatus.ACTIVE,
) -> Client:
    row = Client(phone=phone, name=name, status=status, telegram_user_id=telegram_user_id)
    db.add(row)
    await db.flush()
    return row


async def _mint(db: AsyncSession) -> str:
    issued = await create_login_token(db, request_ip="203.0.113.4", device_info={})
    return issued.token


async def _token_row(db: AsyncSession) -> TelegramLoginToken:
    row = await db.scalar(select(TelegramLoginToken))
    assert row is not None
    await db.refresh(row)
    return row


# --- Webhook authentication --------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="missing"),
        pytest.param({"X-Telegram-Bot-Api-Secret-Token": "wrong"}, id="wrong"),
        pytest.param({"X-Telegram-Bot-Api-Secret-Token": ""}, id="empty"),
    ],
)
async def test_webhook_refuses_anything_but_the_configured_secret(
    client: AsyncClient,
    bot_calls: list[tuple[str, dict[str, Any]]],
    headers: dict[str, str],
) -> None:
    response = await client.post(WEBHOOK_URL, json=_start(), headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "invalid_webhook_secret"
    assert bot_calls == []


async def test_webhook_refuses_everything_while_the_secret_is_unset(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unconfigured webhook must fail closed, not accept every caller."""
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")

    response = await client.post(
        WEBHOOK_URL, json=_start(), headers={"X-Telegram-Bot-Api-Secret-Token": ""}
    )

    assert response.status_code == 403


# --- /start ------------------------------------------------------------------


async def test_bare_start_offers_help_and_the_code_button(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    await _seed_client(
        db_session,
        phone="+998901234567",
        telegram_user_id=SENDER_ID,
    )
    person = await db_session.scalar(select(Client))
    assert person is not None
    person.telegram_unreachable_at = datetime.now(UTC)
    await db_session.flush()

    response = await client.post(WEBHOOK_URL, json=_start(), headers=HEADERS)

    assert response.status_code == 204
    assert _texts(bot_calls) == [HELP_TEXT]
    buttons = _last_markup(bot_calls)["inline_keyboard"][0]
    assert buttons[0]["callback_data"] == LOGIN_CODE_ACTION
    # Pressing Start un-blocks the bot by definition — the stale 403 flag clears.
    await db_session.refresh(person)
    assert person.telegram_unreachable_at is None


async def test_start_with_a_known_account_asks_for_one_confirmation(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    await _seed_client(db_session, phone="+998901234567", telegram_user_id=SENDER_ID)
    token = await _mint(db_session)

    response = await client.post(WEBHOOK_URL, json=_start(token), headers=HEADERS)

    assert response.status_code == 204
    row = await _token_row(db_session)
    assert row.status is TelegramLoginTokenStatus.STARTED
    assert row.telegram_user_id == SENDER_ID
    assert "Tasdiqlaysizmi?" in _texts(bot_calls)[0]
    labels = [button["text"] for button in _last_markup(bot_calls)["inline_keyboard"][0]]
    assert labels == ["Tasdiqlash", "Bekor qilish"]


async def test_start_with_an_expired_token_says_so_and_offers_the_code(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    token = await _mint(db_session)
    row = await _token_row(db_session)
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()

    await client.post(WEBHOOK_URL, json=_start(token), headers=HEADERS)

    assert _texts(bot_calls) == [EXPIRED_TEXT]
    assert (await _token_row(db_session)).status is TelegramLoginTokenStatus.PENDING


async def test_blocked_account_is_told_so_and_the_token_dies(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    await _seed_client(
        db_session,
        phone="+998901234567",
        telegram_user_id=SENDER_ID,
        status=UserStatus.BLOCKED,
    )
    token = await _mint(db_session)

    await client.post(WEBHOOK_URL, json=_start(token), headers=HEADERS)

    assert _texts(bot_calls) == [BLOCKED_TEXT]
    assert (await _token_row(db_session)).status is TelegramLoginTokenStatus.DECLINED


# --- Confirm / decline -------------------------------------------------------


async def test_known_account_confirms_and_the_browser_can_redeem(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    person = await _seed_client(db_session, phone="+998901234567", telegram_user_id=SENDER_ID)
    token = await _mint(db_session)
    await client.post(WEBHOOK_URL, json=_start(token), headers=HEADERS)
    row = await _token_row(db_session)

    await client.post(WEBHOOK_URL, json=_callback(f"confirm:{row.id}"), headers=HEADERS)

    confirmed = await _token_row(db_session)
    assert confirmed.status is TelegramLoginTokenStatus.CONFIRMED
    assert confirmed.client_id == person.id
    assert confirmed.confirmed_at is not None
    assert _texts(bot_calls)[-1] == CONFIRMED_TEXT


async def test_declining_ends_the_handshake(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    await _seed_client(db_session, phone="+998901234567", telegram_user_id=SENDER_ID)
    token = await _mint(db_session)
    await client.post(WEBHOOK_URL, json=_start(token), headers=HEADERS)
    row = await _token_row(db_session)

    await client.post(WEBHOOK_URL, json=_callback(f"decline:{row.id}"), headers=HEADERS)

    assert (await _token_row(db_session)).status is TelegramLoginTokenStatus.DECLINED
    assert _texts(bot_calls)[-1] == DECLINED_TEXT


async def test_another_account_cannot_answer_someone_elses_confirmation(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    await _seed_client(db_session, phone="+998901234567", telegram_user_id=SENDER_ID)
    token = await _mint(db_session)
    await client.post(WEBHOOK_URL, json=_start(token), headers=HEADERS)
    row = await _token_row(db_session)
    intruder = {"id": 9999, "first_name": "Mallory"}

    await client.post(
        WEBHOOK_URL,
        json=_callback(f"confirm:{row.id}", sender=intruder),
        headers=HEADERS,
    )

    assert (await _token_row(db_session)).status is TelegramLoginTokenStatus.STARTED
    assert _texts(bot_calls)[-1] == EXPIRED_TEXT


# --- The contact step --------------------------------------------------------


async def _reach_contact_step(client: AsyncClient, db_session: AsyncSession) -> None:
    token = await _mint(db_session)
    await client.post(WEBHOOK_URL, json=_start(token), headers=HEADERS)
    row = await _token_row(db_session)
    await client.post(WEBHOOK_URL, json=_callback(f"confirm:{row.id}"), headers=HEADERS)


async def test_an_unknown_account_is_asked_for_its_own_number(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    await _reach_contact_step(client, db_session)

    assert (await _token_row(db_session)).status is TelegramLoginTokenStatus.AWAITING_CONTACT
    assert _texts(bot_calls)[-1] == ASK_CONTACT_TEXT
    assert _last_markup(bot_calls)["keyboard"][0][0]["request_contact"] is True


async def test_a_forwarded_contact_is_refused(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """Only the sender's own contact proves possession of the number."""
    await _reach_contact_step(client, db_session)

    await client.post(
        WEBHOOK_URL,
        json=_contact("+998907654321", owner_id=424242),
        headers=HEADERS,
    )

    assert _texts(bot_calls)[-1] == FOREIGN_CONTACT_TEXT
    assert (await _token_row(db_session)).status is TelegramLoginTokenStatus.AWAITING_CONTACT
    assert await db_session.scalar(select(Client)) is None


async def test_an_unknown_number_registers_a_client_named_from_the_profile(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    await _reach_contact_step(client, db_session)

    await client.post(WEBHOOK_URL, json=_contact("998907654321"), headers=HEADERS)

    person = await db_session.scalar(select(Client))
    assert person is not None
    assert person.phone == "+998907654321"
    assert person.name == "Ali Valiyev"
    assert person.telegram_user_id == SENDER_ID
    assert person.status is UserStatus.ACTIVE
    row = await _token_row(db_session)
    assert row.status is TelegramLoginTokenStatus.CONFIRMED
    assert row.client_id == person.id
    assert _texts(bot_calls)[-1] == CONFIRMED_TEXT


async def test_a_long_telegram_name_is_trimmed_to_the_column_limit(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    long_sender = {"id": SENDER_ID, "first_name": "A" * 60, "last_name": "B" * 60}
    token = await _mint(db_session)
    await client.post(WEBHOOK_URL, json=_start(token, sender=long_sender), headers=HEADERS)
    row = await _token_row(db_session)
    await client.post(
        WEBHOOK_URL, json=_callback(f"confirm:{row.id}", sender=long_sender), headers=HEADERS
    )

    await client.post(
        WEBHOOK_URL, json=_contact("+998907654322", sender=long_sender), headers=HEADERS
    )

    person = await db_session.scalar(select(Client))
    assert person is not None
    assert len(person.name) == 80


async def test_a_staff_created_walk_in_row_is_claimed_not_duplicated(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    existing = await _seed_client(db_session, phone="+998907654321", name="Counter Name")
    await _reach_contact_step(client, db_session)

    await client.post(WEBHOOK_URL, json=_contact("+998907654321"), headers=HEADERS)

    people = (await db_session.scalars(select(Client))).all()
    assert len(people) == 1
    await db_session.refresh(existing)
    assert existing.telegram_user_id == SENDER_ID
    # The staff-entered name stands; the profile is the client's to edit.
    assert existing.name == "Counter Name"
    assert (await _token_row(db_session)).client_id == existing.id


async def test_a_fresh_contact_relinks_a_number_to_its_new_telegram_account(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """Possession of the number is the identity: the new account wins."""
    owner = await _seed_client(
        db_session, phone="+998907654321", name="Same Number", telegram_user_id=111
    )
    stale = await _seed_client(
        db_session, phone="+998901110000", name="Old Owner", telegram_user_id=SENDER_ID
    )
    await _reach_contact_step(client, db_session)

    await client.post(WEBHOOK_URL, json=_contact("+998907654321"), headers=HEADERS)

    await db_session.refresh(owner)
    await db_session.refresh(stale)
    assert owner.telegram_user_id == SENDER_ID
    # The id is unique: the row that used to hold it is unbound, not duplicated.
    assert stale.telegram_user_id is None
    assert (await _token_row(db_session)).status is TelegramLoginTokenStatus.CONFIRMED


async def test_a_blocked_number_is_refused_at_the_contact_step(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    blocked = await _seed_client(
        db_session,
        phone="+998907654321",
        name="Blocked",
        status=UserStatus.BLOCKED,
    )
    await _reach_contact_step(client, db_session)

    await client.post(WEBHOOK_URL, json=_contact("+998907654321"), headers=HEADERS)

    assert _texts(bot_calls)[-1] == BLOCKED_TEXT
    assert (await _token_row(db_session)).status is TelegramLoginTokenStatus.DECLINED
    await db_session.refresh(blocked)
    assert blocked.telegram_user_id is None


# --- The fallback code -------------------------------------------------------


async def test_the_code_button_issues_a_code_to_a_known_account(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    person = await _seed_client(db_session, phone="+998901234567", telegram_user_id=SENDER_ID)

    await client.post(WEBHOOK_URL, json=_callback(LOGIN_CODE_ACTION), headers=HEADERS)

    row = await db_session.scalar(select(TelegramLoginCode))
    assert row is not None
    assert row.client_id == person.id
    assert row.consumed_at is None
    shown = _texts(bot_calls)[-1]
    assert "Kirish kodi: " in shown
    code = shown.split("Kirish kodi: ")[1].split("\n")[0]
    assert len(code) == 6 and code.isdigit()
    # Only the hash is stored.
    assert code not in row.code_hash


async def test_the_code_button_identifies_an_unknown_account_first(
    client: AsyncClient,
    db_session: AsyncSession,
    bot_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """No deep link in play — the contact share alone identifies, then a code."""
    await client.post(WEBHOOK_URL, json=_callback(LOGIN_CODE_ACTION), headers=HEADERS)
    assert _texts(bot_calls)[-1] == ASK_CONTACT_TEXT
    assert await db_session.scalar(select(TelegramLoginCode)) is None

    await client.post(WEBHOOK_URL, json=_contact("+998907654321"), headers=HEADERS)

    person = await db_session.scalar(select(Client))
    assert person is not None
    assert person.telegram_user_id == SENDER_ID
    row = await db_session.scalar(select(TelegramLoginCode))
    assert row is not None
    assert row.client_id == person.id
    assert "Kirish kodi: " in _texts(bot_calls)[-1]
