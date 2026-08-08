"""Password, token, and login-attempt security primitives."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import anyio.to_thread
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

PASSWORD_MIN_LENGTH = 8
LOCKOUT_BAD_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)

_hasher = PasswordHasher()


class PasswordPolicyError(ValueError):
    """Raised when a password does not meet the documented policy."""


def validate_password(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise PasswordPolicyError("Password must be at least 8 characters")
    if not any(ch.islower() for ch in password):
        raise PasswordPolicyError("Password must contain a lowercase letter")
    if not any(ch.isupper() for ch in password):
        raise PasswordPolicyError("Password must contain an uppercase letter")
    if not any(ch.isdigit() for ch in password):
        raise PasswordPolicyError("Password must contain a digit")


def hash_password(password: str) -> str:
    validate_password(password)
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


async def verify_password_async(password: str, password_hash: str) -> bool:
    """`verify_password` off the event loop.

    Argon2's defaults are 64 MiB and ~95 ms of CPU per verify. The app runs a
    single event loop, so an inline verify stalls every other in-flight request
    for that long — and a login burst serialises. Async callers use this; the
    sync form stays for tests and CLI paths that have no loop to block.
    """
    return await anyio.to_thread.run_sync(verify_password, password, password_hash)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True)
class LoginAttemptState:
    failed_login_count: int
    locked_until: datetime | None


def is_locked(state: LoginAttemptState, *, now: datetime | None = None) -> bool:
    current = _coerce_utc(now) if now is not None else datetime.now(UTC)
    return state.locked_until is not None and _coerce_utc(state.locked_until) > current


def record_login_failure(
    state: LoginAttemptState,
    *,
    now: datetime | None = None,
) -> LoginAttemptState:
    current = _coerce_utc(now) if now is not None else datetime.now(UTC)
    failed = state.failed_login_count + 1
    locked_until = (
        current + LOCKOUT_DURATION if failed >= LOCKOUT_BAD_ATTEMPTS else state.locked_until
    )
    return LoginAttemptState(failed_login_count=failed, locked_until=locked_until)


def record_login_success() -> LoginAttemptState:
    return LoginAttemptState(failed_login_count=0, locked_until=None)
