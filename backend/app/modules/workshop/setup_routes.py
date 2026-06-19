"""Workshop setup routes."""

import uuid

from fastapi import APIRouter, status

from app.api.deps import AccountReadyPrincipal, Session
from app.modules.catalog.contracts import BranchPricing
from app.modules.workshop.api import (
    BranchOperationalCounts,
    branch_operational_counts,
    create_branch,
    get_branch,
    get_branch_pricing,
    get_settings,
    list_branches,
    set_branch_status,
    update_branch,
    update_branch_pricing,
    update_settings,
)
from app.modules.workshop.contracts import Branch
from app.modules.workshop.schemas import (
    BranchCreateRequest,
    BranchPatchRequest,
    BranchPricingPutRequest,
    BranchPricingResponse,
    BranchResponse,
    BranchStatusRequest,
    WorkshopSettingsPatchRequest,
    WorkshopSettingsResponse,
)

router = APIRouter(prefix="/workshop", tags=["workshop-setup"])


@router.get("/settings", response_model=WorkshopSettingsResponse)
async def settings_show(
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopSettingsResponse:
    row = await get_settings(db, principal=principal)
    return WorkshopSettingsResponse.model_validate(row)


@router.patch("/settings", response_model=WorkshopSettingsResponse)
async def settings_update(
    payload: WorkshopSettingsPatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopSettingsResponse:
    row = await update_settings(db, principal=principal, payload=payload)
    return WorkshopSettingsResponse.model_validate(row)


@router.get("/branches", response_model=list[BranchResponse])
async def branches_index(
    principal: AccountReadyPrincipal,
    db: Session,
) -> list[BranchResponse]:
    rows = await list_branches(db, principal=principal)
    counts = await branch_operational_counts(db, [row.id for row in rows])
    return [_branch_response(row, counts.get(row.id)) for row in rows]


@router.post("/branches", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
async def branches_create(
    payload: BranchCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchResponse:
    row = await create_branch(db, principal=principal, payload=payload)
    counts = await branch_operational_counts(db, [row.id])
    return _branch_response(row, counts.get(row.id))


@router.get("/branches/{branch_id}", response_model=BranchResponse)
async def branches_show(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchResponse:
    row = await get_branch(db, principal=principal, branch_id=branch_id)
    counts = await branch_operational_counts(db, [row.id])
    return _branch_response(row, counts.get(row.id))


@router.patch("/branches/{branch_id}", response_model=BranchResponse)
async def branches_update(
    branch_id: uuid.UUID,
    payload: BranchPatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchResponse:
    row = await update_branch(db, principal=principal, branch_id=branch_id, payload=payload)
    counts = await branch_operational_counts(db, [row.id])
    return _branch_response(row, counts.get(row.id))


@router.post("/branches/{branch_id}/status", response_model=BranchResponse)
async def branches_status(
    branch_id: uuid.UUID,
    payload: BranchStatusRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchResponse:
    row = await set_branch_status(db, principal=principal, branch_id=branch_id, payload=payload)
    counts = await branch_operational_counts(db, [row.id])
    return _branch_response(row, counts.get(row.id))


@router.get("/branches/{branch_id}/pricing", response_model=BranchPricingResponse)
async def branch_pricing_show(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchPricingResponse:
    row = await get_branch_pricing(db, principal=principal, branch_id=branch_id)
    return _branch_pricing_response(row)


@router.put("/branches/{branch_id}/pricing", response_model=BranchPricingResponse)
async def branch_pricing_update(
    branch_id: uuid.UUID,
    payload: BranchPricingPutRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchPricingResponse:
    row = await update_branch_pricing(db, principal=principal, branch_id=branch_id, payload=payload)
    return _branch_pricing_response(row)


def _branch_response(row: Branch, counts: BranchOperationalCounts | None = None) -> BranchResponse:
    return BranchResponse(
        id=row.id,
        workshop_id=row.workshop_id,
        name=row.name,
        address=row.address,
        phone=row.phone,
        latitude=row.latitude,
        longitude=row.longitude,
        working_hours=row.working_hours,
        status=row.status,
        closed_reason=row.closed_reason,
        active_orders_count=counts.active_orders if counts else 0,
        material_count=counts.materials if counts else 0,
        low_stock_count=counts.low_stock if counts else 0,
        staff_count=counts.staff if counts else 0,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _branch_pricing_response(row: BranchPricing) -> BranchPricingResponse:
    return BranchPricingResponse(
        branch_id=row.branch_id,
        cutting_rate_tiyin=row.cutting_rate_tiyin,
        edge_banding_rate_tiyin=row.edge_banding_rate_tiyin,
        updated_at=row.updated_at,
        updated_by_user_id=row.updated_by_user_id,
    )
