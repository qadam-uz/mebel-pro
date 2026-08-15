"""Workshop profile, branch, and pricing setup use cases."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import BranchStatus
from app.modules.access.api import normalize_uz_phone
from app.modules.catalog.contracts import BranchMaterial, BranchPricing
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
    WorkshopOnboardingResponse,
    WorkshopSettingsPatchRequest,
)
from app.modules.workshop.users import require_workshop_owner, require_workshop_principal

_BRANCH_NO_LOCK_KEY = "branches:branch_no"

# A branch publishes one primary number plus at most this many extras (4 total).
MAX_ADDITIONAL_BRANCH_PHONES = 3


async def next_branch_no(db: AsyncSession) -> int:
    """Allocate the next platform-wide branch number.

    `max(branch_no) + 1` under an advisory lock held for the rest of the
    transaction — never a row count, because a count would reuse a number the
    moment the sequence is read concurrently, and `branch_no` is baked into
    every order number the branch ever prints (workshop.md).
    """
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(_BRANCH_NO_LOCK_KEY))))
    highest = await db.scalar(select(func.max(Branch.branch_no)))
    return int(highest or 0) + 1


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


async def create_branch(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: BranchCreateRequest,
) -> Branch:
    workshop_id = require_workshop_owner(principal)
    _validate_coordinates(payload.latitude, payload.longitude)
    phone = normalize_uz_phone(payload.phone)
    branch = Branch(
        workshop_id=workshop_id,
        branch_no=await next_branch_no(db),
        name=_required_text(payload.name, "branch_name_required"),
        address=_required_text(payload.address, "branch_address_required"),
        phone=phone,
        additional_phones=_normalized_additional_phones(payload.additional_phones, primary=phone),
        latitude=payload.latitude,
        longitude=payload.longitude,
        status=BranchStatus.ACTIVE,
        kerf_mm=payload.kerf_mm,
        edge_trim_mm=payload.edge_trim_mm,
        edge_overhang_mm=payload.edge_overhang_mm,
        own_material_allowed=payload.own_material_allowed,
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
    latitude = branch.latitude
    longitude = branch.longitude
    if "latitude" in payload.model_fields_set:
        latitude = payload.latitude
    if "longitude" in payload.model_fields_set:
        longitude = payload.longitude
    _validate_coordinates(latitude, longitude)
    if "name" in payload.model_fields_set and payload.name is not None:
        branch.name = _required_text(payload.name, "branch_name_required")
    if "address" in payload.model_fields_set and payload.address is not None:
        branch.address = _required_text(payload.address, "branch_address_required")
    # Primary and extras are validated as one set: changing either can collide
    # with the other, so the effective final list is what gets checked.
    phone = branch.phone
    if "phone" in payload.model_fields_set and payload.phone is not None:
        phone = normalize_uz_phone(payload.phone)
    additional = branch.additional_phones
    if "additional_phones" in payload.model_fields_set and payload.additional_phones is not None:
        additional = payload.additional_phones
    branch.additional_phones = _normalized_additional_phones(additional, primary=phone)
    branch.phone = phone
    if "latitude" in payload.model_fields_set:
        branch.latitude = latitude
    if "longitude" in payload.model_fields_set:
        branch.longitude = longitude
    if "kerf_mm" in payload.model_fields_set and payload.kerf_mm is not None:
        branch.kerf_mm = payload.kerf_mm
    if "edge_trim_mm" in payload.model_fields_set and payload.edge_trim_mm is not None:
        branch.edge_trim_mm = payload.edge_trim_mm
    if "edge_overhang_mm" in payload.model_fields_set and payload.edge_overhang_mm is not None:
        branch.edge_overhang_mm = payload.edge_overhang_mm
    if (
        "own_material_allowed" in payload.model_fields_set
        and payload.own_material_allowed is not None
    ):
        branch.own_material_allowed = payload.own_material_allowed
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


async def get_onboarding_status(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
) -> WorkshopOnboardingResponse:
    workshop_id = require_workshop_owner(principal)
    first_branch_id = await db.scalar(
        select(Branch.id)
        .where(Branch.workshop_id == workshop_id, Branch.status == BranchStatus.ACTIVE)
        .order_by(Branch.created_at, Branch.id)
        .limit(1)
    )
    branch_configured = (
        await db.scalar(
            select(Branch.id)
            .join(BranchPricing, BranchPricing.branch_id == Branch.id)
            .where(
                Branch.workshop_id == workshop_id,
                Branch.status == BranchStatus.ACTIVE,
                BranchPricing.cutting_rate_tiyin.is_not(None),
                BranchPricing.edge_banding_rate_tiyin.is_not(None),
            )
            .limit(1)
        )
        is not None
    )
    # A format with no price is invisible to clients (client-facing catalog
    # listings exclude `price_tiyin == 0`), so attaching an unpriced format
    # cannot be what completes onboarding — the checklist would say "done"
    # while the branch's public catalog stayed empty. The probe and the client
    # listing filter deliberately agree.
    materials_added = (
        await db.scalar(
            select(BranchMaterial.id)
            .join(Branch, Branch.id == BranchMaterial.branch_id)
            .where(
                Branch.workshop_id == workshop_id,
                BranchMaterial.price_tiyin > 0,
                # A walk-in's board is not the shop stocking its catalog, and it
                # can carry a price (the substitute's) — so exclude it
                # structurally rather than relying on the price gate.
                BranchMaterial.customer_supplied.is_(False),
            )
            .limit(1)
        )
        is not None
    )
    return WorkshopOnboardingResponse(
        branch_configured=branch_configured,
        materials_added=materials_added,
        setup_complete=branch_configured and materials_added,
        first_branch_id=first_branch_id,
    )


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


def _normalized_additional_phones(values: list[str], *, primary: str) -> list[str]:
    """Validate the extra published numbers against the primary and each other.

    Array order is display order, so it is preserved as given. Every entry goes
    through the same ``+998XXXXXXXXX`` rule as the primary number.
    """
    if len(values) > MAX_ADDITIONAL_BRANCH_PHONES:
        raise APIError(
            "too_many_branch_phones",
            f"A branch can have at most {MAX_ADDITIONAL_BRANCH_PHONES} additional phone numbers",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    normalized: list[str] = []
    for value in values:
        phone = normalize_uz_phone(value)
        if phone == primary or phone in normalized:
            raise APIError(
                "duplicate_branch_phone",
                f"Phone number {phone} is already listed for this branch",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        normalized.append(phone)
    return normalized


def _validate_coordinates(latitude: Decimal | None, longitude: Decimal | None) -> None:
    if latitude is None and longitude is None:
        return
    if latitude is None or longitude is None:
        raise APIError(
            "invalid_coordinates",
            "Latitude and longitude must be set together",
            status_code=400,
        )
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
