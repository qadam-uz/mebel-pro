"""Per-IP login throttle: unit behavior + API integration on both login endpoints."""

from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.core.errors import APIError
from app.modules.access.login_throttle import LoginIpThrottle
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_platform_user

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _throttle(
    monkeypatch: pytest.MonkeyPatch, *, max_failures: int = 2, window: int = 60
) -> LoginIpThrottle:
    monkeypatch.setattr(settings, "LOGIN_IP_THROTTLE_ENABLED", True)
    monkeypatch.setattr(settings, "LOGIN_IP_MAX_FAILURES", max_failures)
    monkeypatch.setattr(settings, "LOGIN_IP_WINDOW_SECONDS", window)
    return LoginIpThrottle()


def test_check_passes_under_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    throttle = _throttle(monkeypatch, max_failures=2)
    throttle.record_failure("1.2.3.4", now=T0)
    throttle.check("1.2.3.4", now=T0 + timedelta(seconds=1))


def test_check_raises_429_at_budget_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    throttle = _throttle(monkeypatch, max_failures=2, window=60)
    throttle.record_failure("1.2.3.4", now=T0)
    throttle.record_failure("1.2.3.4", now=T0 + timedelta(seconds=10))

    with pytest.raises(APIError) as exc_info:
        throttle.check("1.2.3.4", now=T0 + timedelta(seconds=20))

    exc = exc_info.value
    assert exc.code == "login_rate_limited"
    assert exc.status_code == 429
    # Retry is bounded by the oldest failure in the window.
    assert exc.details == {"retry_after_seconds": 40}


def test_window_slides_and_frees_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    throttle = _throttle(monkeypatch, max_failures=2, window=60)
    throttle.record_failure("1.2.3.4", now=T0)
    throttle.record_failure("1.2.3.4", now=T0 + timedelta(seconds=10))

    # The oldest failure has aged out — only one attempt remains in-window.
    throttle.check("1.2.3.4", now=T0 + timedelta(seconds=61))


def test_failures_are_tracked_per_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    throttle = _throttle(monkeypatch, max_failures=1)
    throttle.record_failure("1.2.3.4", now=T0)

    throttle.check("5.6.7.8", now=T0)
    with pytest.raises(APIError):
        throttle.check("1.2.3.4", now=T0)


def test_disabled_throttle_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    throttle = _throttle(monkeypatch, max_failures=1)
    monkeypatch.setattr(settings, "LOGIN_IP_THROTTLE_ENABLED", False)
    throttle.record_failure("1.2.3.4", now=T0)
    throttle.check("1.2.3.4", now=T0)


def test_eviction_keeps_map_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    throttle = _throttle(monkeypatch, max_failures=1, window=60)
    monkeypatch.setattr(
        "app.modules.access.login_throttle.MAX_TRACKED_IPS",
        10,
    )
    for index in range(50):
        throttle.record_failure(f"10.0.0.{index}", now=T0)

    assert len(throttle._failures) <= 10


async def test_failed_logins_trip_ip_throttle(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LOGIN_IP_MAX_FAILURES", 3)
    await seed_platform_user(db_session, login="admin-throttle", password="Admin123")

    for _ in range(3):
        response = await client.post(
            "/api/v1/auth/platform/login",
            json={"login": "admin-throttle", "password": "Wrong123"},
        )
        assert response.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "admin-throttle", "password": "Wrong123"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "login_rate_limited"
    assert blocked.json()["details"]["retry_after_seconds"] >= 1

    # Even correct credentials are refused while the IP is tripped.
    correct = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "admin-throttle", "password": "Admin123"},
    )
    assert correct.status_code == 429


async def test_successful_login_does_not_reset_ip_budget(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LOGIN_IP_MAX_FAILURES", 3)
    await seed_platform_user(db_session, login="admin-no-reset", password="Admin123")

    for password in ("Wrong123", "Wrong123", "Admin123", "Wrong123"):
        response = await client.post(
            "/api/v1/auth/platform/login",
            json={"login": "admin-no-reset", "password": password},
        )
    assert response.status_code == 401

    # Three failures in the window despite the interleaved success → tripped.
    blocked = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "admin-no-reset", "password": "Admin123"},
    )
    assert blocked.status_code == 429


async def test_throttle_is_per_client_ip(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LOGIN_IP_MAX_FAILURES", 2)
    await seed_platform_user(db_session, login="admin-per-ip", password="Admin123")

    for _ in range(2):
        response = await client.post(
            "/api/v1/auth/platform/login",
            json={"login": "admin-per-ip", "password": "Wrong123"},
            headers={"X-Forwarded-For": "203.0.113.1"},
        )
        assert response.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "admin-per-ip", "password": "Wrong123"},
        headers={"X-Forwarded-For": "203.0.113.1"},
    )
    assert blocked.status_code == 429

    other_ip = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "admin-per-ip", "password": "Wrong123"},
        headers={"X-Forwarded-For": "203.0.113.2"},
    )
    assert other_ip.status_code == 401


async def test_budget_is_shared_across_login_endpoints(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LOGIN_IP_MAX_FAILURES", 2)
    await seed_platform_user(db_session, login="admin-shared", password="Admin123")

    platform = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "admin-shared", "password": "Wrong123"},
    )
    workshop = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "nobody", "password": "Wrong123"},
    )
    assert platform.status_code == 401
    assert workshop.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "nobody", "password": "Wrong123"},
    )
    assert blocked.status_code == 429


async def test_throttle_disabled_allows_unlimited_attempts(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LOGIN_IP_THROTTLE_ENABLED", False)
    monkeypatch.setattr(settings, "LOGIN_IP_MAX_FAILURES", 1)
    await seed_platform_user(db_session, login="admin-disabled", password="Admin123")

    for _ in range(5):
        response = await client.post(
            "/api/v1/auth/platform/login",
            json={"login": "admin-disabled", "password": "Wrong123"},
        )
        assert response.status_code == 401
