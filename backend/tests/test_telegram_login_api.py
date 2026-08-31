"""Client sign-in through the bot: the browser half of the handshake.

The bot half (webhook, contact, linking) lives in `test_telegram_bot_webhook`.
Here: minting a token, what the poll reveals and releases, the fallback code,
the per-IP budgets, and the dev-mode bypass gate.
"""

from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.core.errors import APIError
from app.models.enums import TelegramLoginTokenStatus, UserStatus
from app.modules.access.api import (
    create_login_token,
    issue_login_code,
    poll_login_token,
    prune_expired_telegram_logins,
    redeem_login_code,
)
from app.modules.access.contracts import Client, TelegramLoginCode, TelegramLoginToken
from app.modules.access.routes import REFRESH_COOKIE_NAME
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

TOKEN_URL = "/api/v1/auth/client/telegram/token"
POLL_URL = "/api/v1/auth/client/telegram/poll"
CODE_URL = "/api/v1/auth/client/telegram/code"
DEV_CONFIRM_URL = "/api/v1/auth/client/telegram/dev-confirm"

T0 = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _bot_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "mebelpro_bot")
    monkeypatch.setattr(settings, "TELEGRAM_LOGIN_CODE_PEPPER", "test-pepper")
    monkeypatch.setattr(settings, "TELEGRAM_LOGIN_DEV_MODE", False)


async def _seed_client(
    db: AsyncSession,
    *,
    phone: str,
    name: str = "Ali Valiyev",
    telegram_user_id: int | None = None,
    status: UserStatus = UserStatus.ACTIVE,
) -> Client:
    row = Client(phone=phone, name=name, status=status, telegram_user_id=telegram_user_id)
    db.add(row)
    await db.flush()
    return row


async def test_login_token_carries_a_deep_link_and_a_separate_poll_secret(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    response = await client.post(TOKEN_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["deep_link"] == f"https://t.me/mebelpro_bot?start={body['token']}"
    # Two independent secrets: the deep-link token is public (it rides in the
    # QR), the poll secret is the browser's alone.
    assert body["poll_secret"] != body["token"]
    assert len(body["token"]) >= 32
    assert len(body["poll_secret"]) >= 32

    row = await db_session.scalar(select(TelegramLoginToken))
    assert row is not None
    assert row.status is TelegramLoginTokenStatus.PENDING
    # Neither plaintext is stored.
    assert row.token_hash not in {body["token"], body["poll_secret"]}
    assert row.poll_secret_hash not in {body["token"], body["poll_secret"]}
    assert row.token_hash != row.poll_secret_hash


async def test_poll_reports_progress_then_releases_one_session(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    issued = (await client.post(TOKEN_URL)).json()
    waiting = await client.post(POLL_URL, json={"poll_secret": issued["poll_secret"]})

    # The bot lands and confirms.
    row = await db_session.scalar(select(TelegramLoginToken))
    assert row is not None
    person = await _seed_client(db_session, phone="+998901234567", telegram_user_id=555)
    row.status = TelegramLoginTokenStatus.CONFIRMED
    row.client_id = person.id
    row.confirmed_at = datetime.now(UTC)
    await db_session.flush()

    logged_in = await client.post(POLL_URL, json={"poll_secret": issued["poll_secret"]})
    replayed = await client.post(POLL_URL, json={"poll_secret": issued["poll_secret"]})

    assert waiting.status_code == 200
    assert waiting.json() == {"status": "pending", "expired": False}
    assert logged_in.status_code == 200
    assert logged_in.json()["me"]["principal_type"] == "client"
    assert logged_in.json()["me"]["phone"] == "+998901234567"
    assert logged_in.cookies.get(REFRESH_COOKIE_NAME)
    # Single redemption: the second poll reports `used` and issues nothing.
    assert replayed.json() == {"status": "used", "expired": False}
    assert (await db_session.scalar(select(TelegramLoginToken))).used_at is not None


async def test_the_deep_link_token_can_never_redeem_a_session(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A photographed QR is inert: only the poll secret releases the session."""
    issued = (await client.post(TOKEN_URL)).json()
    row = await db_session.scalar(select(TelegramLoginToken))
    assert row is not None
    person = await _seed_client(db_session, phone="+998901234511", telegram_user_id=77)
    row.status = TelegramLoginTokenStatus.CONFIRMED
    row.client_id = person.id
    await db_session.flush()

    with_token = await client.post(POLL_URL, json={"poll_secret": issued["token"]})

    assert with_token.status_code == 404
    assert with_token.json()["code"] == "invalid_poll_secret"
    assert (await db_session.scalar(select(TelegramLoginToken))).used_at is None


async def test_poll_reports_expiry_so_the_page_can_offer_a_fresh_qr(
    db_session: AsyncSession,
) -> None:
    issued = await create_login_token(db_session, request_ip="203.0.113.5", now=T0)

    result = await poll_login_token(
        db_session,
        poll_secret=issued.poll_secret,
        trace_id="t",
        now=T0 + timedelta(minutes=6),
    )

    assert result.status is TelegramLoginTokenStatus.PENDING
    assert result.expired is True
    assert result.login is None


async def test_login_token_creation_is_budgeted_per_ip(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_LOGIN_TOKENS_PER_IP_PER_HOUR", 2)
    for index in range(2):
        await create_login_token(
            db_session, request_ip="203.0.113.9", now=T0 + timedelta(seconds=index)
        )

    with pytest.raises(APIError) as exc_info:
        await create_login_token(
            db_session, request_ip="203.0.113.9", now=T0 + timedelta(seconds=3)
        )

    assert exc_info.value.code == "login_token_rate_limited"
    assert exc_info.value.details is not None
    assert exc_info.value.details["retry_after_seconds"] > 0
    # A different browser behind a different address is unaffected.
    await create_login_token(db_session, request_ip="203.0.113.10", now=T0 + timedelta(seconds=3))


async def test_login_token_budget_can_be_disabled_for_e2e(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_LOGIN_TOKENS_PER_IP_PER_HOUR", 1)
    monkeypatch.setattr(settings, "TELEGRAM_LOGIN_RATE_LIMITS_ENABLED", False)

    for index in range(3):
        await create_login_token(
            db_session, request_ip="127.0.0.1", now=T0 + timedelta(seconds=index)
        )

    rows = (await db_session.scalars(select(TelegramLoginToken))).all()
    assert len(rows) == 3


async def test_request_ip_is_the_hop_a_trusted_proxy_vouches_for(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    response = await client.post(TOKEN_URL, headers={"X-Forwarded-For": "203.0.113.10, 10.0.0.1"})

    assert response.status_code == 200
    row = await db_session.scalar(select(TelegramLoginToken))
    assert row is not None
    # Right-most untrusted hop; the left-most entry is client-supplied.
    assert row.request_ip == "10.0.0.1"


async def test_fallback_code_logs_the_client_in_once(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    person = await _seed_client(db_session, phone="+998907654321", telegram_user_id=42)
    code = await issue_login_code(db_session, client=person)

    logged_in = await client.post(CODE_URL, json={"code": code})
    replayed = await client.post(CODE_URL, json={"code": code})

    assert logged_in.status_code == 200
    assert logged_in.json()["me"]["phone"] == "+998907654321"
    assert logged_in.cookies.get(REFRESH_COOKIE_NAME)
    # Burned on first success — a reused code is indistinguishable from a wrong one.
    assert replayed.status_code == 400
    assert replayed.json()["code"] == "invalid_code"


@pytest.mark.parametrize(
    "case",
    ["unknown", "expired", "consumed", "malformed"],
)
async def test_every_bad_code_answers_the_same_generic_error(
    client: AsyncClient,
    db_session: AsyncSession,
    case: str,
) -> None:
    """No oracle: unknown, expired, used, and malformed are one answer."""
    person = await _seed_client(db_session, phone="+998900000001", telegram_user_id=9)
    code = await issue_login_code(db_session, client=person)
    if case == "unknown":
        code = "000000" if code != "000000" else "111111"
    elif case == "malformed":
        code = "12ab5"
    else:
        row = await db_session.scalar(select(TelegramLoginCode))
        assert row is not None
        if case == "expired":
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        else:
            row.consumed_at = datetime.now(UTC)
        await db_session.flush()

    response = await client.post(CODE_URL, json={"code": code})

    assert response.status_code == 400
    assert response.json() == {
        "code": "invalid_code",
        "message": "Invalid code",
        "trace_id": response.json()["trace_id"],
    }


async def test_code_redeem_is_throttled_per_ip_with_a_retry_hint(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_LOGIN_CODE_REDEEMS_PER_IP", 3)

    for _ in range(3):
        assert (await client.post(CODE_URL, json={"code": "123456"})).status_code == 400

    blocked = await client.post(CODE_URL, json={"code": "123456"})

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "login_code_rate_limited"
    assert blocked.json()["details"]["retry_after_seconds"] >= 1


async def test_blocked_client_cannot_redeem_a_live_code(
    db_session: AsyncSession,
) -> None:
    person = await _seed_client(db_session, phone="+998900000002", telegram_user_id=11)
    code = await issue_login_code(db_session, client=person)
    person.status = UserStatus.BLOCKED
    await db_session.flush()

    with pytest.raises(APIError) as exc_info:
        await redeem_login_code(db_session, code=code, request_ip="203.0.113.1", trace_id="t")

    # Generic, and the code is burned anyway — a blocked account is not an oracle.
    assert exc_info.value.code == "invalid_code"


async def test_dev_confirm_is_absent_unless_dev_mode_is_on(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await client.post(TOKEN_URL)

    off = await client.post(DEV_CONFIRM_URL, json={"phone": "+998901112233", "name": "Dev"})

    assert off.status_code == 404
    assert off.json()["code"] == "not_found"

    monkeypatch.setattr(settings, "TELEGRAM_LOGIN_DEV_MODE", True)
    on = await client.post(DEV_CONFIRM_URL, json={"phone": "+998901112233", "name": "Dev"})
    assert on.status_code == 204


async def test_dev_confirm_registers_the_phone_and_the_poll_logs_in(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The E2E path: no bot, no webhook — the login page's poll still succeeds."""
    monkeypatch.setattr(settings, "TELEGRAM_LOGIN_DEV_MODE", True)
    issued = (await client.post(TOKEN_URL)).json()

    confirmed = await client.post(
        DEV_CONFIRM_URL,
        json={"token": issued["token"], "phone": "+998905550001", "name": "E2E Client"},
    )
    logged_in = await client.post(POLL_URL, json={"poll_secret": issued["poll_secret"]})

    assert confirmed.status_code == 204
    assert logged_in.status_code == 200
    assert logged_in.json()["me"]["name"] == "E2E Client"
    assert logged_in.json()["me"]["phone"] == "+998905550001"
    person = await db_session.scalar(select(Client))
    assert person is not None
    # Dev mode skips Telegram entirely, so no account is linked.
    assert person.telegram_user_id is None


async def test_dev_confirm_needs_a_name_for_an_unknown_phone(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_LOGIN_DEV_MODE", True)
    await client.post(TOKEN_URL)

    response = await client.post(DEV_CONFIRM_URL, json={"phone": "+998905550002"})

    assert response.status_code == 400
    assert response.json()["code"] == "name_required"


async def test_prune_drops_only_rows_past_the_retention_window(
    db_session: AsyncSession,
) -> None:
    """Retention must outlast the 24 h budget window, or pruning refills budgets."""
    now = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
    person = await _seed_client(db_session, phone="+998900000003", telegram_user_id=12)
    for age in (timedelta(days=8), timedelta(hours=23)):
        db_session.add(
            TelegramLoginToken(
                token_hash=f"t{age}",
                poll_secret_hash=f"p{age}",
                status=TelegramLoginTokenStatus.USED,
                request_ip="203.0.113.9",
                expires_at=now - age + timedelta(minutes=5),
                created_at=now - age,
            )
        )
        db_session.add(
            TelegramLoginCode(
                code_hash=f"c{age}",
                client_id=person.id,
                expires_at=now - age + timedelta(minutes=5),
                created_at=now - age,
            )
        )
    await db_session.flush()

    tokens, codes = await prune_expired_telegram_logins(db_session, now=now)

    assert (tokens, codes) == (1, 1)
    assert len((await db_session.scalars(select(TelegramLoginToken))).all()) == 1
    assert len((await db_session.scalars(select(TelegramLoginCode))).all()) == 1
