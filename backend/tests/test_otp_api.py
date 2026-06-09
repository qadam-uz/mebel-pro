from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.core.errors import APIError
from app.modules.access.api import request_otp_code, resolve_client_ip
from app.modules.access.contracts import PhoneVerificationChallenge
from app.modules.access.routes import REFRESH_COOKIE_NAME, get_otp_sender
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class FakeOtpSender:
    sent: list[tuple[str, str, int]] = field(default_factory=list)

    async def send_code(self, *, phone: str, code: str, ttl_seconds: int) -> None:
        self.sent.append((phone, code, ttl_seconds))


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
    assert challenge.request_ip == "203.0.113.10"
    assert challenge.code_hash != sender.sent[0][1]
    assert len(challenge.code_hash) == 64

    login = await client.post(
        "/api/v1/auth/client/otp/verify",
        json={"phone": "+998901111111", "code": sender.sent[0][1], "name": "Telegram User"},
    )

    assert login.status_code == 200
    assert login.json()["me"]["phone"] == "+998901111111"


async def test_otp_wrong_code_burns_challenge_after_five_attempts(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OTP_DEV_CODES", ["000000"])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    await client.post("/api/v1/auth/client/otp/request", json={"phone": "+998902222222"})

    for _ in range(4):
        response = await client.post(
            "/api/v1/auth/client/otp/verify",
            json={"phone": "+998902222222", "code": "111111"},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_code"

    burned = await client.post(
        "/api/v1/auth/client/otp/verify",
        json={"phone": "+998902222222", "code": "111111"},
    )
    correct_after_burn = await client.post(
        "/api/v1/auth/client/otp/verify",
        json={"phone": "+998902222222", "code": "000000", "name": "Late User"},
    )

    assert burned.status_code == 400
    assert burned.json()["code"] == "too_many_attempts"
    assert correct_after_burn.status_code == 400
    assert correct_after_burn.json()["code"] == "invalid_code"


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


def test_client_ip_uses_forwarded_header_only_from_trusted_peer() -> None:
    assert (
        resolve_client_ip(
            peer_host="127.0.0.1",
            x_forwarded_for="203.0.113.20, 10.0.0.1",
            trusted_proxy_cidrs=["127.0.0.1/32"],
        )
        == "203.0.113.20"
    )
    assert (
        resolve_client_ip(
            peer_host="10.0.0.5",
            x_forwarded_for="203.0.113.20",
            trusted_proxy_cidrs=["127.0.0.1/32"],
        )
        == "10.0.0.5"
    )
