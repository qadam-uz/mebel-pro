"""Client Telegram OTP request and verification service."""

import hmac
import ipaddress
import json
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, NoReturn, Protocol

import anyio
from fastapi import status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.core.config import settings
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal
from app.models.enums import AuthenticatedPrincipalType
from app.modules.access.clients import find_or_create_client, normalize_uz_phone
from app.modules.access.contracts import PhoneVerificationChallenge, Session
from app.modules.access.sessions import PlainSessionTokens, create_session, principal_from_session

logger = get_logger(__name__)

CODE_RE = re.compile(r"^\d{6}$")
OTP_TTL = timedelta(minutes=5)
# Pinned by the DB check constraint on attempt_count (0..5) — not env-tunable.
MAX_VERIFY_ATTEMPTS = 5
# Send budgets (cooldown, per-phone/IP/global hourly + daily caps) live in
# Settings so they can be tightened mid-incident without a deploy.
# Challenge rows feed the send-limit counters, so retention must exceed the
# longest limit window (24 h) — pruning earlier would refill send budgets.
CHALLENGE_RETENTION = timedelta(days=7)


class OtpSender(Protocol):
    async def send_code(self, *, phone: str, code: str, ttl_seconds: int) -> None: ...


class TelegramDeliveryError(Exception):
    """Raised when Telegram cannot deliver or accept the verification request."""


class TelegramGatewaySender:
    def __init__(
        self,
        *,
        access_token: str,
        api_base_url: str,
        timeout_seconds: float,
    ) -> None:
        parsed = urllib.parse.urlparse(api_base_url)
        if parsed.scheme != "https":
            raise ValueError("Telegram Gateway API base URL must use HTTPS")
        self._access_token = access_token
        self._api_base_url = api_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def send_code(self, *, phone: str, code: str, ttl_seconds: int) -> None:
        await anyio.to_thread.run_sync(
            self._send_code_sync,
            phone,
            code,
            ttl_seconds,
        )

    def _send_code_sync(self, phone: str, code: str, ttl_seconds: int) -> None:
        if self._access_token in {"", "{{change-me}}"}:
            raise TelegramDeliveryError("telegram_gateway_unconfigured")
        payload = {
            "phone_number": phone,
            "code": code,
            "ttl": ttl_seconds,
            "payload": f"client-otp-{uuid.uuid4().hex[:16]}",
        }
        request = urllib.request.Request(  # noqa: S310 - base URL is an HTTPS Gateway setting.
            f"{self._api_base_url}/sendVerificationMessage",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 - request URL is validated configuration.
                request,
                timeout=self._timeout_seconds,
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            raise TelegramDeliveryError(str(exc)) from exc
        if not isinstance(body, dict) or body.get("ok") is not True:
            raise TelegramDeliveryError(str(body.get("error", "telegram_gateway_error")))


@dataclass(frozen=True)
class OtpRequestResult:
    phone: str
    expires_at: datetime
    resend_after_seconds: int


@dataclass(frozen=True)
class ClientOtpLoginResult:
    tokens: PlainSessionTokens
    principal: AuthenticatedPrincipal


@dataclass(frozen=True)
class ClientOtpVerifyResult:
    is_new: bool
    login: ClientOtpLoginResult | None = None


def resolve_client_ip(
    *,
    peer_host: str | None,
    x_forwarded_for: str | None,
    trusted_proxy_cidrs: Sequence[str],
) -> str:
    if peer_host is None:
        return "unknown"
    peer = _parse_ip(peer_host)
    if peer is None:
        return peer_host
    if x_forwarded_for and _is_trusted_proxy(peer, trusted_proxy_cidrs):
        hops: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
        for part in x_forwarded_for.split(","):
            hop = _parse_ip(part.strip())
            if hop is None:
                # Malformed entry — distrust the whole header.
                return str(peer)
            hops.append(hop)
        # Walk right→left: the right-most hop outside the trusted CIDRs is the
        # closest address a trusted proxy actually vouches for. Left-most
        # entries are client-supplied and forgeable.
        for hop in reversed(hops):
            if not _is_trusted_proxy(hop, trusted_proxy_cidrs):
                return str(hop)
        if hops:
            # Every hop is a trusted proxy — the chain origin is the client.
            return str(hops[0])
    return str(peer)


async def request_otp_code(
    db: AsyncSession,
    *,
    phone: str,
    request_ip: str,
    sender: OtpSender,
    now: datetime | None = None,
) -> OtpRequestResult:
    normalized_phone = normalize_uz_phone(phone)
    current = _current_time(now)
    await _enforce_send_limits(db, phone=normalized_phone, request_ip=request_ip, now=current)
    code = _generate_code()
    # The row is written before the delivery attempt so that failed sends also
    # count toward the cooldown and send caps — otherwise unreachable numbers
    # could be probed for free, without limit.
    challenge = PhoneVerificationChallenge(
        phone=normalized_phone,
        code_hash=hash_otp_code(code),
        request_ip=request_ip,
        expires_at=current + OTP_TTL,
        attempt_count=0,
        created_at=current,
    )
    db.add(challenge)
    await db.flush()
    if not settings.OTP_DEV_CODES:
        try:
            await sender.send_code(
                phone=normalized_phone,
                code=code,
                ttl_seconds=int(OTP_TTL.total_seconds()),
            )
        except TelegramDeliveryError as exc:
            # Burn the undelivered challenge: nobody received the code, so
            # nothing may remain guessable — but the row keeps counting.
            challenge.consumed_at = current
            await db.commit()
            logger.warning(
                "otp_delivery_failed",
                phone_suffix=normalized_phone[-4:],
                request_ip=request_ip,
                error=str(exc),
            )
            raise APIError(
                "phone_unreachable_on_telegram",
                "Phone is not reachable on Telegram",
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc
    return OtpRequestResult(
        phone=normalized_phone,
        expires_at=challenge.expires_at,
        resend_after_seconds=settings.OTP_RESEND_COOLDOWN_SECONDS,
    )


async def verify_otp_code(
    db: AsyncSession,
    *,
    phone: str,
    code: str,
    name: str | None,
    trace_id: str,
    device_info: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> ClientOtpVerifyResult:
    normalized_phone = normalize_uz_phone(phone)
    current = _current_time(now)
    if not CODE_RE.fullmatch(code.strip()):
        raise APIError("invalid_code", "Invalid code", status_code=status.HTTP_400_BAD_REQUEST)
    challenge = await _latest_open_challenge(db, phone=normalized_phone)
    if challenge is None:
        raise APIError("invalid_code", "Invalid code", status_code=status.HTTP_400_BAD_REQUEST)
    if _coerce_utc(challenge.expires_at) <= current:
        challenge.consumed_at = current
        await _commit_and_raise(
            db,
            APIError("code_expired", "Code expired", status_code=status.HTTP_400_BAD_REQUEST),
        )
    if challenge.attempt_count >= MAX_VERIFY_ATTEMPTS:
        challenge.consumed_at = current
        await _commit_and_raise(
            db,
            APIError(
                "too_many_attempts",
                "Too many verification attempts",
                status_code=status.HTTP_400_BAD_REQUEST,
            ),
        )
    if not _code_matches(code.strip(), challenge.code_hash):
        challenge.attempt_count += 1
        if challenge.attempt_count >= MAX_VERIFY_ATTEMPTS:
            challenge.consumed_at = current
            logger.warning(
                "otp_challenge_burned_too_many_attempts",
                phone_suffix=normalized_phone[-4:],
                request_ip=challenge.request_ip,
            )
            await _commit_and_raise(
                db,
                APIError(
                    "too_many_attempts",
                    "Too many verification attempts",
                    status_code=status.HTTP_400_BAD_REQUEST,
                ),
            )
        await _commit_and_raise(
            db,
            APIError(
                "invalid_code",
                "Invalid code",
                status_code=status.HTTP_400_BAD_REQUEST,
                details={"attempts_remaining": MAX_VERIFY_ATTEMPTS - challenge.attempt_count},
            ),
        )

    try:
        resolution = await find_or_create_client(db, phone=normalized_phone, name=name)
    except APIError as exc:
        if exc.code == "account_blocked":
            challenge.consumed_at = current
            await db.commit()
        raise
    if resolution is None:
        if name is None:
            # First-time phone, no name supplied yet → prompt the registration step.
            return ClientOtpVerifyResult(is_new=True)
        # A name was supplied but is blank/whitespace — reject it explicitly
        # instead of silently re-prompting forever (CB-79).
        raise APIError(
            "name_required",
            "Name is required",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    client = resolution.client

    client.last_login_at = current
    challenge.consumed_at = current
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=client.id,
        device_info=device_info,
        now=current,
    )
    session = await db.get(Session, tokens.session_id)
    if session is None:
        raise RuntimeError("created session row disappeared before principal resolution")
    principal = await principal_from_session(db, session, trace_id=trace_id)
    if principal is None:
        raise RuntimeError("created client session could not resolve an active principal")
    return ClientOtpVerifyResult(
        is_new=False,
        login=ClientOtpLoginResult(tokens=tokens, principal=principal),
    )


async def prune_expired_otp_challenges(db: AsyncSession, *, now: datetime | None = None) -> int:
    current = _current_time(now)
    stale_ids = (
        await db.scalars(
            select(PhoneVerificationChallenge.id).where(
                PhoneVerificationChallenge.created_at < current - CHALLENGE_RETENTION
            )
        )
    ).all()
    if stale_ids:
        await db.execute(
            delete(PhoneVerificationChallenge).where(PhoneVerificationChallenge.id.in_(stale_ids))
        )
    return len(stale_ids)


async def _commit_and_raise(db: AsyncSession, error: APIError) -> NoReturn:
    """Persist anti-abuse state, then reject the request.

    ``get_session`` rolls the transaction back on any exception, which would
    silently discard attempt counters and challenge burns (CB-133) — commit
    them explicitly before the error propagates.
    """
    await db.commit()
    raise error


def hash_otp_code(code: str) -> str:
    return hmac.new(
        settings.OTP_CODE_PEPPER.encode("utf-8"),
        code.encode("utf-8"),
        "sha256",
    ).hexdigest()


def _code_matches(code: str, stored_hash: str) -> bool:
    if settings.OTP_DEV_CODES and code in settings.OTP_DEV_CODES:
        return True
    return hmac.compare_digest(hash_otp_code(code), stored_hash)


async def _enforce_send_limits(
    db: AsyncSession,
    *,
    phone: str,
    request_ip: str,
    now: datetime,
) -> None:
    if not settings.OTP_RATE_LIMITS_ENABLED:
        return

    cooldown_row = await db.scalar(
        select(PhoneVerificationChallenge)
        .where(PhoneVerificationChallenge.phone == phone)
        .order_by(PhoneVerificationChallenge.created_at.desc())
        .limit(1)
    )
    if cooldown_row is not None:
        retry_at = _coerce_utc(cooldown_row.created_at) + timedelta(
            seconds=settings.OTP_RESEND_COOLDOWN_SECONDS
        )
        if retry_at > now:
            _raise_rate_limited(retry_at, now)

    hour = timedelta(hours=1)
    day = timedelta(hours=24)
    # (name, phone filter, ip filter, window, cap) — the global rows have no
    # filters and cap the platform-wide Telegram spend regardless of how an
    # attack is distributed across phones and IPs.
    budgets: tuple[tuple[str, str | None, str | None, timedelta, int], ...] = (
        ("phone_hourly", phone, None, hour, settings.OTP_PHONE_SENDS_PER_HOUR),
        ("phone_daily", phone, None, day, settings.OTP_PHONE_SENDS_PER_DAY),
        ("ip_hourly", None, request_ip, hour, settings.OTP_IP_SENDS_PER_HOUR),
        ("ip_daily", None, request_ip, day, settings.OTP_IP_SENDS_PER_DAY),
        ("global_hourly", None, None, hour, settings.OTP_GLOBAL_SENDS_PER_HOUR),
        ("global_daily", None, None, day, settings.OTP_GLOBAL_SENDS_PER_DAY),
    )
    for name, phone_filter, ip_filter, window, cap in budgets:
        await _enforce_window_limit(
            db,
            name=name,
            phone=phone_filter,
            request_ip=ip_filter,
            window=window,
            cap=cap,
            now=now,
        )


async def _enforce_window_limit(
    db: AsyncSession,
    *,
    name: str,
    phone: str | None,
    request_ip: str | None,
    window: timedelta,
    cap: int,
    now: datetime,
) -> None:
    window_start = now - window
    query = (
        select(func.count())
        .select_from(PhoneVerificationChallenge)
        .where(PhoneVerificationChallenge.created_at >= window_start)
    )
    if phone is not None:
        query = query.where(PhoneVerificationChallenge.phone == phone)
    if request_ip is not None:
        query = query.where(PhoneVerificationChallenge.request_ip == request_ip)
    count = await db.scalar(query)
    if (count or 0) < cap:
        return
    if phone is None and request_ip is None:
        # Platform-wide budget exhausted — either legit growth or an active
        # cost attack. Surfaced loudly so the operator looks before the bill.
        logger.warning("otp_global_send_cap_reached", limit=name, cap=cap)
    oldest = await _oldest_in_window(
        db,
        phone=phone,
        request_ip=request_ip,
        window_start=window_start,
    )
    _raise_rate_limited(_coerce_utc(oldest.created_at) + window, now)


async def _oldest_in_window(
    db: AsyncSession,
    *,
    phone: str | None,
    request_ip: str | None,
    window_start: datetime,
) -> PhoneVerificationChallenge:
    query = select(PhoneVerificationChallenge).where(
        PhoneVerificationChallenge.created_at >= window_start
    )
    if phone is not None:
        query = query.where(PhoneVerificationChallenge.phone == phone)
    if request_ip is not None:
        query = query.where(PhoneVerificationChallenge.request_ip == request_ip)
    row = await db.scalar(query.order_by(PhoneVerificationChallenge.created_at).limit(1))
    if row is None:
        raise RuntimeError("rate-limit count existed without a matching challenge row")
    return row


async def _latest_open_challenge(
    db: AsyncSession,
    *,
    phone: str,
) -> PhoneVerificationChallenge | None:
    # FOR UPDATE serializes concurrent guesses on the same challenge so no
    # attempt increment is lost to a read-modify-write race (no-op on SQLite).
    row = await db.scalar(
        select(PhoneVerificationChallenge)
        .where(
            PhoneVerificationChallenge.phone == phone,
            PhoneVerificationChallenge.consumed_at.is_(None),
        )
        .order_by(PhoneVerificationChallenge.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    return row


def _raise_rate_limited(retry_at: datetime, now: datetime) -> None:
    retry_after = max(1, int((retry_at - now).total_seconds()))
    raise APIError(
        "code_send_rate_limited",
        "Code send rate limited",
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        details={"retry_after_seconds": retry_after},
    )


def _generate_code() -> str:
    return str(secrets.randbelow(1_000_000)).zfill(6)


def _current_time(now: datetime | None) -> datetime:
    return _coerce_utc(now) if now is not None else datetime.now(UTC)


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _is_trusted_proxy(
    peer: ipaddress.IPv4Address | ipaddress.IPv6Address,
    trusted_proxy_cidrs: Sequence[str],
) -> bool:
    for raw_cidr in trusted_proxy_cidrs:
        try:
            network = ipaddress.ip_network(raw_cidr, strict=False)
        except ValueError:
            continue
        if peer in network:
            return True
    return False
