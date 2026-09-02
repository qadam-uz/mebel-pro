"""Telegram bot sign-in: login tokens, the poll, and the fallback code.

The browser mints a [login token](../../../docs/ref/entities/identity.md), the
bot advances it, the browser's poll redeems it for a normal client session.
Session mechanics are unchanged — this module only decides *when* a client is
proven, and hands off to `sessions.create_session` exactly like the OTP flow it
replaced.
"""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, NoReturn

from fastapi import status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal
from app.models.enums import AuthenticatedPrincipalType, TelegramLoginTokenStatus, UserStatus
from app.modules.access.clients import find_or_create_client, normalize_uz_phone
from app.modules.access.contracts import Client, TelegramLoginCode, TelegramLoginToken
from app.modules.access.contracts import Session as AuthSession
from app.modules.access.login_throttle import telegram_code_throttle
from app.modules.access.sessions import PlainSessionTokens, create_session, principal_from_session

# Both handshake halves live 5 minutes: long enough to find the phone and scan,
# short enough that a photographed QR goes stale before it is useful.
TOKEN_TTL = timedelta(minutes=5)
CODE_TTL = timedelta(minutes=5)
# Retention must exceed the longest per-IP budget window (24 h) — pruning
# earlier would refill token-creation budgets.
LOGIN_RETENTION = timedelta(days=7)
# ≥ 32 random bytes each, per the entity invariants. `token_urlsafe(32)` yields
# 43 URL-safe characters, which fits a `t.me` deep-link payload.
SECRET_BYTES = 32
CODE_DIGITS = 6

# Statuses the bot may still advance. `confirmed` is excluded on purpose: a
# second `/start` must not re-open a handshake the browser may already be
# redeeming.
ADVANCEABLE_STATUSES = (
    TelegramLoginTokenStatus.PENDING,
    TelegramLoginTokenStatus.STARTED,
    TelegramLoginTokenStatus.AWAITING_CONTACT,
)

INVALID_CODE = "invalid_code"


@dataclass(frozen=True)
class LoginTokenIssue:
    token: str
    poll_secret: str
    expires_at: datetime


@dataclass(frozen=True)
class ClientLoginResult:
    tokens: PlainSessionTokens
    principal: AuthenticatedPrincipal


@dataclass(frozen=True)
class LoginPollResult:
    status: TelegramLoginTokenStatus
    expired: bool = False
    login: ClientLoginResult | None = None


def hash_login_token(value: str) -> str:
    """SHA-256 — the deep-link token and the poll secret are already high-entropy."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_login_code(code: str) -> str:
    """HMAC-SHA-256 with a server-side pepper.

    A 6-digit code is trivially rainbow-tabled under a bare hash; the pepper
    means a leaked table of `code_hash` values is useless without the secret.
    """
    return hmac.new(
        settings.TELEGRAM_LOGIN_CODE_PEPPER.encode("utf-8"),
        code.encode("utf-8"),
        "sha256",
    ).hexdigest()


async def create_login_token(
    db: AsyncSession,
    *,
    request_ip: str,
    device_info: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> LoginTokenIssue:
    current = _current_time(now)
    await _enforce_token_budget(db, request_ip=request_ip, now=current)
    token = secrets.token_urlsafe(SECRET_BYTES)
    poll_secret = secrets.token_urlsafe(SECRET_BYTES)
    row = TelegramLoginToken(
        token_hash=hash_login_token(token),
        poll_secret_hash=hash_login_token(poll_secret),
        status=TelegramLoginTokenStatus.PENDING,
        request_ip=request_ip,
        device_info=device_info or {},
        expires_at=current + TOKEN_TTL,
        created_at=current,
    )
    db.add(row)
    await db.flush()
    return LoginTokenIssue(token=token, poll_secret=poll_secret, expires_at=row.expires_at)


async def poll_login_token(
    db: AsyncSession,
    *,
    poll_secret: str,
    trace_id: str,
    device_info: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> LoginPollResult:
    """Report the handshake's state, releasing a session exactly once.

    The session is released only against the poll secret. The deep-link token is
    on screen for anyone to photograph; the poll secret never leaves the browser
    that asked for it, so a photographed QR cannot win the victim's session.
    """
    current = _current_time(now)
    # FOR UPDATE serializes concurrent polls of the same handshake. Without it
    # two in-flight polls could both read `confirmed` and both mint a session,
    # breaking single redemption (no-op on SQLite).
    row = await db.scalar(
        select(TelegramLoginToken)
        .where(TelegramLoginToken.poll_secret_hash == hash_login_token(poll_secret))
        .with_for_update()
    )
    if row is None:
        raise APIError(
            "invalid_poll_secret",
            "Login request not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if row.status is TelegramLoginTokenStatus.CONFIRMED:
        if row.client_id is None:
            raise RuntimeError("confirmed login token carries no client")
        login = await _issue_client_session(
            db,
            client_id=row.client_id,
            trace_id=trace_id,
            device_info=device_info,
            now=current,
        )
        # Burn before returning: the token is single-redemption, so a replayed
        # poll answers `used`, never a second session.
        row.status = TelegramLoginTokenStatus.USED
        row.used_at = current
        await db.flush()
        return LoginPollResult(status=TelegramLoginTokenStatus.USED, login=login)
    expired = row.status in ADVANCEABLE_STATUSES and _coerce_utc(row.expires_at) <= current
    return LoginPollResult(status=row.status, expired=expired)


async def issue_login_code(
    db: AsyncSession,
    *,
    client: Client,
    now: datetime | None = None,
) -> str:
    """Mint the 6-digit fallback code the bot shows an identified client."""
    current = _current_time(now)
    code = str(secrets.randbelow(10**CODE_DIGITS)).zfill(CODE_DIGITS)
    db.add(
        TelegramLoginCode(
            code_hash=hash_login_code(code),
            client_id=client.id,
            expires_at=current + CODE_TTL,
            created_at=current,
        )
    )
    await db.flush()
    return code


async def redeem_login_code(
    db: AsyncSession,
    *,
    code: str,
    request_ip: str,
    trace_id: str,
    device_info: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> ClientLoginResult:
    """Trade a live code for a session.

    Unknown, expired, and already-used codes are one generic `invalid_code`:
    telling them apart would turn the endpoint into an oracle for which codes
    ever existed.
    """
    current = _current_time(now)
    telegram_code_throttle.check(request_ip, now=current)
    telegram_code_throttle.record(request_ip, now=current)
    normalized = code.strip()
    if len(normalized) != CODE_DIGITS or not normalized.isdigit():
        raise _invalid_code()
    row = await db.scalar(
        select(TelegramLoginCode)
        .where(
            TelegramLoginCode.code_hash == hash_login_code(normalized),
            TelegramLoginCode.consumed_at.is_(None),
        )
        .order_by(TelegramLoginCode.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if row is None or _coerce_utc(row.expires_at) <= current:
        raise _invalid_code()
    # Burn first: a code dies on its first successful redeem regardless of what
    # happens next, so a blocked-account rejection can't leave it guessable.
    row.consumed_at = current
    client = await db.get(Client, row.client_id)
    if client is None or client.status is not UserStatus.ACTIVE:
        await _commit_and_raise(db, _invalid_code())
    login = await _issue_client_session(
        db,
        client_id=row.client_id,
        trace_id=trace_id,
        device_info=device_info,
        now=current,
    )
    await db.flush()
    return login


async def dev_confirm_login_token(
    db: AsyncSession,
    *,
    phone: str,
    token: str | None = None,
    name: str | None = None,
    now: datetime | None = None,
) -> None:
    """Confirm a pending token as `phone`, skipping Telegram entirely.

    Gated by `TELEGRAM_LOGIN_DEV_MODE` at the route. Local, CI, and E2E runs
    have no public webhook and no real bot; the login page is untouched — its
    poll succeeds exactly as it would after a real confirm.
    """
    current = _current_time(now)
    query = select(TelegramLoginToken).where(
        TelegramLoginToken.status.in_(ADVANCEABLE_STATUSES),
        TelegramLoginToken.expires_at > current,
    )
    if token is not None:
        query = query.where(TelegramLoginToken.token_hash == hash_login_token(token))
    row = await db.scalar(query.order_by(TelegramLoginToken.created_at.desc()).limit(1))
    if row is None:
        raise APIError(
            "login_token_not_found",
            "No pending login token",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    resolution = await find_or_create_client(db, phone=normalize_uz_phone(phone), name=name)
    if resolution is None:
        raise APIError(
            "name_required",
            "Name is required for a new phone",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    confirm_login_token(row, client=resolution.client, now=current)
    await db.flush()


def confirm_login_token(
    row: TelegramLoginToken,
    *,
    client: Client,
    now: datetime,
) -> None:
    """Bind a token to its client. The single place a handshake becomes valid."""
    row.status = TelegramLoginTokenStatus.CONFIRMED
    row.client_id = client.id
    row.confirmed_at = now


def decline_login_token(row: TelegramLoginToken, *, now: datetime) -> None:
    row.status = TelegramLoginTokenStatus.DECLINED
    row.confirmed_at = row.confirmed_at or now


async def find_login_token(
    db: AsyncSession,
    *,
    token: str,
) -> TelegramLoginToken | None:
    row: TelegramLoginToken | None = await db.scalar(
        select(TelegramLoginToken).where(TelegramLoginToken.token_hash == hash_login_token(token))
    )
    return row


async def find_awaiting_contact_token(
    db: AsyncSession,
    *,
    telegram_user_id: int,
    now: datetime,
) -> TelegramLoginToken | None:
    """The handshake this Telegram account is mid-way through, if any.

    A contact arriving with no such token is the fallback-code flow: the client
    pressed **Kirish kodi** from a chat that was never opened by a deep link.
    """
    row: TelegramLoginToken | None = await db.scalar(
        select(TelegramLoginToken)
        .where(
            TelegramLoginToken.telegram_user_id == telegram_user_id,
            TelegramLoginToken.status == TelegramLoginTokenStatus.AWAITING_CONTACT,
            TelegramLoginToken.expires_at > now,
        )
        .order_by(TelegramLoginToken.created_at.desc())
        .limit(1)
    )
    return row


async def prune_expired_telegram_logins(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> tuple[int, int]:
    """Drop tokens and codes past the 7-day retention. Returns (tokens, codes)."""
    current = _current_time(now)
    cutoff = current - LOGIN_RETENTION
    token_ids = (
        await db.scalars(
            select(TelegramLoginToken.id).where(TelegramLoginToken.created_at < cutoff)
        )
    ).all()
    if token_ids:
        await db.execute(
            delete(TelegramLoginToken).where(TelegramLoginToken.id.in_(token_ids)),
        )
    code_ids = (
        await db.scalars(select(TelegramLoginCode.id).where(TelegramLoginCode.created_at < cutoff))
    ).all()
    if code_ids:
        await db.execute(delete(TelegramLoginCode).where(TelegramLoginCode.id.in_(code_ids)))
    return len(token_ids), len(code_ids)


async def _issue_client_session(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    trace_id: str,
    device_info: dict[str, Any] | None,
    now: datetime,
) -> ClientLoginResult:
    client = await db.get(Client, client_id)
    if client is None:
        raise RuntimeError("login token referenced a client that no longer exists")
    if client.status is not UserStatus.ACTIVE:
        raise APIError(
            "account_blocked",
            "Account is blocked",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    client.last_login_at = now
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=client.id,
        device_info=device_info,
        now=now,
    )
    session = await db.get(AuthSession, tokens.session_id)
    if session is None:
        raise RuntimeError("created session row disappeared before principal resolution")
    principal = await principal_from_session(db, session, trace_id=trace_id)
    if principal is None:
        raise RuntimeError("created client session could not resolve an active principal")
    return ClientLoginResult(tokens=tokens, principal=principal)


async def _enforce_token_budget(
    db: AsyncSession,
    *,
    request_ip: str,
    now: datetime,
) -> None:
    if not settings.TELEGRAM_LOGIN_RATE_LIMITS_ENABLED:
        return
    budgets = (
        (timedelta(hours=1), settings.TELEGRAM_LOGIN_TOKENS_PER_IP_PER_HOUR),
        (timedelta(hours=24), settings.TELEGRAM_LOGIN_TOKENS_PER_IP_PER_DAY),
    )
    for window, cap in budgets:
        window_start = now - window
        count = await db.scalar(
            select(func.count())
            .select_from(TelegramLoginToken)
            .where(
                TelegramLoginToken.request_ip == request_ip,
                TelegramLoginToken.created_at >= window_start,
            )
        )
        if (count or 0) < cap:
            continue
        oldest = await db.scalar(
            select(TelegramLoginToken)
            .where(
                TelegramLoginToken.request_ip == request_ip,
                TelegramLoginToken.created_at >= window_start,
            )
            .order_by(TelegramLoginToken.created_at)
            .limit(1)
        )
        if oldest is None:
            raise RuntimeError("rate-limit count existed without a matching login token")
        retry_at = _coerce_utc(oldest.created_at) + window
        raise APIError(
            "login_token_rate_limited",
            "Too many login requests",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after_seconds": max(1, int((retry_at - now).total_seconds()))},
        )


def _invalid_code() -> APIError:
    return APIError(INVALID_CODE, "Invalid code", status_code=status.HTTP_400_BAD_REQUEST)


async def _commit_and_raise(db: AsyncSession, error: APIError) -> NoReturn:
    """Persist the burn, then reject.

    ``get_session`` rolls back on any exception, which would silently un-burn a
    consumed code (the shape of CB-133).
    """
    await db.commit()
    raise error


def _current_time(now: datetime | None) -> datetime:
    return _coerce_utc(now) if now is not None else datetime.now(UTC)


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
