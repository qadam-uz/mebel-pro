"""In-memory per-IP sliding-window throttles for the sign-in surfaces.

Two budgets share one primitive:

* **Password login** — the per-account lockout in `app.core.security` stops
  targeted guessing, but it can't cover every shape: workshop logins shared
  across workshops record no failures at all, and an attacker rotating across
  many accounts stays under each account's lockout. Only *failures* count here,
  and a success never resets the window — otherwise one valid credential could
  launder unlimited brute-force budget from its IP.
* **Telegram fallback-code redeem** — every *attempt* counts. A 6-digit code
  has 10⁶ of entropy and lives 5 minutes; the throttle is what turns that into
  lottery odds. There is no per-row counter to lean on: no code row is
  addressable before a correct guess.

Process-local by design — the app runs as a single instance, and the account
lockout remains the durable backstop across restarts.
"""

from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import status

from app.core.config import settings
from app.core.errors import APIError

# Upper bound on tracked IPs so a spray of distinct source addresses can't
# grow the map without limit.
MAX_TRACKED_IPS = 10_000


class SlidingWindowIpThrottle:
    """Counts recorded events per client IP inside a sliding window.

    The budget, window, and enabled flag are read through callables so a
    settings change (or a test's monkeypatch) takes effect without rebuilding
    the throttle.
    """

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        enabled: Callable[[], bool],
        budget: Callable[[], int],
        window_seconds: Callable[[], int],
    ) -> None:
        self._error_code = error_code
        self._message = message
        self._enabled = enabled
        self._budget = budget
        self._window_seconds = window_seconds
        self._failures: dict[str, deque[datetime]] = {}

    def check(self, ip: str, *, now: datetime | None = None) -> None:
        """Raise 429 when the IP is over its budget for the window."""
        if not self._enabled():
            return
        current = _now(now)
        attempts = self._pruned(ip, current)
        if len(attempts) < self._budget():
            return
        retry_at = attempts[0] + timedelta(seconds=self._window_seconds())
        raise APIError(
            self._error_code,
            self._message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after_seconds": max(1, int((retry_at - current).total_seconds()))},
        )

    def record(self, ip: str, *, now: datetime | None = None) -> None:
        if not self._enabled():
            return
        current = _now(now)
        attempts = self._pruned(ip, current)
        attempts.append(current)
        self._failures[ip] = attempts
        self._evict_if_full()

    def reset(self) -> None:
        """Drop all tracked state (tests)."""
        self._failures.clear()

    def _pruned(self, ip: str, now: datetime) -> deque[datetime]:
        attempts = self._failures.get(ip, deque())
        cutoff = now - timedelta(seconds=self._window_seconds())
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        return attempts

    def _evict_if_full(self) -> None:
        if len(self._failures) <= MAX_TRACKED_IPS:
            return
        cutoff = datetime.now(UTC) - timedelta(seconds=self._window_seconds())
        for ip, attempts in list(self._failures.items()):
            if attempts[-1] <= cutoff:
                del self._failures[ip]
        if len(self._failures) > MAX_TRACKED_IPS:
            # Still over: drop the stalest-active entries first.
            by_recency = sorted(self._failures, key=lambda key: self._failures[key][-1])
            for ip in by_recency[: len(self._failures) - MAX_TRACKED_IPS]:
                del self._failures[ip]


class LoginIpThrottle(SlidingWindowIpThrottle):
    """Sliding-window counter of failed password logins per client IP."""

    def __init__(self) -> None:
        super().__init__(
            error_code="login_rate_limited",
            message="Too many login attempts",
            enabled=lambda: settings.LOGIN_IP_THROTTLE_ENABLED,
            budget=lambda: settings.LOGIN_IP_MAX_FAILURES,
            window_seconds=lambda: settings.LOGIN_IP_WINDOW_SECONDS,
        )

    def record_failure(self, ip: str, *, now: datetime | None = None) -> None:
        self.record(ip, now=now)


def _now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    return now if now.tzinfo is not None else now.replace(tzinfo=UTC)


login_throttle = LoginIpThrottle()

# Fallback-code redeem attempts per IP. Shares the Telegram-login master switch
# so an E2E run can turn every per-IP budget off in one place.
telegram_code_throttle = SlidingWindowIpThrottle(
    error_code="login_code_rate_limited",
    message="Too many code attempts",
    enabled=lambda: settings.TELEGRAM_LOGIN_RATE_LIMITS_ENABLED,
    budget=lambda: settings.TELEGRAM_LOGIN_CODE_REDEEMS_PER_IP,
    window_seconds=lambda: settings.TELEGRAM_LOGIN_CODE_REDEEM_WINDOW_SECONDS,
)
