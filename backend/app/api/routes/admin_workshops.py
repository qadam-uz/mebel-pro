"""Workshop administration routes (superadmin app). Platform-operator scoped."""

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentPlatformUser, Session
from app.models.workshop import Workshop
from app.schemas.workshop import (
    WorkshopBlock,
    WorkshopOut,
    WorkshopProfileUpdate,
    WorkshopProvision,
    WorkshopProvisionResult,
    WorkshopSummary,
)
from app.services import workshops as workshop_service

router = APIRouter()


async def _summary(db: Session, ws: Workshop) -> WorkshopSummary:
    enrichment = await workshop_service.workshop_enrichment(db, ws)
    summary = WorkshopSummary.model_validate(ws)
    summary.owner_name = enrichment["owner_name"]
    summary.owner_phone = enrichment["owner_phone"]
    summary.branches_count = enrichment["branches_count"]
    summary.orders_30d_count = enrichment["orders_30d_count"]
    return summary


@router.get("", response_model=list[WorkshopSummary])
async def list_workshops(_: CurrentPlatformUser, db: Session) -> list[WorkshopSummary]:
    rows = await workshop_service.list_workshops(db)
    return [await _summary(db, ws) for ws in rows]


@router.post("", response_model=WorkshopProvisionResult, status_code=201)
async def provision_workshop(
    body: WorkshopProvision, actor: CurrentPlatformUser, db: Session
) -> WorkshopProvisionResult:
    result = await workshop_service.provision_workshop(
        db,
        actor,
        name=body.name,
        phone=body.phone,
        address=body.address,
        logo_file_id=body.logo_file_id,
        owner_full_name=body.owner_full_name,
        owner_login=body.owner_login,
        owner_phone=body.owner_phone,
        owner_password=body.owner_password,
    )
    return WorkshopProvisionResult(
        workshop=WorkshopOut.model_validate(result.workshop),
        owner_id=result.owner.id,
        owner_login=result.owner.login,
        temp_password=result.temp_password,
    )


@router.get("/{workshop_id}", response_model=WorkshopSummary)
async def get_workshop(
    workshop_id: uuid.UUID, _: CurrentPlatformUser, db: Session
) -> WorkshopSummary:
    ws = await workshop_service.get_workshop(db, workshop_id)
    return await _summary(db, ws)


@router.patch("/{workshop_id}/profile", response_model=WorkshopOut)
async def edit_profile(
    workshop_id: uuid.UUID,
    body: WorkshopProfileUpdate,
    actor: CurrentPlatformUser,
    db: Session,
) -> WorkshopOut:
    ws = await workshop_service.edit_workshop_profile(
        db,
        actor,
        workshop_id,
        name=body.name,
        phone=body.phone,
        address=body.address,
        address_set="address" in body.model_fields_set,
        logo_file_id=body.logo_file_id,
        logo_file_id_set=body.logo_file_id_set,
    )
    return WorkshopOut.model_validate(ws)


@router.post("/{workshop_id}/block", response_model=WorkshopOut)
async def block_workshop(
    workshop_id: uuid.UUID, body: WorkshopBlock, actor: CurrentPlatformUser, db: Session
) -> WorkshopOut:
    ws = await workshop_service.set_workshop_status(
        db, actor, workshop_id, blocked=True, reason=body.reason
    )
    return WorkshopOut.model_validate(ws)


@router.post("/{workshop_id}/unblock", response_model=WorkshopOut)
async def unblock_workshop(
    workshop_id: uuid.UUID, body: WorkshopBlock, actor: CurrentPlatformUser, db: Session
) -> WorkshopOut:
    ws = await workshop_service.set_workshop_status(
        db, actor, workshop_id, blocked=False, reason=body.reason
    )
    return WorkshopOut.model_validate(ws)
