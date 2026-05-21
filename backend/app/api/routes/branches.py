"""Branch CRUD + status (workshop app). Owner-only writes; scoped reads."""

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentOwner, CurrentWorkshopUser, Session
from app.models.workshop import Branch
from app.schemas.workshop import (
    BranchCreate,
    BranchOut,
    BranchStatusChange,
    BranchSummary,
    BranchUpdate,
)
from app.services import workshops as workshop_service

router = APIRouter()


async def _summary(db: Session, branch: Branch) -> BranchSummary:
    enrichment = await workshop_service.branch_enrichment(db, branch)
    summary = BranchSummary.model_validate(branch)
    summary.materials_count = enrichment["materials_count"]
    summary.low_stock_count = enrichment["low_stock_count"]
    summary.active_orders_count = enrichment["active_orders_count"]
    return summary


@router.get("", response_model=list[BranchSummary])
async def list_branches(principal: CurrentWorkshopUser, db: Session) -> list[BranchSummary]:
    rows = await workshop_service.list_branches(db, principal)
    return [await _summary(db, b) for b in rows]


@router.post("", response_model=BranchOut, status_code=201)
async def create_branch(body: BranchCreate, owner: CurrentOwner, db: Session) -> BranchOut:
    branch = await workshop_service.create_branch(
        db,
        owner,
        name=body.name,
        address=body.address,
        phone=body.phone,
        latitude=body.latitude,
        longitude=body.longitude,
        working_hours=body.working_hours,
    )
    return BranchOut.model_validate(branch)


@router.get("/{branch_id}", response_model=BranchSummary)
async def get_branch(
    branch_id: uuid.UUID, principal: CurrentWorkshopUser, db: Session
) -> BranchSummary:
    branch = await workshop_service.readable_branch(db, principal, branch_id)
    return await _summary(db, branch)


@router.patch("/{branch_id}", response_model=BranchOut)
async def edit_branch(
    branch_id: uuid.UUID, body: BranchUpdate, owner: CurrentOwner, db: Session
) -> BranchOut:
    branch = await workshop_service.edit_branch(
        db,
        owner,
        branch_id,
        name=body.name,
        address=body.address,
        phone=body.phone,
        latitude=body.latitude,
        longitude=body.longitude,
        latitude_set=body.latitude_set,
        longitude_set=body.longitude_set,
        working_hours=body.working_hours,
    )
    return BranchOut.model_validate(branch)


@router.post("/{branch_id}/status", response_model=BranchOut)
async def change_status(
    branch_id: uuid.UUID, body: BranchStatusChange, owner: CurrentOwner, db: Session
) -> BranchOut:
    branch = await workshop_service.change_branch_status(
        db, owner, branch_id, status=body.status, closed_reason=body.closed_reason
    )
    return BranchOut.model_validate(branch)
