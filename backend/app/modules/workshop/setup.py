"""Workshop profile, branch, and pricing setup use cases."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import BranchStatus, OrderStatus
from app.modules.access.api import normalize_uz_phone
from app.modules.access.contracts import PermissionGrant, WorkshopUser
from app.modules.catalog.contracts import BranchMaterial, BranchPricing
from app.modules.inventory.contracts import StockItem
from app.modules.sales.contracts import Order
from app.modules.support.api import (
    IMAGE_CONTENT_TYPES,
    record_action,
    record_status_change,
    replace_attached_file,
)
from app.modules.workshop.contracts import Branch, Workshop
from app.modules.workshop.schemas import (
    BranchCreateRequest,
    BranchPatchRequest,
    BranchPricingPutRequest,
    BranchStatusRequest,
    WorkshopSettingsPatchRequest,
    dump_working_hours,
)
from app.modules.workshop.users import require_workshop_owner, require_workshop_principal


@dataclass(frozen=True)
class BranchOperationalCounts:
    active_orders: int = 0
    materials: int = 0
    low_stock: int = 0
    staff: int = 0


async def get_settings(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
) -> Workshop:
    workshop_id = require_workshop_owner(principal)
    workshop = await db.get(Workshop, workshop_id)
    if workshop is None:
        raise APIError("workshop_not_found", "Workshop not found", status_code=404)
    return workshop


async def update_settings(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: WorkshopSettingsPatchRequest,
) -> Workshop:
    workshop = await get_settings(db, principal=principal)
    if "name" in payload.model_fields_set and payload.name is not None:
        workshop.name = _required_text(payload.name, "workshop_name_required")
    if "phone" in payload.model_fields_set and payload.phone is not None:
        workshop.phone = normalize_uz_phone(payload.phone)
    if "address" in payload.model_fields_set:
        workshop.address = _optional_text(payload.address)
    if "logo_file_id" in payload.model_fields_set:
        workshop.logo_file_id = await replace_attached_file(
            db,
            principal=principal,
            file_id=payload.logo_file_id,
            current_file_id=workshop.logo_file_id,
            entity_type="workshop",
            entity_id=workshop.id,
            allowed_content_types=IMAGE_CONTENT_TYPES,
        )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="workshop.settings.update",
        entity_type="workshop",
        entity_id=workshop.id,
        workshop_id=workshop.id,
        summary=f"Updated workshop settings for {workshop.name}",
    )
    await db.refresh(workshop)
    return workshop


async def list_branches(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
) -> list[Branch]:
    workshop_id = require_workshop_owner(principal)
    return list(
        (
            await db.scalars(
                select(Branch).where(Branch.workshop_id == workshop_id).order_by(Branch.name)
            )
        ).all()
    )


async def branch_operational_counts(
    db: AsyncSession,
    branch_ids: list[uuid.UUID],
) -> dict[uuid.UUID, BranchOperationalCounts]:
    ids = list(dict.fromkeys(branch_ids))
    if not ids:
        return {}
    active_orders: dict[uuid.UUID, int] = {}
    material_counts: dict[uuid.UUID, int] = {}
    low_stock_counts: dict[uuid.UUID, int] = {}
    staff_by_branch: dict[uuid.UUID, set[uuid.UUID]] = {branch_id: set() for branch_id in ids}

    order_rows = (
        await db.execute(
            select(Order.branch_id, func.count(Order.id))
            .where(
                Order.branch_id.in_(ids),
                ~Order.status.in_([OrderStatus.COMPLETED, OrderStatus.CANCELLED]),
            )
            .group_by(Order.branch_id)
        )
    ).all()
    for branch_id, count in order_rows:
        active_orders[branch_id] = int(count)

    material_rows = (
        await db.execute(
            select(BranchMaterial.branch_id, func.count(BranchMaterial.id))
            .where(BranchMaterial.branch_id.in_(ids))
            .group_by(BranchMaterial.branch_id)
        )
    ).all()
    for branch_id, count in material_rows:
        material_counts[branch_id] = int(count)

    low_stock_rows = (
        await db.execute(
            select(StockItem.branch_id, func.count(StockItem.id))
            .where(
                StockItem.branch_id.in_(ids),
                StockItem.on_hand <= StockItem.min_stock,
            )
            .group_by(StockItem.branch_id)
        )
    ).all()
    for branch_id, count in low_stock_rows:
        low_stock_counts[branch_id] = int(count)

    home_rows = (
        await db.execute(
            select(WorkshopUser.home_branch_id, WorkshopUser.id).where(
                WorkshopUser.home_branch_id.in_(ids)
            )
        )
    ).all()
    for branch_id, user_id in home_rows:
        if branch_id in staff_by_branch:
            staff_by_branch[branch_id].add(user_id)

    grant_rows = (
        await db.execute(
            select(PermissionGrant.branch_id, PermissionGrant.workshop_user_id).where(
                PermissionGrant.branch_id.in_(ids)
            )
        )
    ).all()
    for branch_id, user_id in grant_rows:
        staff_by_branch[branch_id].add(user_id)

    return {
        branch_id: BranchOperationalCounts(
            active_orders=active_orders.get(branch_id, 0),
            materials=material_counts.get(branch_id, 0),
            low_stock=low_stock_counts.get(branch_id, 0),
            staff=len(staff_by_branch.get(branch_id, set())),
        )
        for branch_id in ids
    }


async def create_branch(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: BranchCreateRequest,
) -> Branch:
    workshop_id = require_workshop_owner(principal)
    _validate_coordinates(payload.latitude, payload.longitude)
    branch = Branch(
        workshop_id=workshop_id,
        name=_required_text(payload.name, "branch_name_required"),
        address=_required_text(payload.address, "branch_address_required"),
        phone=normalize_uz_phone(payload.phone),
        latitude=payload.latitude,
        longitude=payload.longitude,
        working_hours=dump_working_hours(payload.working_hours),
        status=BranchStatus.ACTIVE,
    )
    db.add(branch)
    await db.flush()
    db.add(BranchPricing(branch_id=branch.id))
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="workshop.branch.create",
        entity_type="branch",
        entity_id=branch.id,
        workshop_id=workshop_id,
        branch_id=branch.id,
        summary=f"Created branch {branch.name}",
    )
    await db.refresh(branch)
    return branch


async def get_branch(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
) -> Branch:
    workshop_id = require_workshop_principal(principal)
    branch = await db.get(Branch, branch_id)
    if branch is None or branch.workshop_id != workshop_id:
        raise APIError("branch_not_found", "Branch not found", status_code=404)
    if principal.is_owner:
        return branch
    if branch.status is BranchStatus.INACTIVE:
        raise APIError("branch_not_found", "Branch not found", status_code=404)
    allowed = {grant.branch_id for grant in principal.grants}
    if branch.id not in allowed:
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    return branch


async def update_branch(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    payload: BranchPatchRequest,
) -> Branch:
    branch = await _owner_branch(db, principal=principal, branch_id=branch_id)
    latitude = payload.latitude if payload.latitude is not None else branch.latitude
    longitude = payload.longitude if payload.longitude is not None else branch.longitude
    _validate_coordinates(latitude, longitude)
    if "name" in payload.model_fields_set and payload.name is not None:
        branch.name = _required_text(payload.name, "branch_name_required")
    if "address" in payload.model_fields_set and payload.address is not None:
        branch.address = _required_text(payload.address, "branch_address_required")
    if "phone" in payload.model_fields_set and payload.phone is not None:
        branch.phone = normalize_uz_phone(payload.phone)
    if "latitude" in payload.model_fields_set:
        branch.latitude = latitude
    if "longitude" in payload.model_fields_set:
        branch.longitude = longitude
    if "working_hours" in payload.model_fields_set and payload.working_hours is not None:
        branch.working_hours = dump_working_hours(payload.working_hours)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="workshop.branch.update",
        entity_type="branch",
        entity_id=branch.id,
        workshop_id=branch.workshop_id,
        branch_id=branch.id,
        summary=f"Updated branch {branch.name}",
    )
    await db.refresh(branch)
    return branch


async def set_branch_status(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    payload: BranchStatusRequest,
) -> Branch:
    branch = await _owner_branch(db, principal=principal, branch_id=branch_id)
    reason = _optional_text(payload.reason)
    if payload.status is not BranchStatus.ACTIVE and reason is None:
        raise APIError("reason_required", "Reason is required", status_code=400)
    if branch.status is payload.status:
        branch.closed_reason = None if payload.status is BranchStatus.ACTIVE else reason
        return branch
    from_status = branch.status.value
    branch.status = payload.status
    branch.closed_reason = None if payload.status is BranchStatus.ACTIVE else reason
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action=f"workshop.branch.{payload.status.value}",
        entity_type="branch",
        entity_id=branch.id,
        workshop_id=branch.workshop_id,
        branch_id=branch.id,
        summary=f"Set branch {branch.name} to {payload.status.value}",
        details={"reason": reason},
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="branch",
        entity_id=branch.id,
        workshop_id=branch.workshop_id,
        branch_id=branch.id,
        from_status=from_status,
        to_status=payload.status.value,
        reason=reason,
        action_log_id=action.id,
    )
    await db.refresh(branch)
    return branch


async def get_branch_pricing(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
) -> BranchPricing:
    branch = await _owner_branch(db, principal=principal, branch_id=branch_id)
    row = await db.get(BranchPricing, branch.id)
    if row is None:
        row = BranchPricing(branch_id=branch.id)
        db.add(row)
        await db.flush()
    return row


async def update_branch_pricing(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    payload: BranchPricingPutRequest,
) -> BranchPricing:
    row = await get_branch_pricing(db, principal=principal, branch_id=branch_id)
    _validate_optional_nonnegative(payload.cutting_rate_tiyin, "invalid_cutting_rate")
    _validate_optional_nonnegative(payload.edge_banding_rate_tiyin, "invalid_edge_banding_rate")
    row.cutting_rate_tiyin = payload.cutting_rate_tiyin
    row.edge_banding_rate_tiyin = payload.edge_banding_rate_tiyin
    row.updated_at = datetime.now(UTC)
    row.updated_by_user_id = principal.principal_id
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="workshop.branch_pricing.update",
        entity_type="branch_pricing",
        entity_id=row.branch_id,
        workshop_id=principal.workshop_id,
        branch_id=row.branch_id,
        summary="Updated branch pricing",
    )
    return row


async def _owner_branch(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
) -> Branch:
    workshop_id = require_workshop_owner(principal)
    branch = await db.get(Branch, branch_id)
    if branch is None or branch.workshop_id != workshop_id:
        raise APIError("branch_not_found", "Branch not found", status_code=404)
    return branch


def _validate_coordinates(latitude: Decimal, longitude: Decimal) -> None:
    if latitude < Decimal("-90") or latitude > Decimal("90"):
        raise APIError("invalid_latitude", "Latitude is invalid", status_code=400)
    if longitude < Decimal("-180") or longitude > Decimal("180"):
        raise APIError("invalid_longitude", "Longitude is invalid", status_code=400)


def _validate_optional_nonnegative(value: int | None, code: str) -> None:
    if value is not None and value < 0:
        raise APIError(code, "Value must be non-negative", status_code=400)


def _required_text(value: str, code: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise APIError(code, "Required field is missing", status_code=status.HTTP_400_BAD_REQUEST)
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized or None
