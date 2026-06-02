from datetime import UTC, datetime, timedelta

import pytest
from app.core.security import (
    LOCKOUT_BAD_ATTEMPTS,
    LoginAttemptState,
    PasswordPolicyError,
    hash_password,
    hash_token,
    is_locked,
    record_login_failure,
    record_login_success,
    validate_password,
    verify_password,
)


@pytest.mark.parametrize("password", ["short", "alllowercase1", "ALLUPPERCASE1", "NoDigitsHere"])
def test_password_policy_rejects_weak_passwords(password: str) -> None:
    with pytest.raises(PasswordPolicyError):
        validate_password(password)


def test_password_hash_verifies_without_storing_plaintext() -> None:
    password_hash = hash_password("Strong123")

    assert "Strong123" not in password_hash
    assert verify_password("Strong123", password_hash)
    assert not verify_password("Wrong123", password_hash)


def test_tokens_are_hashed_deterministically() -> None:
    assert hash_token("token") == hash_token("token")
    assert hash_token("token") != hash_token("other-token")


def test_login_lockout_starts_after_configured_failures() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    state = LoginAttemptState(failed_login_count=0, locked_until=None)

    for _ in range(LOCKOUT_BAD_ATTEMPTS):
        state = record_login_failure(state, now=now)

    assert state.failed_login_count == LOCKOUT_BAD_ATTEMPTS
    assert state.locked_until is not None
    assert is_locked(state, now=now + timedelta(minutes=1))
    assert not is_locked(state, now=now + timedelta(minutes=16))
    assert record_login_success() == LoginAttemptState(failed_login_count=0, locked_until=None)


def test_login_lockout_handles_naive_persisted_datetimes() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    state = LoginAttemptState(
        failed_login_count=LOCKOUT_BAD_ATTEMPTS,
        locked_until=datetime(2026, 1, 1, 0, 10),
    )

    assert is_locked(state, now=now)
