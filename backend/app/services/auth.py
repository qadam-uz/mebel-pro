"""Authentication — password sign-in (workshop/platform), Telegram OAuth
(client), refresh, change-password, and the ``me`` projection.

Generic failure ("login or password is incorrect") avoids an account-existence
oracle; five consecutive bad attempts lock the account for 15 minutes
(docs/ref/features/access-management.md).
"""

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, unauthorized
from app.core.principal import Principal
from app.core.security import (
    hash_password,
    needs_rehash,
    password_complexity_ok,
    verify_password,
)
from app.models.enums import PrincipalType, UserStatus
from app.models.identity import Client, PlatformUser, WorkshopUser
from app.models.workshop import Workshop
from app.services import sessions as session_service

LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)

_GENERIC_LOGIN_ERROR = "Login or password is incorrect."


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _is_locked(user: PlatformUser | WorkshopUser) -> bool:
    locked_until = _aware(user.locked_until)
    return locked_until is not None and locked_until > _now()


def _register_failure(user: PlatformUser | WorkshopUser) -> None:
    user.failed_login_count += 1
    if user.failed_login_count >= LOCKOUT_THRESHOLD:
        user.locked_until = _now() + LOCKOUT_DURATION
        user.failed_login_count = 0


def _register_success(user: PlatformUser | WorkshopUser) -> None:
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = _now()


def _lockout_error(user: PlatformUser | WorkshopUser) -> AppError:
    locked_until = _aware(user.locked_until)
    when = locked_until.strftime("%H:%M") if locked_until else ""
    return AppError(
        "account_locked",
        f"Too many attempts. Try again at {when}.",
        status_code=429,
        extra={"locked_until": locked_until.isoformat() if locked_until else None},
    )


async def authenticate_platform(
    db: AsyncSession, login: str, password: str, device_info: dict[str, Any] | None = None
) -> session_service.IssuedTokens:
    user = (
        await db.execute(select(PlatformUser).where(PlatformUser.login == login.strip().lower()))
    ).scalar_one_or_none()
    return await _password_login(db, user, password, PrincipalType.PLATFORM_USER, device_info)


async def authenticate_workshop(
    db: AsyncSession, login: str, password: str, device_info: dict[str, Any] | None = None
) -> session_service.IssuedTokens:
    # Login is unique per workshop, not globally; resolve by matching password.
    candidates = (
        (await db.execute(select(WorkshopUser).where(WorkshopUser.login == login.strip().lower())))
        .scalars()
        .all()
    )
    if len(candidates) == 1:
        return await _password_login(
            db, candidates[0], password, PrincipalType.WORKSHOP_USER, device_info
        )
    # Collision across workshops: pick the single user whose password verifies.
    matched = [
        u
        for u in candidates
        if u.status is UserStatus.ACTIVE
        and not _is_locked(u)
        and verify_password(password, u.password_hash)
    ]
    if len(matched) != 1:
        raise unauthorized(_GENERIC_LOGIN_ERROR, code="invalid_credentials")
    user = matched[0]
    await _assert_workshop_active(db, user.workshop_id)
    _register_success(user)
    await db.flush()
    return await session_service.create_session(
        db, PrincipalType.WORKSHOP_USER, user.id, device_info
    )


async def _password_login(
    db: AsyncSession,
    user: PlatformUser | WorkshopUser | None,
    password: str,
    principal_type: PrincipalType,
    device_info: dict[str, Any] | None,
) -> session_service.IssuedTokens:
    if user is None:
        # Spend time hashing to avoid a timing oracle, then fail generically.
        verify_password(password, "$argon2id$v=19$m=65536,t=3,p=4$" + "A" * 22)
        raise unauthorized(_GENERIC_LOGIN_ERROR, code="invalid_credentials")
    if user.status is not UserStatus.ACTIVE:
        raise unauthorized("This account is blocked.", code="account_blocked")
    if _is_locked(user):
        raise _lockout_error(user)
    if not verify_password(password, user.password_hash):
        _register_failure(user)
        await db.flush()
        raise unauthorized(_GENERIC_LOGIN_ERROR, code="invalid_credentials")
    if isinstance(user, WorkshopUser):
        await _assert_workshop_active(db, user.workshop_id)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    _register_success(user)
    await db.flush()
    return await session_service.create_session(db, principal_type, user.id, device_info)


async def _assert_workshop_active(db: AsyncSession, workshop_id: uuid.UUID) -> None:
    ws = await db.get(Workshop, workshop_id)
    if ws is None or ws.status.value != "active":
        raise unauthorized("This workshop is blocked.", code="workshop_blocked")


# --- Telegram OAuth (client) ----------------------------------------------


def verify_telegram_payload(payload: dict[str, Any]) -> None:
    """HMAC-verify the Telegram Login Widget payload; raise on failure.

    Skipped when no bot token is configured (dev convenience). This is safe
    only because `Settings._enforce_prod_safety` refuses to boot with an empty
    `TELEGRAM_BOT_TOKEN` when `ENV=prod`, so the skip never happens in prod.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    received_hash = payload.get("hash")
    if not received_hash:
        raise AppError("invalid_oauth_signature", "Missing signature.", status_code=401)
    pairs = sorted(f"{k}={v}" for k, v in payload.items() if k != "hash" and v is not None)
    data_check_string = "\n".join(pairs)
    secret_key = hashlib.sha256(token.encode()).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(received_hash)):
        raise AppError("invalid_oauth_signature", "Invalid signature.", status_code=401)
    auth_date = payload.get("auth_date")
    if auth_date is not None:
        age = _now().timestamp() - float(auth_date)
        if age > settings.TELEGRAM_OAUTH_MAX_AGE_SECONDS:
            raise AppError("oauth_expired", "Sign-in expired, please retry.", status_code=401)


@dataclass
class ClientLogin:
    tokens: session_service.IssuedTokens
    is_new: bool


async def authenticate_client_telegram(
    db: AsyncSession, payload: dict[str, Any], device_info: dict[str, Any] | None = None
) -> ClientLogin:
    verify_telegram_payload(payload)
    telegram_id = payload.get("id") or payload.get("telegram_id")
    if telegram_id is None:
        raise AppError("invalid_oauth_signature", "Missing Telegram id.", status_code=401)
    phone = payload.get("phone_number") or payload.get("phone")
    client = (
        await db.execute(select(Client).where(Client.telegram_id == int(telegram_id)))
    ).scalar_one_or_none()
    is_new = client is None
    if client is None:
        if not phone:
            raise AppError(
                "missing_phone_number",
                "Share your phone with the bot and try again.",
                status_code=400,
            )
        client = Client(
            telegram_id=int(telegram_id),
            phone=str(phone),
            first_name=str(payload.get("first_name") or "Mijoz"),
            last_name=payload.get("last_name"),
            photo_url=payload.get("photo_url"),
        )
        db.add(client)
        await db.flush()
    else:
        if client.status is not UserStatus.ACTIVE:
            raise unauthorized("This account is blocked.", code="account_blocked")
        # Telegram is the source of truth — refresh profile on every login.
        client.first_name = str(payload.get("first_name") or client.first_name)
        client.last_name = payload.get("last_name")
        client.photo_url = payload.get("photo_url")
        if phone:
            client.phone = str(phone)
    client.last_login_at = _now()
    await db.flush()
    tokens = await session_service.create_session(db, PrincipalType.CLIENT, client.id, device_info)
    return ClientLogin(tokens=tokens, is_new=is_new)


# --- refresh / change-password / me ----------------------------------------


async def refresh_tokens(
    db: AsyncSession, refresh_token: str
) -> tuple[str, session_service.IssuedTokens | None]:
    session = await session_service.get_session_by_refresh_token(db, refresh_token)
    if session is None:
        raise unauthorized("Invalid or expired token.")
    expires = _aware(session.refresh_token_expires_at)
    if expires is None or expires < _now():
        await session_service.revoke(db, session)
        raise unauthorized("Invalid or expired token.")
    if not await session_service.principal_is_active(db, session):
        await session_service.revoke(db, session)
        raise unauthorized("Account is not active.", code="account_blocked")
    access_token = await session_service.rotate_access_token(db, session)
    return access_token, None


async def _user_for_principal(
    db: AsyncSession, principal: Principal
) -> PlatformUser | WorkshopUser | None:
    if principal.is_platform_user:
        return await db.get(PlatformUser, principal.id)
    if principal.is_workshop_user:
        return await db.get(WorkshopUser, principal.id)
    return None


async def change_own_password(
    db: AsyncSession, principal: Principal, current_password: str, new_password: str
) -> None:
    user = await _user_for_principal(db, principal)
    if user is None:
        raise unauthorized()
    if not verify_password(current_password, user.password_hash):
        raise unauthorized(_GENERIC_LOGIN_ERROR, code="invalid_credentials")
    if not password_complexity_ok(new_password):
        raise AppError(
            "weak_password",
            "Password must be ≥ 8 chars with an upper, a lower, and a digit.",
        )
    user.password_hash = hash_password(new_password)
    user.force_password_change = False
    await db.flush()
    # Revoke all *other* sessions; keep the current one.
    await session_service.revoke_all(
        db, principal.type, principal.id, except_session_id=principal.session_id
    )
