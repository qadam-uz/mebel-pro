"""Catalog — platform materials master, branch material selection, branch pricing.

Materials are platform-wide master records, created/edited only by a platform
operator. A branch *selects* from the active subset, sets its own price and
min-stock, and gets a StockItem (at 0) alongside the selection. Branch pricing
is owner-only (not delegable). Spec: docs/ref/features/catalog-inventory.md and
docs/ref/entities/catalog.md.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import bad_request, conflict, forbidden, not_found
from app.core.principal import Principal
from app.models.catalog import BranchMaterial, BranchPricing, Material
from app.models.enums import (
    CatalogStatus,
    CuttingModel,
    MaterialKind,
    MaterialType,
    Permission,
)
from app.models.inventory import StockItem
from app.services import audit, workshops

# --- platform materials master (platform operator) -------------------------


def _validate_material_fields(
    kind: MaterialKind,
    *,
    type_: MaterialType | None,
    sheet_length_mm: int | None,
    sheet_width_mm: int | None,
    grain_direction: bool | None,
) -> None:
    """Sheet rules: requires type, sheet size with length ≥ width, grain.
    Edge rules: none of those fields are allowed."""
    if kind is MaterialKind.SHEET:
        if type_ is None:
            raise bad_request("A sheet material requires a type.", code="invalid_material")
        if sheet_length_mm is None or sheet_width_mm is None:
            raise bad_request(
                "A sheet material requires sheet length and width.", code="invalid_material"
            )
        if sheet_length_mm < sheet_width_mm:
            raise bad_request(
                "Sheet length must be ≥ width (long side is the grain direction).",
                code="invalid_material",
            )
        if grain_direction is None:
            raise bad_request(
                "A sheet material requires a grain direction.", code="invalid_material"
            )
    else:  # edge
        if (
            type_ is not None
            or sheet_length_mm is not None
            or sheet_width_mm is not None
            or grain_direction is not None
        ):
            raise bad_request(
                "An edge material has no type, sheet size, or grain.", code="invalid_material"
            )


async def create_material(
    db: AsyncSession,
    actor: Principal,
    *,
    kind: MaterialKind,
    type_: MaterialType | None,
    name: str,
    thickness_mm: float,
    color: str,
    decor_code: str | None,
    sheet_length_mm: int | None,
    sheet_width_mm: int | None,
    grain_direction: bool | None,
    image_file_id: uuid.UUID | None,
) -> Material:
    _validate_material_fields(
        kind,
        type_=type_,
        sheet_length_mm=sheet_length_mm,
        sheet_width_mm=sheet_width_mm,
        grain_direction=grain_direction,
    )
    material = Material(
        kind=kind,
        type=type_,
        name=name.strip(),
        thickness_mm=thickness_mm,
        color=color.strip(),
        decor_code=decor_code.strip() if decor_code else None,
        sheet_length_mm=sheet_length_mm,
        sheet_width_mm=sheet_width_mm,
        grain_direction=grain_direction,
        image_file_id=image_file_id,
        status=CatalogStatus.ACTIVE,
    )
    db.add(material)
    await db.flush()
    await audit.record_action(
        db,
        actor=actor,
        action="material.created",
        entity_type="material",
        entity_id=material.id,
        summary=f"Created material {material.name}",
    )
    await db.refresh(material)
    return material


async def get_material(db: AsyncSession, material_id: uuid.UUID) -> Material:
    material = await db.get(Material, material_id)
    if material is None:
        raise not_found("Material not found.")
    return material


async def edit_material(
    db: AsyncSession,
    actor: Principal,
    material_id: uuid.UUID,
    *,
    type_: MaterialType | None = None,
    type_set: bool = False,
    name: str | None = None,
    thickness_mm: float | None = None,
    color: str | None = None,
    decor_code: str | None = None,
    decor_code_set: bool = False,
    sheet_length_mm: int | None = None,
    sheet_width_mm: int | None = None,
    grain_direction: bool | None = None,
    image_file_id: uuid.UUID | None = None,
    image_file_id_set: bool = False,
) -> Material:
    material = await get_material(db, material_id)
    if name is not None:
        material.name = name.strip()
    if thickness_mm is not None:
        material.thickness_mm = thickness_mm
    if color is not None:
        material.color = color.strip()
    if decor_code_set:
        material.decor_code = decor_code.strip() if decor_code else None
    if image_file_id_set:
        material.image_file_id = image_file_id
    if material.kind is MaterialKind.SHEET:
        if type_set and type_ is not None:
            material.type = type_
        if sheet_length_mm is not None:
            material.sheet_length_mm = sheet_length_mm
        if sheet_width_mm is not None:
            material.sheet_width_mm = sheet_width_mm
        if grain_direction is not None:
            material.grain_direction = grain_direction
        if (
            material.sheet_length_mm is not None
            and material.sheet_width_mm is not None
            and material.sheet_length_mm < material.sheet_width_mm
        ):
            raise bad_request("Sheet length must be ≥ width.", code="invalid_material")
    await audit.record_action(
        db,
        actor=actor,
        action="material.updated",
        entity_type="material",
        entity_id=material.id,
    )
    await db.refresh(material)
    return material


async def set_material_status(
    db: AsyncSession, actor: Principal, material_id: uuid.UUID, *, active: bool
) -> Material:
    material = await get_material(db, material_id)
    from_status = material.status
    material.status = CatalogStatus.ACTIVE if active else CatalogStatus.INACTIVE
    log = await audit.record_action(
        db,
        actor=actor,
        action="material.activated" if active else "material.deactivated",
        entity_type="material",
        entity_id=material.id,
    )
    await audit.record_status_change(
        db,
        entity_type="material",
        entity_id=material.id,
        from_status=from_status.value,
        to_status=material.status.value,
        actor=actor,
        action_log_id=log.id,
    )
    await db.refresh(material)
    return material


async def list_materials(
    db: AsyncSession, *, active_only: bool = False, kind: MaterialKind | None = None
) -> list[Material]:
    stmt = select(Material)
    if active_only:
        stmt = stmt.where(Material.status == CatalogStatus.ACTIVE)
    if kind is not None:
        stmt = stmt.where(Material.kind == kind)
    stmt = stmt.order_by(Material.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


# --- branch material selection (owner or manage_catalog on branch) ---------


def _require_catalog_access(principal: Principal, branch_id: uuid.UUID) -> None:
    if not principal.has_permission(Permission.MANAGE_CATALOG, branch_id):
        raise forbidden()


async def add_branch_material(
    db: AsyncSession,
    principal: Principal,
    branch_id: uuid.UUID,
    *,
    material_id: uuid.UUID,
    price_tiyin: int,
    min_stock: int,
) -> BranchMaterial:
    branch = await workshops.owned_branch(db, principal, branch_id)
    _require_catalog_access(principal, branch.id)
    material = await get_material(db, material_id)
    if material.status is not CatalogStatus.ACTIVE:
        raise bad_request("Cannot add an inactive platform material.", code="material_inactive")
    existing = (
        await db.execute(
            select(BranchMaterial).where(
                BranchMaterial.branch_id == branch.id,
                BranchMaterial.material_id == material_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise conflict("This material is already in the branch's selection.", code="duplicate")

    bm = BranchMaterial(
        branch_id=branch.id,
        material_id=material_id,
        price_tiyin=price_tiyin,
        min_stock=min_stock,
        status=CatalogStatus.ACTIVE,
    )
    db.add(bm)
    # The branch's stock item for this material is created alongside (at 0).
    stock = (
        await db.execute(
            select(StockItem).where(
                StockItem.branch_id == branch.id, StockItem.material_id == material_id
            )
        )
    ).scalar_one_or_none()
    if stock is None:
        db.add(
            StockItem(branch_id=branch.id, material_id=material_id, on_hand=0, min_stock=min_stock)
        )
    else:
        stock.min_stock = min_stock
    await db.flush()
    await audit.record_action(
        db,
        actor=principal,
        action="branch_material.added",
        entity_type="branch_material",
        entity_id=bm.id,
        workshop_id=branch.workshop_id,
        branch_id=branch.id,
    )
    await db.refresh(bm)
    return bm


async def _owned_branch_material(
    db: AsyncSession, principal: Principal, branch_id: uuid.UUID, branch_material_id: uuid.UUID
) -> tuple[BranchMaterial, Any]:
    branch = await workshops.owned_branch(db, principal, branch_id)
    _require_catalog_access(principal, branch.id)
    bm = await db.get(BranchMaterial, branch_material_id)
    if bm is None or bm.branch_id != branch.id:
        raise not_found("Branch material not found.")
    return bm, branch


async def edit_branch_material(
    db: AsyncSession,
    principal: Principal,
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    *,
    price_tiyin: int | None = None,
    min_stock: int | None = None,
) -> BranchMaterial:
    bm, branch = await _owned_branch_material(db, principal, branch_id, branch_material_id)
    if price_tiyin is not None:
        bm.price_tiyin = price_tiyin
    if min_stock is not None:
        bm.min_stock = min_stock
        stock = (
            await db.execute(
                select(StockItem).where(
                    StockItem.branch_id == branch.id,
                    StockItem.material_id == bm.material_id,
                )
            )
        ).scalar_one_or_none()
        if stock is not None:
            stock.min_stock = min_stock
    await audit.record_action(
        db,
        actor=principal,
        action="branch_material.updated",
        entity_type="branch_material",
        entity_id=bm.id,
        workshop_id=branch.workshop_id,
        branch_id=branch.id,
    )
    await db.refresh(bm)
    return bm


async def set_branch_material_status(
    db: AsyncSession,
    principal: Principal,
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    *,
    active: bool,
) -> BranchMaterial:
    bm, branch = await _owned_branch_material(db, principal, branch_id, branch_material_id)
    from_status = bm.status
    bm.status = CatalogStatus.ACTIVE if active else CatalogStatus.INACTIVE
    log = await audit.record_action(
        db,
        actor=principal,
        action="branch_material.activated" if active else "branch_material.deactivated",
        entity_type="branch_material",
        entity_id=bm.id,
        workshop_id=branch.workshop_id,
        branch_id=branch.id,
    )
    await audit.record_status_change(
        db,
        entity_type="branch_material",
        entity_id=bm.id,
        from_status=from_status.value,
        to_status=bm.status.value,
        actor=principal,
        workshop_id=branch.workshop_id,
        branch_id=branch.id,
        action_log_id=log.id,
    )
    await db.refresh(bm)
    return bm


async def list_branch_materials(
    db: AsyncSession, principal: Principal, branch_id: uuid.UUID
) -> list[BranchMaterial]:
    branch = await workshops.readable_branch(db, principal, branch_id)
    if not principal.has_permission(Permission.MANAGE_CATALOG, branch.id):
        raise forbidden()
    return list(
        (
            await db.execute(
                select(BranchMaterial)
                .where(BranchMaterial.branch_id == branch.id)
                .order_by(BranchMaterial.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


# --- branch pricing (owner only, not delegable) ----------------------------


async def get_branch_pricing(
    db: AsyncSession, principal: Principal, branch_id: uuid.UUID
) -> BranchPricing:
    branch = await workshops.readable_branch(db, principal, branch_id)
    pricing = await db.get(BranchPricing, branch.id)
    if pricing is None:
        # defensive: every branch should have one from create_branch
        pricing = BranchPricing(branch_id=branch.id, cutting_model=None, cutting_rate_tiyin=0)
        db.add(pricing)
        await db.flush()
        await db.refresh(pricing)
    return pricing


async def set_branch_pricing(
    db: AsyncSession,
    owner: Principal,
    branch_id: uuid.UUID,
    *,
    cutting_model: CuttingModel,
    cutting_rate_tiyin: int,
    edge_banding_rates: dict[str, int],
) -> BranchPricing:
    # Owner-only — enforced by the route's CurrentOwner dependency too.
    if not owner.is_owner:
        raise forbidden("Branch pricing is owner-only.")
    branch = await workshops.owned_branch(db, owner, branch_id)
    pricing = await db.get(BranchPricing, branch.id)
    if pricing is None:
        pricing = BranchPricing(branch_id=branch.id)
        db.add(pricing)
    pricing.cutting_model = cutting_model
    pricing.cutting_rate_tiyin = cutting_rate_tiyin
    pricing.edge_banding_rates = dict(edge_banding_rates)
    pricing.updated_by_user_id = owner.id
    await db.flush()
    await audit.record_action(
        db,
        actor=owner,
        action="branch_pricing.updated",
        entity_type="branch_pricing",
        entity_id=branch.id,
        workshop_id=branch.workshop_id,
        branch_id=branch.id,
    )
    await db.refresh(pricing)
    return pricing
