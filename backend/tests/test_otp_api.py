from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.core.errors import APIError
from app.modules.access.api import (
    TelegramDeliveryError,
    prune_expired_otp_challenges,
    request_otp_code,
    resolve_client_ip,
)
from app.modules.access.contracts import PhoneVerificationChallenge
from app.modules.access.routes import REFRESH_COOKIE_NAME, get_otp_sender
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import BoundaryHarness


@dataclass
class FakeOtpSender:
    sent: list[tuple[str, str, int]] = field(default_factory=list)

    async def send_code(self, *, phone: str, code: str, ttl_seconds: int) -> None:
        self.sent.append((phone, code, ttl_seconds))


class FailingOtpSender:
    async def send_code(self, *, phone: str, code: str, ttl_seconds: int) -> None:
        raise TelegramDeliveryError("unreachable")


async def test_client_dev_code_registers_new_client_without_telegram(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = FakeOtpSender()
    monkeypatch.setattr(settings, "OTP_DEV_CODES", ["000000"])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    from app.main import app

    app.dependency_overrides[get_otp_sender] = lambda: sender

    request = await client.post(
        "/api/v1/auth/client/otp/request",
        json={"phone": "+998901234567"},
    )
    needs_name = await client.post(
        "/api/v1/auth/client/otp/verify",
        json={"phone": "+998901234567", "code": "000000"},
    )
    login = await client.post(
        "/api/v1/auth/client/otp/verify",
        json={"phone": "+998901234567", "code": "000000", "name": "Ali Valiyev"},
    )

    assert request.status_code == 200
    assert request.json()["phone"] == "+998901234567"
    assert request.json()["resend_after_seconds"] == 60
    assert needs_name.status_code == 200
    assert needs_name.json() == {"is_new": True}
    assert login.status_code == 200
    assert login.cookies.get(REFRESH_COOKIE_NAME)
    assert login.json()["me"]["principal_type"] == "client"
    assert login.json()["me"]["name"] == "Ali Valiyev"
    assert login.json()["me"]["phone"] == "+998901234567"


async def test_client_verify_rejects_blank_name_on_registration(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A supplied-but-blank name must raise name_required, not silently re-prompt (CB-79)."""
    sender = FakeOtpSender()
    monkeypatch.setattr(settings, "OTP_DEV_CODES", ["000000"])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    from app.main import app

    app.dependency_overrides[get_otp_sender] = lambda: sender

    await client.post("/api/v1/auth/client/otp/request", json={"phone": "+998903334455"})

    # No name → first step still asks for the name (is_new), no error.
    needs_name = await client.post(
        "/api/v1/auth/client/otp/verify",
        json={"phone": "+998903334455", "code": "000000"},
    )
    assert needs_name.status_code == 200
    assert needs_name.json() == {"is_new": True}

    # A whitespace-only name is an explicit failure, not another is_new.
    blank = await client.post(
        "/api/v1/auth/client/otp/verify",
        json={"phone": "+998903334455", "code": "000000", "name": "   "},
    )
    assert blank.status_code == 400
    assert blank.json()["code"] == "name_required"
    assert sender.sent == []


async def test_telegram_request_stores_hmac_and_trusted_forwarded_ip(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = FakeOtpSender()
    monkeypatch.setattr(settings, "OTP_DEV_CODES", [])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    from app.main import app

    app.dependency_overrides[get_otp_sender] = lambda: sender

    response = await client.post(
        "/api/v1/auth/client/otp/request",
        json={"phone": "+998901111111"},
        headers={"X-Forwarded-For": "203.0.113.10, 10.0.0.1"},
    )

    assert response.status_code == 200
    assert len(sender.sent) == 1
    assert sender.sent[0][0] == "+998901111111"
    assert len(sender.sent[0][1]) == 6
    challenge = await db_session.scalar(select(PhoneVerificationChallenge))
    assert challenge is not None
    # Right-most untrusted hop: 10.0.0.1 is what the trusted peer vouches for;
    # the left-most 203.0.113.10 is client-supplied and forgeable.
    assert challenge.request_ip == "10.0.0.1"
    assert challenge.code_hash != sender.sent[0][1]
    assert len(challenge.code_hash) == 64

    login = await client.post(
        "/api/v1/auth/client/otp/verify",
        json={"phone": "+998901111111", "code": sender.sent[0][1], "name": "Telegram User"},
    )

    assert login.status_code == 200
    assert login.json()["me"]["phone"] == "+998901111111"


async def test_otp_wrong_code_burns_challenge_after_five_attempts(
    boundary_client: BoundaryHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Attempt counting must survive the per-request rollback on APIError (CB-133).

    Runs against the real commit/rollback boundary: each wrong guess is its own
    request/session, so the counter only advances if the service persists it.
    """
    monkeypatch.setattr(settings, "OTP_DEV_CODES", ["000000"])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    http = boundary_client.http
    await http.post("/api/v1/auth/client/otp/request", json={"phone": "+998902222222"})

    for attempt in range(1, 5):
        response = await http.post(
            "/api/v1/auth/client/otp/verify",
            json={"phone": "+998902222222", "code": "111111"},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_code"
        assert response.json()["details"]["attempts_remaining"] == 5 - attempt

    burned = await http.post(
        "/api/v1/auth/client/otp/verify",
        json={"phone": "+998902222222", "code": "111111"},
    )
    correct_after_burn = await http.post(
        "/api/v1/auth/client/otp/verify",
        json={"phone": "+998902222222", "code": "000000", "name": "Late User"},
    )

    assert burned.status_code == 400
    assert burned.json()["code"] == "too_many_attempts"
    assert correct_after_burn.status_code == 400
    assert correct_after_burn.json()["code"] == "invalid_code"

    async with boundary_client.sessions() as db:
        challenge = await db.scalar(select(PhoneVerificationChallenge))
        assert challenge is not None
        assert challenge.attempt_count == 5
        assert challenge.consumed_at is not None


async def test_otp_wrong_attempt_count_persists_across_requests(
    boundary_client: BoundaryHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The narrowest pin on CB-133: one wrong guess → attempt_count == 1 in the DB."""
    monkeypatch.setattr(settings, "OTP_DEV_CODES", ["000000"])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    http = boundary_client.http
    await http.post("/api/v1/auth/client/otp/request", json={"phone": "+998905555555"})

    response = await http.post(
        "/api/v1/auth/client/otp/verify",
        json={"phone": "+998905555555", "code": "111111"},
    )

    assert response.status_code == 400
    async with boundary_client.sessions() as db:
        challenge = await db.scalar(select(PhoneVerificationChallenge))
        assert challenge is not None
        assert challenge.attempt_count == 1
        assert challenge.consumed_at is None


async def test_otp_expired_code_burn_persists(
    boundary_client: BoundaryHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An expired-code attempt burns the challenge durably (CB-133)."""
    monkeypatch.setattr(settings, "OTP_DEV_CODES", ["000000"])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    http = boundary_client.http
    await http.post("/api/v1/auth/client/otp/request", json={"phone": "+998906666666"})
    async with boundary_client.sessions() as db:
        challenge = await db.scalar(select(PhoneVerificationChallenge))
        assert challenge is not None
        challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()

    expired = await http.post(
        "/api/v1/auth/client/otp/verify",
        json={"phone": "+998906666666", "code": "000000"},
    )

    assert expired.status_code == 400
    assert expired.json()["code"] == "code_expired"
    async with boundary_client.sessions() as db:
        challenge = await db.scalar(select(PhoneVerificationChallenge))
        assert challenge is not None
        assert challenge.consumed_at is not None


async def test_otp_delivery_failure_burns_row_and_counts_toward_limits(
    boundary_client: BoundaryHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed Telegram send must consume rate-limit budget, not probe for free.

    The undelivered challenge is persisted burned: it triggers the resend
    cooldown, counts toward the send caps, and can never be verified.
    """
    monkeypatch.setattr(settings, "OTP_DEV_CODES", [])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    from app.main import app

    app.dependency_overrides[get_otp_sender] = FailingOtpSender
    http = boundary_client.http

    failed = await http.post("/api/v1/auth/client/otp/request", json={"phone": "+998907777777"})
    assert failed.status_code == 400
    assert failed.json()["code"] == "phone_unreachable_on_telegram"

    async with boundary_client.sessions() as db:
        challenge = await db.scalar(select(PhoneVerificationChallenge))
        assert challenge is not None
        assert challenge.consumed_at is not None

    retry = await http.post("/api/v1/auth/client/otp/request", json={"phone": "+998907777777"})
    assert retry.status_code == 429
    assert retry.json()["code"] == "code_send_rate_limited"

    verify = await http.post(
        "/api/v1/auth/client/otp/verify",
        json={"phone": "+998907777777", "code": "123456"},
    )
    assert verify.status_code == 400
    assert verify.json()["code"] == "invalid_code"


async def test_otp_resend_cooldown_is_durable(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OTP_DEV_CODES", ["000000"])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    sender = FakeOtpSender()
    now = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
    await request_otp_code(
        db_session,
        phone="+998903333333",
        request_ip="198.51.100.1",
        sender=sender,
        now=now,
    )

    with pytest.raises(APIError) as exc_info:
        await request_otp_code(
            db_session,
            phone="+998903333333",
            request_ip="198.51.100.1",
            sender=sender,
            now=now + timedelta(seconds=10),
        )

    assert exc_info.value.code == "code_send_rate_limited"
    assert exc_info.value.details == {"retry_after_seconds": 50}


async def test_otp_send_limits_can_be_disabled_for_e2e(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OTP_DEV_CODES", ["000000"])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    monkeypatch.setattr(settings, "OTP_RATE_LIMITS_ENABLED", False)
    sender = FakeOtpSender()
    now = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)

    await request_otp_code(
        db_session,
        phone="+998904444444",
        request_ip="198.51.100.3",
        sender=sender,
        now=now,
    )
    await request_otp_code(
        db_session,
        phone="+998904444444",
        request_ip="198.51.100.3",
        sender=sender,
        now=now + timedelta(seconds=10),
    )

    rows = (
        await db_session.scalars(
            select(PhoneVerificationChallenge).where(
                PhoneVerificationChallenge.phone == "+998904444444"
            )
        )
    ).all()
    assert len(rows) == 2


async def test_otp_ip_hourly_limit_is_durable(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OTP_DEV_CODES", ["000000"])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    sender = FakeOtpSender()
    now = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
    for index in range(30):
        await request_otp_code(
            db_session,
            phone=f"+99890{index:07d}",
            request_ip="198.51.100.2",
            sender=sender,
            now=now + timedelta(seconds=61 * index),
        )

    with pytest.raises(APIError) as exc_info:
        await request_otp_code(
            db_session,
            phone="+998909999999",
            request_ip="198.51.100.2",
            sender=sender,
            now=now + timedelta(seconds=61 * 30),
        )

    assert exc_info.value.code == "code_send_rate_limited"


async def test_otp_phone_daily_limit_is_durable(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OTP_DEV_CODES", ["000000"])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    monkeypatch.setattr(settings, "OTP_PHONE_SENDS_PER_DAY", 2)
    sender = FakeOtpSender()
    now = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
    for index in range(2):
        await request_otp_code(
            db_session,
            phone="+998911111111",
            request_ip="198.51.100.4",
            sender=sender,
            now=now + timedelta(seconds=61 * index),
        )

    with pytest.raises(APIError) as exc_info:
        await request_otp_code(
            db_session,
            phone="+998911111111",
            request_ip="198.51.100.4",
            sender=sender,
            now=now + timedelta(seconds=61 * 2),
        )

    assert exc_info.value.code == "code_send_rate_limited"
    # A retry window far beyond an hour proves the *daily* cap tripped, not the
    # hourly one (still 5) or the cooldown.
    assert exc_info.value.details is not None
    assert exc_info.value.details["retry_after_seconds"] > 3600


async def test_otp_ip_daily_limit_is_durable(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OTP_DEV_CODES", ["000000"])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    monkeypatch.setattr(settings, "OTP_IP_SENDS_PER_DAY", 2)
    sender = FakeOtpSender()
    now = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
    for index in range(2):
        await request_otp_code(
            db_session,
            phone=f"+99891222222{index}",
            request_ip="198.51.100.5",
            sender=sender,
            now=now + timedelta(seconds=index),
        )

    with pytest.raises(APIError) as exc_info:
        await request_otp_code(
            db_session,
            phone="+998912222229",
            request_ip="198.51.100.5",
            sender=sender,
            now=now + timedelta(seconds=2),
        )

    assert exc_info.value.code == "code_send_rate_limited"
    assert exc_info.value.details is not None
    assert exc_info.value.details["retry_after_seconds"] > 3600


async def test_otp_global_caps_bound_total_sends(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The global caps are the platform-wide Telegram bill ceiling: they trip
    across unrelated phones AND unrelated IPs."""
    monkeypatch.setattr(settings, "OTP_DEV_CODES", ["000000"])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    monkeypatch.setattr(settings, "OTP_GLOBAL_SENDS_PER_HOUR", 2)
    sender = FakeOtpSender()
    now = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
    for index in range(2):
        await request_otp_code(
            db_session,
            phone=f"+99891333333{index}",
            request_ip=f"198.51.100.{10 + index}",
            sender=sender,
            now=now + timedelta(seconds=index),
        )

    with pytest.raises(APIError) as exc_info:
        await request_otp_code(
            db_session,
            phone="+998913333339",
            request_ip="198.51.100.99",
            sender=sender,
            now=now + timedelta(seconds=2),
        )

    assert exc_info.value.code == "code_send_rate_limited"

    # The daily ceiling holds even when the hourly window has rolled over.
    monkeypatch.setattr(settings, "OTP_GLOBAL_SENDS_PER_HOUR", 150)
    monkeypatch.setattr(settings, "OTP_GLOBAL_SENDS_PER_DAY", 2)
    with pytest.raises(APIError) as exc_info:
        await request_otp_code(
            db_session,
            phone="+998913333339",
            request_ip="198.51.100.99",
            sender=sender,
            now=now + timedelta(hours=2),
        )

    assert exc_info.value.code == "code_send_rate_limited"
    assert exc_info.value.details is not None
    assert exc_info.value.details["retry_after_seconds"] > 3600


async def test_prune_expired_otp_challenges_keeps_limit_windows_intact(
    db_session: AsyncSession,
) -> None:
    """Pruning drops rows older than the 7-day retention but keeps everything
    inside the 24 h limit windows — including consumed rows, which still feed
    the send counters."""
    now = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)

    def challenge(
        *, phone: str, created_at: datetime, consumed: bool
    ) -> PhoneVerificationChallenge:
        return PhoneVerificationChallenge(
            phone=phone,
            code_hash="x" * 64,
            request_ip="198.51.100.9",
            expires_at=created_at + timedelta(minutes=5),
            attempt_count=0,
            consumed_at=created_at if consumed else None,
            created_at=created_at,
        )

    db_session.add_all(
        [
            challenge(phone="+998910000001", created_at=now - timedelta(days=8), consumed=True),
            challenge(phone="+998910000002", created_at=now - timedelta(days=8), consumed=False),
            challenge(phone="+998910000003", created_at=now - timedelta(hours=23), consumed=True),
            challenge(phone="+998910000004", created_at=now - timedelta(minutes=1), consumed=False),
        ]
    )
    await db_session.flush()

    pruned = await prune_expired_otp_challenges(db_session, now=now)

    assert pruned == 2
    remaining = (await db_session.scalars(select(PhoneVerificationChallenge.phone))).all()
    assert sorted(remaining) == ["+998910000003", "+998910000004"]


def test_client_ip_uses_forwarded_header_only_from_trusted_peer() -> None:
    # Trusted peer: take the right-most untrusted hop, not the forgeable
    # left-most entry.
    assert (
        resolve_client_ip(
            peer_host="127.0.0.1",
            x_forwarded_for="203.0.113.20, 10.0.0.1",
            trusted_proxy_cidrs=["127.0.0.1/32"],
        )
        == "10.0.0.1"
    )
    # Untrusted peer: the header is ignored entirely.
    assert (
        resolve_client_ip(
            peer_host="10.0.0.5",
            x_forwarded_for="203.0.113.20",
            trusted_proxy_cidrs=["127.0.0.1/32"],
        )
        == "10.0.0.5"
    )


def test_client_ip_skips_trusted_chain_and_distrusts_spoofed_entries() -> None:
    trusted = ["127.0.0.1/32", "172.29.0.0/24"]
    # A spoofed left-most entry is skipped: the right-most hop outside the
    # trusted CIDRs is the real client vouched for by our proxies.
    assert (
        resolve_client_ip(
            peer_host="172.29.0.7",
            x_forwarded_for="1.2.3.4, 203.0.113.20, 172.29.0.9",
            trusted_proxy_cidrs=trusted,
        )
        == "203.0.113.20"
    )
    # Every hop trusted → the chain origin is the client.
    assert (
        resolve_client_ip(
            peer_host="172.29.0.7",
            x_forwarded_for="172.29.0.3, 172.29.0.9",
            trusted_proxy_cidrs=trusted,
        )
        == "172.29.0.3"
    )
    # A malformed entry poisons the whole header → fall back to the peer.
    assert (
        resolve_client_ip(
            peer_host="172.29.0.7",
            x_forwarded_for="203.0.113.20, not-an-ip",
            trusted_proxy_cidrs=trusted,
        )
        == "172.29.0.7"
    )
