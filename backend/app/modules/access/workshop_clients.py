"""Workshop walk-in client resolve/lookup use cases.

Staff with ``manage_orders`` on at least one branch may resolve a walk-in
client by phone (find-or-create) to place an order on their behalf. Resolve
discloses an existing client's stored name to staff — a deliberate, recorded
decision — so every call is audited and rate limited per staff user following
the OTP-limits convention.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.modules.access.authz import require_manage_orders_workshop
from app.modules.access.clients import ClientResolution, find_or_create_client, normalize_uz_phone
from app.modules.access.contracts import Client
from app.modules.cutting.contracts import CuttingDraft
from app.modules.sales.contracts import Order
from app.modules.support.api import record_action
from app.modules.support.contracts import ActionLog

# Per-staff-user resolve budget (OTP-limits convention: constant + windowed
# count). Generous for a busy counter, tight enough to blunt phone probing.
CLIENT_RESOLVES_PER_STAFF_PER_HOUR = 30
CLIENT_RESOLVE_ACTION = "workshop_client.resolve"


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
    if not settings.OTP_RATE_LIMITS_ENABLED:
        return
    window_start = now - timedelta(hours=1)
    count = await db.scalar(
        select(func.count())
        .select_from(ActionLog)
        .where(
            ActionLog.action == CLIENT_RESOLVE_ACTION,
            ActionLog.actor_user_id == staff_user_id,
            ActionLog.created_at >= window_start,
        )
    )
    if (count or 0) < CLIENT_RESOLVES_PER_STAFF_PER_HOUR:
        return
    oldest = await db.scalar(
        select(ActionLog)
        .where(
            ActionLog.action == CLIENT_RESOLVE_ACTION,
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
        "client_resolve_rate_limited",
        "Client resolve rate limited",
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
