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
from typing import Any, Protocol

import anyio
from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal
from app.models.enums import AuthenticatedPrincipalType, UserStatus
from app.modules.access.contracts import Client, PhoneVerificationChallenge, Session
from app.modules.access.sessions import PlainSessionTokens, create_session, principal_from_session

PHONE_RE = re.compile(r"^\+998\d{9}$")
CODE_RE = re.compile(r"^\d{6}$")
OTP_TTL = timedelta(minutes=5)
RESEND_COOLDOWN = timedelta(seconds=60)
PHONE_SENDS_PER_HOUR = 5
IP_SENDS_PER_HOUR = 30
MAX_VERIFY_ATTEMPTS = 5


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


def normalize_uz_phone(phone: str) -> str:
    normalized = phone.strip()
    if not PHONE_RE.fullmatch(normalized):
        raise APIError("invalid_phone", "Invalid phone", status_code=status.HTTP_400_BAD_REQUEST)
    return normalized


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
        forwarded = _parse_ip(x_forwarded_for.split(",", maxsplit=1)[0].strip())
        if forwarded is not None:
            return str(forwarded)
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
    if not settings.OTP_DEV_CODES:
        try:
            await sender.send_code(
                phone=normalized_phone,
                code=code,
                ttl_seconds=int(OTP_TTL.total_seconds()),
            )
        except TelegramDeliveryError as exc:
            raise APIError(
                "phone_unreachable_on_telegram",
                "Phone is not reachable on Telegram",
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc
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
    return OtpRequestResult(
        phone=normalized_phone,
        expires_at=challenge.expires_at,
        resend_after_seconds=int(RESEND_COOLDOWN.total_seconds()),
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
        raise APIError("code_expired", "Code expired", status_code=status.HTTP_400_BAD_REQUEST)
    if challenge.attempt_count >= MAX_VERIFY_ATTEMPTS:
        challenge.consumed_at = current
        raise APIError(
            "too_many_attempts",
            "Too many verification attempts",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if not _code_matches(code.strip(), challenge.code_hash):
        challenge.attempt_count += 1
        if challenge.attempt_count >= MAX_VERIFY_ATTEMPTS:
            challenge.consumed_at = current
            raise APIError(
                "too_many_attempts",
                "Too many verification attempts",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        raise APIError("invalid_code", "Invalid code", status_code=status.HTTP_400_BAD_REQUEST)

    client = await db.scalar(select(Client).where(Client.phone == normalized_phone))
    if client is None:
        client_name = _normalize_name(name)
        if client_name is None:
            return ClientOtpVerifyResult(is_new=True)
        client = Client(phone=normalized_phone, name=client_name, status=UserStatus.ACTIVE)
        db.add(client)
        await db.flush()
    elif client.status is not UserStatus.ACTIVE:
        challenge.consumed_at = current
        raise APIError(
            "account_blocked",
            "Account is blocked",
            status_code=status.HTTP_403_FORBIDDEN,
        )

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
    cooldown_row = await db.scalar(
        select(PhoneVerificationChallenge)
        .where(PhoneVerificationChallenge.phone == phone)
        .order_by(PhoneVerificationChallenge.created_at.desc())
        .limit(1)
    )
    if cooldown_row is not None:
        retry_at = _coerce_utc(cooldown_row.created_at) + RESEND_COOLDOWN
        if retry_at > now:
            _raise_rate_limited(retry_at, now)

    window_start = now - timedelta(hours=1)
    phone_count = await db.scalar(
        select(func.count())
        .select_from(PhoneVerificationChallenge)
        .where(
            PhoneVerificationChallenge.phone == phone,
            PhoneVerificationChallenge.created_at >= window_start,
        )
    )
    if (phone_count or 0) >= PHONE_SENDS_PER_HOUR:
        oldest = await _oldest_in_window(
            db,
            phone=phone,
            request_ip=None,
            window_start=window_start,
        )
        _raise_rate_limited(_coerce_utc(oldest.created_at) + timedelta(hours=1), now)

    ip_count = await db.scalar(
        select(func.count())
        .select_from(PhoneVerificationChallenge)
        .where(
            PhoneVerificationChallenge.request_ip == request_ip,
            PhoneVerificationChallenge.created_at >= window_start,
        )
    )
    if (ip_count or 0) >= IP_SENDS_PER_HOUR:
        oldest = await _oldest_in_window(
            db,
            phone=None,
            request_ip=request_ip,
            window_start=window_start,
        )
        _raise_rate_limited(_coerce_utc(oldest.created_at) + timedelta(hours=1), now)


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
    row = await db.scalar(
        select(PhoneVerificationChallenge)
        .where(
            PhoneVerificationChallenge.phone == phone,
            PhoneVerificationChallenge.consumed_at.is_(None),
        )
        .order_by(PhoneVerificationChallenge.created_at.desc())
        .limit(1)
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


def _normalize_name(name: str | None) -> str | None:
    if name is None:
        return None
    normalized = " ".join(name.strip().split())
    if not normalized:
        return None
    if len(normalized) > 80:
        raise APIError("name_required", "Name is required", status_code=status.HTTP_400_BAD_REQUEST)
    return normalized


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
