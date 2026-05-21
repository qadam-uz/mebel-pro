"""Workshop-side catalog routes — material picker, branch selection, pricing."""

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentClient, CurrentOwner, CurrentWorkshopUser, Session
from app.models.enums import MaterialKind
from app.schemas.catalog import (
    BranchMaterialCreate,
    BranchMaterialOut,
    BranchMaterialUpdate,
    BranchPricingOut,
    BranchPricingUpdate,
    MaterialOut,
)
from app.services import catalog as catalog_service

# --- material picker (any workshop user; active platform materials) --------

picker_router = APIRouter()


@picker_router.get("", response_model=list[MaterialOut])
async def list_active_materials(
    _: CurrentWorkshopUser, db: Session, kind: MaterialKind | None = None
) -> list[MaterialOut]:
    rows = await catalog_service.list_materials(db, active_only=True, kind=kind)
    return [MaterialOut.model_validate(m) for m in rows]


# --- client material picker (any client; active platform sheet materials) --

client_picker_router = APIRouter()


@client_picker_router.get("", response_model=list[MaterialOut])
async def client_list_active_materials(
    _: CurrentClient, db: Session, kind: MaterialKind | None = MaterialKind.SHEET
) -> list[MaterialOut]:
    rows = await catalog_service.list_materials(db, active_only=True, kind=kind)
    return [MaterialOut.model_validate(m) for m in rows]


# --- branch material selection (owner or manage_catalog) -------------------

materials_router = APIRouter()


@materials_router.get("", response_model=list[BranchMaterialOut])
async def list_branch_materials(
    branch_id: uuid.UUID, principal: CurrentWorkshopUser, db: Session
) -> list[BranchMaterialOut]:
    rows = await catalog_service.list_branch_materials(db, principal, branch_id)
    return [BranchMaterialOut.model_validate(r) for r in rows]


@materials_router.post("", response_model=BranchMaterialOut, status_code=201)
async def add_branch_material(
    branch_id: uuid.UUID,
    body: BranchMaterialCreate,
    principal: CurrentWorkshopUser,
    db: Session,
) -> BranchMaterialOut:
    bm = await catalog_service.add_branch_material(
        db,
        principal,
        branch_id,
        material_id=body.material_id,
        price_tiyin=body.price_tiyin,
        min_stock=body.min_stock,
    )
    return BranchMaterialOut.model_validate(bm)


@materials_router.patch("/{branch_material_id}", response_model=BranchMaterialOut)
async def edit_branch_material(
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    body: BranchMaterialUpdate,
    principal: CurrentWorkshopUser,
    db: Session,
) -> BranchMaterialOut:
    bm = await catalog_service.edit_branch_material(
        db,
        principal,
        branch_id,
        branch_material_id,
        price_tiyin=body.price_tiyin,
        min_stock=body.min_stock,
    )
    return BranchMaterialOut.model_validate(bm)


@materials_router.post("/{branch_material_id}/activate", response_model=BranchMaterialOut)
async def activate_branch_material(
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    principal: CurrentWorkshopUser,
    db: Session,
) -> BranchMaterialOut:
    bm = await catalog_service.set_branch_material_status(
        db, principal, branch_id, branch_material_id, active=True
    )
    return BranchMaterialOut.model_validate(bm)


@materials_router.post("/{branch_material_id}/deactivate", response_model=BranchMaterialOut)
async def deactivate_branch_material(
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    principal: CurrentWorkshopUser,
    db: Session,
) -> BranchMaterialOut:
    bm = await catalog_service.set_branch_material_status(
        db, principal, branch_id, branch_material_id, active=False
    )
    return BranchMaterialOut.model_validate(bm)


# --- branch pricing (owner only) -------------------------------------------

pricing_router = APIRouter()


@pricing_router.get("", response_model=BranchPricingOut)
async def get_pricing(
    branch_id: uuid.UUID, principal: CurrentWorkshopUser, db: Session
) -> BranchPricingOut:
    pricing = await catalog_service.get_branch_pricing(db, principal, branch_id)
    return BranchPricingOut.model_validate(pricing)


@pricing_router.put("", response_model=BranchPricingOut)
async def set_pricing(
    branch_id: uuid.UUID, body: BranchPricingUpdate, owner: CurrentOwner, db: Session
) -> BranchPricingOut:
    pricing = await catalog_service.set_branch_pricing(
        db,
        owner,
        branch_id,
        cutting_model=body.cutting_model,
        cutting_rate_tiyin=body.cutting_rate_tiyin,
        edge_banding_rates=body.edge_banding_rates,
    )
    return BranchPricingOut.model_validate(pricing)
