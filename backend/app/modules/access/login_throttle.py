"""In-memory per-IP throttle for password login endpoints.

The per-account lockout in `app.core.security` stops targeted guessing, but it
can't cover every shape: workshop logins shared across workshops record no
failures at all, and an attacker rotating across many accounts stays under
each account's lockout. This throttle caps *failed* login attempts per client
IP in a sliding window, which also keeps Argon2 verification cost off the hot
path once an IP is tripped.

Process-local by design — the app runs as a single instance, and the
account lockout remains the durable backstop across restarts.
"""

from collections import deque
from datetime import UTC, datetime, timedelta

from fastapi import status

from app.core.config import settings
from app.core.errors import APIError

# Upper bound on tracked IPs so a spray of distinct source addresses can't
# grow the map without limit.
MAX_TRACKED_IPS = 10_000


class LoginIpThrottle:
    """Sliding-window counter of failed password logins per client IP.

    Only failures count and a success never resets the window — otherwise one
    valid credential could launder unlimited brute-force budget from its IP.
    """

    def __init__(self) -> None:
        self._failures: dict[str, deque[datetime]] = {}

    def check(self, ip: str, *, now: datetime | None = None) -> None:
        """Raise 429 when the IP is over the failure budget for the window."""
        if not settings.LOGIN_IP_THROTTLE_ENABLED:
            return
        current = _now(now)
        attempts = self._pruned(ip, current)
        if len(attempts) < settings.LOGIN_IP_MAX_FAILURES:
            return
        retry_at = attempts[0] + timedelta(seconds=settings.LOGIN_IP_WINDOW_SECONDS)
        raise APIError(
            "login_rate_limited",
            "Too many login attempts",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after_seconds": max(1, int((retry_at - current).total_seconds()))},
        )

    def record_failure(self, ip: str, *, now: datetime | None = None) -> None:
        if not settings.LOGIN_IP_THROTTLE_ENABLED:
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
        cutoff = now - timedelta(seconds=settings.LOGIN_IP_WINDOW_SECONDS)
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        return attempts

    def _evict_if_full(self) -> None:
        if len(self._failures) <= MAX_TRACKED_IPS:
            return
        cutoff = datetime.now(UTC) - timedelta(seconds=settings.LOGIN_IP_WINDOW_SECONDS)
        for ip, attempts in list(self._failures.items()):
            if attempts[-1] <= cutoff:
                del self._failures[ip]
        if len(self._failures) > MAX_TRACKED_IPS:
            # Still over: drop the stalest-active entries first.
            by_recency = sorted(self._failures, key=lambda key: self._failures[key][-1])
            for ip in by_recency[: len(self._failures) - MAX_TRACKED_IPS]:
                del self._failures[ip]


def _now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    return now if now.tzinfo is not None else now.replace(tzinfo=UTC)


login_throttle = LoginIpThrottle()
