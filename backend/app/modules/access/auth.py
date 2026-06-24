"""Authentication use cases for platform and workshop users."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal
from app.core.security import (
    LoginAttemptState,
    PasswordPolicyError,
    hash_password,
    is_locked,
    record_login_failure,
    record_login_success,
    validate_password,
    verify_password,
)
from app.models.enums import AuthenticatedPrincipalType, UserStatus, WorkshopStatus
from app.modules.access.contracts import PlatformUser, Session, WorkshopUser
from app.modules.access.sessions import (
    PlainSessionTokens,
    create_session,
    principal_from_session,
    revoke_other_sessions,
)
from app.modules.workshop.contracts import Workshop

LOCKED_STATUS_CODE = 423
INVALID_CREDENTIALS_CODE = "invalid_credentials"


@dataclass(frozen=True)
class AuthSessionResult:
    tokens: PlainSessionTokens
    principal: AuthenticatedPrincipal


def _now() -> datetime:
    return datetime.now(UTC)


def _normalized(value: str) -> str:
    return value.strip().lower()


def _invalid_credentials() -> APIError:
    return APIError(
        INVALID_CREDENTIALS_CODE,
        "Invalid credentials",
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


def _account_locked() -> APIError:
    return APIError("account_locked", "Account is locked", status_code=LOCKED_STATUS_CODE)


def _account_blocked() -> APIError:
    return APIError(
        "account_blocked",
        "Account is blocked",
        status_code=status.HTTP_403_FORBIDDEN,
    )


def _login_state(user: PlatformUser | WorkshopUser) -> LoginAttemptState:
    return LoginAttemptState(
        failed_login_count=user.failed_login_count,
        locked_until=user.locked_until,
    )


def _set_login_state(user: PlatformUser | WorkshopUser, state: LoginAttemptState) -> None:
    user.failed_login_count = state.failed_login_count
    user.locked_until = state.locked_until


async def authenticate_platform_user(
    db: AsyncSession,
    *,
    login: str,
    password: str,
    trace_id: str,
    device_info: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> AuthSessionResult:
    user = await db.scalar(
        select(PlatformUser).where(func.lower(PlatformUser.login) == _normalized(login))
    )
    return await _authenticate_user(
        db,
        user=user,
        password=password,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        trace_id=trace_id,
        device_info=device_info,
        now=now,
    )


async def authenticate_workshop_user(
    db: AsyncSession,
    *,
    login: str,
    password: str,
    trace_id: str,
    device_info: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> AuthSessionResult:
    # Workshop logins are unique per workshop, not globally, so the login alone
    # can't name the workshop. Resolve it with the password: among the accounts
    # sharing this login, the one whose password matches is the user. Exactly one
    # match authenticates; with none, a lone account still records the failed
    # attempt (so lockout holds) while a shared login can't be locked by guesses;
    # a duplicate match (same login AND password in two workshops) stays generic.
    candidates = (
        await db.scalars(
            select(WorkshopUser).where(func.lower(WorkshopUser.login) == _normalized(login))
        )
    ).all()
    matched = [
        candidate for candidate in candidates if verify_password(password, candidate.password_hash)
    ]
    user: WorkshopUser | None
    if len(matched) == 1:
        user = matched[0]
    elif not matched and len(candidates) == 1:
        user = candidates[0]
    else:
        user = None
    workshop = await db.get(Workshop, user.workshop_id) if user is not None else None
    return await _authenticate_user(
        db,
        user=user,
        password=password,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        trace_id=trace_id,
        device_info=device_info,
        workshop=workshop,
        now=now,
    )


async def change_password(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    current_password: str,
    new_password: str,
) -> None:
    if principal.principal_type is AuthenticatedPrincipalType.CLIENT:
        raise APIError(
            "password_not_supported",
            "Client accounts do not use passwords",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    user = await _load_password_user(db, principal)
    if user is None:
        raise APIError(
            "invalid_access_token",
            "Authentication required",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    if not verify_password(current_password, user.password_hash):
        raise APIError(
            "invalid_current_password",
            "Current password is invalid",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_password(new_password)
    except PasswordPolicyError as exc:
        raise APIError(
            "weak_password",
            str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc

    user.password_hash = hash_password(new_password)
    user.password_reset_required = False
    _set_login_state(user, record_login_success())
    await revoke_other_sessions(
        db,
        principal_type=principal.principal_type,
        principal_id=principal.principal_id,
        keep_session_id=principal.session_id,
    )


async def _authenticate_user(
    db: AsyncSession,
    *,
    user: PlatformUser | WorkshopUser | None,
    password: str,
    principal_type: AuthenticatedPrincipalType,
    trace_id: str,
    device_info: dict[str, Any] | None,
    workshop: Workshop | None = None,
    now: datetime | None,
) -> AuthSessionResult:
    current = now or _now()
    if user is None:
        raise _invalid_credentials()

    state = _login_state(user)
    password_valid = verify_password(password, user.password_hash)
    if not password_valid:
        if user.status is UserStatus.ACTIVE and not is_locked(state, now=current):
            _set_login_state(user, record_login_failure(state, now=current))
        raise _invalid_credentials()

    if is_locked(state, now=current):
        raise _account_locked()
    if user.status is not UserStatus.ACTIVE:
        raise _account_blocked()
    if workshop is not None and workshop.status is not WorkshopStatus.ACTIVE:
        raise _account_blocked()

    _set_login_state(user, record_login_success())
    user.last_login_at = current
    tokens = await create_session(
        db,
        principal_type=principal_type,
        principal_id=user.id,
        device_info=device_info,
        now=current,
    )
    session = await db.get(Session, tokens.session_id)
    if session is None:
        raise RuntimeError("created session row disappeared before principal resolution")
    principal = await principal_from_session(db, session, trace_id=trace_id)
    if principal is None:
        raise RuntimeError("created session could not resolve an active principal")
    return AuthSessionResult(tokens=tokens, principal=principal)


async def _load_password_user(
    db: AsyncSession,
    principal: AuthenticatedPrincipal,
) -> PlatformUser | WorkshopUser | None:
    user_id: uuid.UUID = principal.principal_id
    if principal.principal_type is AuthenticatedPrincipalType.PLATFORM_USER:
        return await db.get(PlatformUser, user_id)
    if principal.principal_type is AuthenticatedPrincipalType.WORKSHOP_USER:
        return await db.get(WorkshopUser, user_id)
    return None
