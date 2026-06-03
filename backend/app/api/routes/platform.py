"""Platform-operator routes."""

import uuid

from fastapi import APIRouter, status

from app.api.deps import AccountReadyPrincipal, Session
from app.schemas.platform import (
    BlockWorkshopRequest,
    BranchSummary,
    PlatformWorkshopDetail,
    ProvisionWorkshopRequest,
    ProvisionWorkshopResponse,
    WorkshopSummary,
    WorkshopUserSummary,
)
from app.services.platform import (
    block_workshop,
    get_workshop_detail,
    list_workshops,
    provision_workshop,
    require_platform_operator,
    unblock_workshop,
)

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/workshops", response_model=list[WorkshopSummary])
async def workshops_index(
    principal: AccountReadyPrincipal,
    db: Session,
) -> list[WorkshopSummary]:
    require_platform_operator(principal)
    rows = await list_workshops(db)
    return [WorkshopSummary.model_validate(row) for row in rows]


@router.post(
    "/workshops",
    response_model=ProvisionWorkshopResponse,
    status_code=status.HTTP_201_CREATED,
)
async def workshops_create(
    payload: ProvisionWorkshopRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ProvisionWorkshopResponse:
    provisioned = await provision_workshop(db, principal=principal, payload=payload)
    return ProvisionWorkshopResponse(
        workshop=WorkshopSummary.model_validate(provisioned.workshop),
        branch=BranchSummary.model_validate(provisioned.branch),
        owner=WorkshopUserSummary.model_validate(provisioned.owner),
        temp_password=provisioned.temp_password,
    )


@router.get("/workshops/{workshop_id}", response_model=PlatformWorkshopDetail)
async def workshops_show(
    workshop_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> PlatformWorkshopDetail:
    require_platform_operator(principal)
    workshop, branches, owner = await get_workshop_detail(db, workshop_id=workshop_id)
    return PlatformWorkshopDetail(
        workshop=WorkshopSummary.model_validate(workshop),
        branches=[BranchSummary.model_validate(branch) for branch in branches],
        owner=WorkshopUserSummary.model_validate(owner),
    )


@router.post("/workshops/{workshop_id}/block", response_model=WorkshopSummary)
async def workshops_block(
    workshop_id: uuid.UUID,
    payload: BlockWorkshopRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopSummary:
    workshop = await block_workshop(
        db,
        principal=principal,
        workshop_id=workshop_id,
        reason=payload.reason,
    )
    return WorkshopSummary.model_validate(workshop)


@router.post("/workshops/{workshop_id}/unblock", response_model=WorkshopSummary)
async def workshops_unblock(
    workshop_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopSummary:
    workshop = await unblock_workshop(db, principal=principal, workshop_id=workshop_id)
    return WorkshopSummary.model_validate(workshop)
