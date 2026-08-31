"""Workshop walk-in client resolve/lookup use cases.

Staff with ``manage_orders`` on at least one branch may resolve a walk-in
client by phone (find-or-create) to place an order on their behalf. Resolve
discloses an existing client's stored name to staff — a deliberate, recorded
decision — so every call is audited and rate limited per staff user following
the Telegram-login budget convention.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import UserStatus
from app.modules.access.authz import require_manage_orders_workshop
from app.modules.access.clients import ClientResolution, find_or_create_client, normalize_uz_phone
from app.modules.access.contracts import Client
from app.modules.cutting.contracts import CuttingDraft
from app.modules.sales.contracts import Order
from app.modules.support.api import record_action
from app.modules.support.contracts import ActionLog

# Per-staff-user resolve budget (login-budget convention: constant + windowed
# count). Generous for a busy counter, tight enough to blunt phone probing.
CLIENT_RESOLVES_PER_STAFF_PER_HOUR = 30
CLIENT_RESOLVE_ACTION = "workshop_client.resolve"

# Lookup discloses exactly what resolve does — an existing client's name — so it
# carries the same audit and the same class of budget. Its own, larger one:
# the counter looks a number up before deciding to write an order, so a staffer
# legitimately reaches more lookups than creates in an hour. A lookup that is
# not followed by a resolve is the normal case, not a suspicious one.
CLIENT_LOOKUPS_PER_STAFF_PER_HOUR = 90
CLIENT_LOOKUP_ACTION = "workshop_client.lookup"


async def resolve_walk_in_client(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    phone: str,
    name: str | None,
    now: datetime | None = None,
) -> ClientResolution:
    workshop_id = require_manage_orders_workshop(principal)
    normalized_phone = normalize_uz_phone(phone)
    current = now if now is not None else datetime.now(UTC)
    await _enforce_resolve_limit(db, staff_user_id=principal.principal_id, now=current)
    try:
        resolution = await find_or_create_client(db, phone=normalized_phone, name=name)
    except APIError as exc:
        if exc.code == "account_blocked":
            await _record_resolve(
                db,
                principal=principal,
                workshop_id=workshop_id,
                phone=normalized_phone,
                client_id=None,
                created=False,
                outcome="account_blocked",
            )
        raise
    if resolution is None:
        raise APIError(
            "client_name_required",
            "Client name is required",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    await _record_resolve(
        db,
        principal=principal,
        workshop_id=workshop_id,
        phone=normalized_phone,
        client_id=resolution.client.id,
        created=resolution.created,
        outcome="created" if resolution.created else "found",
    )
    return resolution


async def lookup_walk_in_client(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    phone: str,
    now: datetime | None = None,
) -> Client | None:
    """Find the client owning ``phone`` without creating one.

    The counter types a phone before it knows whether the person is already in
    the base; `resolve_walk_in_client` cannot answer that, because asking it
    *writes* — a mistyped digit would mint a client. This is the read-only half,
    and it carries the same two controls, because it discloses the same fact: a
    per-staff hourly budget and an audit row per call.

    A blocked account reads as a miss rather than raising: the operator is
    asking "may I write an order for this number", and the answer for a blocked
    client is no. Raising here would also turn the lookup into an oracle for
    account status, which the resolve path deliberately only reveals on a real
    attempt to act.
    """
    workshop_id = require_manage_orders_workshop(principal)
    normalized_phone = normalize_uz_phone(phone)
    current = now if now is not None else datetime.now(UTC)
    await _enforce_call_limit(
        db,
        staff_user_id=principal.principal_id,
        now=current,
        action=CLIENT_LOOKUP_ACTION,
        budget=CLIENT_LOOKUPS_PER_STAFF_PER_HOUR,
        code="client_lookup_rate_limited",
    )
    client = await db.scalar(select(Client).where(Client.phone == normalized_phone))
    if client is not None and client.status is not UserStatus.ACTIVE:
        client = None
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action=CLIENT_LOOKUP_ACTION,
        entity_type="client",
        entity_id=client.id if client is not None else None,
        workshop_id=workshop_id,
        summary="Looked up a walk-in client by phone",
        details={"phone": normalized_phone, "found": client is not None},
    )
    return client


async def get_workshop_client(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    client_id: uuid.UUID,
) -> Client:
    """Return a client visible to this workshop, else 404.

    Simplest sound rule (checkout refresh-safety): the client is visible when
    they have at least one cutting draft minted via this workshop or at least
    one order with this workshop.
    """
    workshop_id = require_manage_orders_workshop(principal)
    client = await db.get(Client, client_id)
    if client is None:
        raise _client_not_found()
    draft_id = await db.scalar(
        select(CuttingDraft.id)
        .where(
            CuttingDraft.client_id == client_id,
            CuttingDraft.created_via_workshop_id == workshop_id,
        )
        .limit(1)
    )
    if draft_id is None:
        order_id = await db.scalar(
            select(Order.id)
            .where(Order.client_id == client_id, Order.workshop_id == workshop_id)
            .limit(1)
        )
        if order_id is None:
            raise _client_not_found()
    return client


async def _enforce_resolve_limit(
    db: AsyncSession,
    *,
    staff_user_id: uuid.UUID,
    now: datetime,
) -> None:
    await _enforce_call_limit(
        db,
        staff_user_id=staff_user_id,
        now=now,
        action=CLIENT_RESOLVE_ACTION,
        budget=CLIENT_RESOLVES_PER_STAFF_PER_HOUR,
        code="client_resolve_rate_limited",
    )


async def _enforce_call_limit(
    db: AsyncSession,
    *,
    staff_user_id: uuid.UUID,
    now: datetime,
    action: str,
    budget: int,
    code: str,
) -> None:
    """One windowed-count limiter for both disclosure paths.

    The window is derived from the audit log rather than a counter column, so a
    call that was recorded is a call that was spent — the two cannot drift.
    """
    if not settings.TELEGRAM_LOGIN_RATE_LIMITS_ENABLED:
        return
    window_start = now - timedelta(hours=1)
    count = await db.scalar(
        select(func.count())
        .select_from(ActionLog)
        .where(
            ActionLog.action == action,
            ActionLog.actor_user_id == staff_user_id,
            ActionLog.created_at >= window_start,
        )
    )
    if (count or 0) < budget:
        return
    oldest = await db.scalar(
        select(ActionLog)
        .where(
            ActionLog.action == action,
            ActionLog.actor_user_id == staff_user_id,
            ActionLog.created_at >= window_start,
        )
        .order_by(ActionLog.created_at)
        .limit(1)
    )
    if oldest is None:
        raise RuntimeError("rate-limit count existed without a matching audit row")
    retry_at = _coerce_utc(oldest.created_at) + timedelta(hours=1)
    retry_after = max(1, int((retry_at - now).total_seconds()))
    raise APIError(
        code,
        "Client disclosure rate limited",
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        details={"retry_after_seconds": retry_after},
    )


async def _record_resolve(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    workshop_id: uuid.UUID,
    phone: str,
    client_id: uuid.UUID | None,
    created: bool,
    outcome: str,
) -> None:
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action=CLIENT_RESOLVE_ACTION,
        entity_type="client",
        entity_id=client_id,
        workshop_id=workshop_id,
        summary="Resolved walk-in client by phone",
        details={"phone": phone, "created": created, "outcome": outcome},
    )


def _client_not_found() -> APIError:
    return APIError(
        "client_not_found",
        "Client not found",
        status_code=status.HTTP_404_NOT_FOUND,
    )


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
