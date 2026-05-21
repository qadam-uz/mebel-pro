"""Workshop administration — provisioning, profile, block/unblock, branches.

Provisioning creates the Workshop and its first owner atomically (one
transaction; if either fails, nothing persists). Branch CRUD is owner-only and
creates the branch's empty BranchPricing row alongside the branch. Tenancy and
the blocking cascade follow docs/access-patterns.md and
docs/ref/features/access-management.md.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import bad_request, conflict, forbidden, not_found
from app.core.principal import Principal
from app.core.security import generate_temp_password, hash_password, password_complexity_ok
from app.models.catalog import BranchMaterial, BranchPricing
from app.models.enums import (
    BranchStatus,
    OrderStatus,
    WorkshopStatus,
)
from app.models.identity import WorkshopUser
from app.models.inventory import StockItem
from app.models.sales import Order
from app.models.workshop import Branch, Workshop
from app.services import audit, sessions

_OPEN_ORDER_STATUSES = (
    OrderStatus.NEW,
    OrderStatus.CONFIRMED,
    OrderStatus.CUTTING,
    OrderStatus.EDGE_BANDING,
    OrderStatus.READY,
)


@dataclass
class ProvisionedWorkshop:
    workshop: Workshop
    owner: WorkshopUser
    temp_password: str


def _normalise_login(login: str) -> str:
    return login.strip().lower()


def _resolve_password(password: str | None) -> tuple[str, str]:
    plaintext = password or generate_temp_password()
    if password and not password_complexity_ok(password):
        raise bad_request(
            "Password must be ≥ 8 chars with an upper, a lower, and a digit.",
            code="weak_password",
        )
    return plaintext, hash_password(plaintext)


# --- provisioning (platform operator) --------------------------------------


async def provision_workshop(
    db: AsyncSession,
    actor: Principal,
    *,
    name: str,
    phone: str,
    address: str | None,
    logo_file_id: uuid.UUID | None,
    owner_full_name: str,
    owner_login: str,
    owner_phone: str,
    owner_password: str | None = None,
) -> ProvisionedWorkshop:
    """Create a Workshop + its owner WorkshopUser atomically.

    Both rows live in one flush; the caller's session commits on success and
    rolls back on any error, so a half-provisioned workshop never persists.
    """
    owner_login = _normalise_login(owner_login)
    plaintext, password_hash = _resolve_password(owner_password)

    workshop = Workshop(
        name=name.strip(),
        phone=phone.strip(),
        address=address.strip() if address else None,
        logo_file_id=logo_file_id,
        status=WorkshopStatus.ACTIVE,
    )
    db.add(workshop)
    await db.flush()

    owner = WorkshopUser(
        workshop_id=workshop.id,
        login=owner_login,
        password_hash=password_hash,
        full_name=owner_full_name.strip(),
        phone=owner_phone.strip(),
        is_owner=True,
        force_password_change=True,
    )
    db.add(owner)
    await db.flush()

    workshop.owner_user_id = owner.id
    await db.flush()

    await audit.record_action(
        db,
        actor=actor,
        action="workshop.provisioned",
        entity_type="workshop",
        entity_id=workshop.id,
        workshop_id=workshop.id,
        summary=f"Provisioned workshop {workshop.name} with owner {owner_login}",
    )
    await db.refresh(workshop)
    return ProvisionedWorkshop(workshop=workshop, owner=owner, temp_password=plaintext)


# --- read (platform operator) ----------------------------------------------


async def get_workshop(db: AsyncSession, workshop_id: uuid.UUID) -> Workshop:
    ws = await db.get(Workshop, workshop_id)
    if ws is None:
        raise not_found("Workshop not found.")
    return ws


async def list_workshops(db: AsyncSession) -> list[Workshop]:
    return list(
        (await db.execute(select(Workshop).order_by(Workshop.created_at.desc()))).scalars().all()
    )


async def workshop_enrichment(db: AsyncSession, workshop: Workshop) -> dict[str, Any]:
    """Owner name/phone + branches count + orders-30d count for a workshop row."""
    owner_name: str | None = None
    owner_phone: str | None = None
    if workshop.owner_user_id is not None:
        owner = await db.get(WorkshopUser, workshop.owner_user_id)
        if owner is not None:
            owner_name = owner.full_name
            owner_phone = owner.phone
    branches_count = (
        await db.execute(
            select(func.count()).select_from(Branch).where(Branch.workshop_id == workshop.id)
        )
    ).scalar_one()
    since = datetime.now(UTC) - timedelta(days=30)
    orders_30d = (
        await db.execute(
            select(func.count())
            .select_from(Order)
            .where(Order.workshop_id == workshop.id, Order.created_at >= since)
        )
    ).scalar_one()
    return {
        "owner_name": owner_name,
        "owner_phone": owner_phone,
        "branches_count": int(branches_count),
        "orders_30d_count": int(orders_30d),
    }


# --- block / unblock (platform operator) -----------------------------------


async def set_workshop_status(
    db: AsyncSession, actor: Principal, workshop_id: uuid.UUID, *, blocked: bool, reason: str
) -> Workshop:
    ws = await get_workshop(db, workshop_id)
    from_status = ws.status
    if blocked:
        ws.status = WorkshopStatus.BLOCKED
        # Block-cascade: revoke owner + staff sessions. Clients are unaffected.
        await sessions.revoke_workshop_sessions(db, ws.id)
    else:
        ws.status = WorkshopStatus.ACTIVE
        # Unblock does NOT restore sessions — users log in again.
    log = await audit.record_action(
        db,
        actor=actor,
        action="workshop.blocked" if blocked else "workshop.unblocked",
        entity_type="workshop",
        entity_id=ws.id,
        workshop_id=ws.id,
        summary=reason,
    )
    await audit.record_status_change(
        db,
        entity_type="workshop",
        entity_id=ws.id,
        from_status=from_status.value,
        to_status=ws.status.value,
        actor=actor,
        workshop_id=ws.id,
        reason=reason,
        action_log_id=log.id,
    )
    await db.refresh(ws)
    return ws


# --- profile edit (owner OR platform operator) -----------------------------


async def edit_workshop_profile(
    db: AsyncSession,
    actor: Principal,
    workshop_id: uuid.UUID,
    *,
    name: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    logo_file_id: uuid.UUID | None = None,
    address_set: bool = False,
    logo_file_id_set: bool = False,
) -> Workshop:
    ws = await get_workshop(db, workshop_id)
    if name is not None:
        ws.name = name.strip()
    if phone is not None:
        ws.phone = phone.strip()
    if address_set:
        ws.address = address.strip() if address else None
    if logo_file_id_set:
        ws.logo_file_id = logo_file_id
    await audit.record_action(
        db,
        actor=actor,
        action="workshop.profile_updated",
        entity_type="workshop",
        entity_id=ws.id,
        workshop_id=ws.id,
    )
    await db.refresh(ws)
    return ws


# --- branches (owner-only writes) ------------------------------------------


async def owned_branch(db: AsyncSession, principal: Principal, branch_id: uuid.UUID) -> Branch:
    """Resolve a branch and verify it belongs to the principal's workshop.

    Tenancy is derived from stored data — the branch's ``workshop_id`` must match
    the principal's workshop. Cross-tenant access is ``not_found`` (no oracle).
    """
    branch = await db.get(Branch, branch_id)
    if branch is None or branch.workshop_id != principal.workshop_id:
        raise not_found("Branch not found.")
    return branch


async def create_branch(
    db: AsyncSession,
    owner: Principal,
    *,
    name: str,
    address: str,
    phone: str,
    latitude: float | None,
    longitude: float | None,
    working_hours: dict[str, Any],
) -> Branch:
    assert owner.workshop_id is not None
    branch = Branch(
        workshop_id=owner.workshop_id,
        name=name.strip(),
        address=address.strip(),
        phone=phone.strip(),
        latitude=latitude,
        longitude=longitude,
        working_hours=working_hours or {},
        status=BranchStatus.ACTIVE,
    )
    db.add(branch)
    await db.flush()
    # Each branch gets its (empty) pricing row at creation.
    db.add(BranchPricing(branch_id=branch.id, cutting_model=None, cutting_rate_tiyin=0))
    await db.flush()
    await audit.record_action(
        db,
        actor=owner,
        action="branch.created",
        entity_type="branch",
        entity_id=branch.id,
        workshop_id=owner.workshop_id,
        branch_id=branch.id,
        summary=f"Created branch {branch.name}",
    )
    await db.refresh(branch)
    return branch


async def edit_branch(
    db: AsyncSession,
    owner: Principal,
    branch_id: uuid.UUID,
    *,
    name: str | None = None,
    address: str | None = None,
    phone: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    latitude_set: bool = False,
    longitude_set: bool = False,
    working_hours: dict[str, Any] | None = None,
) -> Branch:
    branch = await owned_branch(db, owner, branch_id)
    if name is not None:
        branch.name = name.strip()
    if address is not None:
        branch.address = address.strip()
    if phone is not None:
        branch.phone = phone.strip()
    if latitude_set:
        branch.latitude = latitude
    if longitude_set:
        branch.longitude = longitude
    if working_hours is not None:
        branch.working_hours = working_hours
    await audit.record_action(
        db,
        actor=owner,
        action="branch.updated",
        entity_type="branch",
        entity_id=branch.id,
        workshop_id=owner.workshop_id,
        branch_id=branch.id,
    )
    await db.refresh(branch)
    return branch


async def change_branch_status(
    db: AsyncSession,
    owner: Principal,
    branch_id: uuid.UUID,
    *,
    status: BranchStatus,
    closed_reason: str | None = None,
) -> Branch:
    branch = await owned_branch(db, owner, branch_id)
    from_status = branch.status
    branch.status = status
    # closed_reason only meaningful for temporarily_closed; cleared otherwise.
    branch.closed_reason = closed_reason if status is BranchStatus.TEMPORARILY_CLOSED else None
    # Status change does NOT revoke sessions or grants (spec).
    log = await audit.record_action(
        db,
        actor=owner,
        action="branch.status_changed",
        entity_type="branch",
        entity_id=branch.id,
        workshop_id=owner.workshop_id,
        branch_id=branch.id,
        summary=f"{from_status.value} → {status.value}",
    )
    await audit.record_status_change(
        db,
        entity_type="branch",
        entity_id=branch.id,
        from_status=from_status.value,
        to_status=status.value,
        actor=owner,
        workshop_id=owner.workshop_id,
        branch_id=branch.id,
        reason=branch.closed_reason,
        action_log_id=log.id,
    )
    await db.refresh(branch)
    return branch


async def list_branches(db: AsyncSession, principal: Principal) -> list[Branch]:
    """Owner sees every branch; staff see only branches they hold any grant on."""
    assert principal.workshop_id is not None
    stmt = select(Branch).where(Branch.workshop_id == principal.workshop_id)
    if not principal.is_owner:
        accessible = principal.accessible_branches
        if not accessible:
            return []
        stmt = stmt.where(Branch.id.in_(accessible))
    stmt = stmt.order_by(Branch.created_at.asc())
    return list((await db.execute(stmt)).scalars().all())


async def readable_branch(db: AsyncSession, principal: Principal, branch_id: uuid.UUID) -> Branch:
    """A branch the principal may read: owner → any in workshop; staff → granted."""
    branch = await owned_branch(db, principal, branch_id)
    if not principal.is_owner and branch.id not in principal.accessible_branches:
        raise forbidden()
    return branch


async def branch_enrichment(db: AsyncSession, branch: Branch) -> dict[str, int]:
    materials_count = (
        await db.execute(
            select(func.count())
            .select_from(BranchMaterial)
            .where(BranchMaterial.branch_id == branch.id)
        )
    ).scalar_one()
    low_stock_count = (
        await db.execute(
            select(func.count())
            .select_from(StockItem)
            .where(
                StockItem.branch_id == branch.id,
                StockItem.on_hand <= StockItem.min_stock,
            )
        )
    ).scalar_one()
    active_orders_count = (
        await db.execute(
            select(func.count())
            .select_from(Order)
            .where(Order.branch_id == branch.id, Order.status.in_(_OPEN_ORDER_STATUSES))
        )
    ).scalar_one()
    return {
        "materials_count": int(materials_count),
        "low_stock_count": int(low_stock_count),
        "active_orders_count": int(active_orders_count),
    }


# --- workshop self (owner, workshop app) -----------------------------------


async def get_owner_workshop(db: AsyncSession, owner: Principal) -> Workshop:
    assert owner.workshop_id is not None
    return await get_workshop(db, owner.workshop_id)


def assert_active_workshop(ws: Workshop) -> None:
    if ws.status is not WorkshopStatus.ACTIVE:
        raise conflict("This workshop is blocked.", code="workshop_blocked")
