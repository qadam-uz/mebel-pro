"""Workshop-staff management routes (workshop app). Owner-only."""

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentOwner, Session
from app.schemas.identity import (
    CreatedSecretResponse,
    GrantIn,
    GrantsSet,
    WorkshopUserCreate,
    WorkshopUserDetail,
    WorkshopUserOut,
    WorkshopUserUpdate,
)
from app.services import users as user_service

router = APIRouter()


@router.get("", response_model=list[WorkshopUserOut])
async def list_users(owner: CurrentOwner, db: Session) -> list[WorkshopUserOut]:
    assert owner.workshop_id is not None
    rows = await user_service.list_workshop_users(db, owner.workshop_id)
    return [WorkshopUserOut.model_validate(r) for r in rows]


@router.post("", response_model=CreatedSecretResponse, status_code=201)
async def create_user(
    body: WorkshopUserCreate, owner: CurrentOwner, db: Session
) -> CreatedSecretResponse:
    created = await user_service.create_workshop_user(
        db,
        owner,
        full_name=body.full_name,
        login=body.login,
        phone=body.phone,
        home_branch_id=body.home_branch_id,
        grants=[(g.permission, g.branch_id) for g in body.grants],
        password=body.password,
    )
    return CreatedSecretResponse(
        id=created.user.id, login=created.user.login, temp_password=created.temp_password
    )


@router.get("/{user_id}", response_model=WorkshopUserDetail)
async def get_user(user_id: uuid.UUID, owner: CurrentOwner, db: Session) -> WorkshopUserDetail:
    user = await user_service.owned_workshop_user(db, owner, user_id)
    grants = await user_service.get_user_grants(db, user_id)
    detail = WorkshopUserDetail.model_validate(user)
    detail.grants = [GrantIn(permission=g.permission, branch_id=g.branch_id) for g in grants]
    return detail


@router.patch("/{user_id}", response_model=WorkshopUserOut)
async def update_user(
    user_id: uuid.UUID, body: WorkshopUserUpdate, owner: CurrentOwner, db: Session
) -> WorkshopUserOut:
    user = await user_service.edit_workshop_user(
        db,
        owner,
        user_id,
        full_name=body.full_name,
        phone=body.phone,
        home_branch_id=body.home_branch_id,
        home_branch_set=body.home_branch_set,
    )
    return WorkshopUserOut.model_validate(user)


@router.put("/{user_id}/grants", response_model=WorkshopUserDetail)
async def set_grants(
    user_id: uuid.UUID, body: GrantsSet, owner: CurrentOwner, db: Session
) -> WorkshopUserDetail:
    user = await user_service.set_workshop_user_grants(
        db, owner, user_id, [(g.permission, g.branch_id) for g in body.grants]
    )
    grants = await user_service.get_user_grants(db, user_id)
    detail = WorkshopUserDetail.model_validate(user)
    detail.grants = [GrantIn(permission=g.permission, branch_id=g.branch_id) for g in grants]
    return detail


@router.post("/{user_id}/reset-password", response_model=CreatedSecretResponse)
async def reset_password(
    user_id: uuid.UUID, owner: CurrentOwner, db: Session
) -> CreatedSecretResponse:
    user = await user_service.owned_workshop_user(db, owner, user_id)
    temp = await user_service.reset_workshop_password(db, owner, user_id)
    return CreatedSecretResponse(id=user.id, login=user.login, temp_password=temp)


@router.post("/{user_id}/block", response_model=WorkshopUserOut)
async def block_user(user_id: uuid.UUID, owner: CurrentOwner, db: Session) -> WorkshopUserOut:
    user = await user_service.set_workshop_user_status(db, owner, user_id, blocked=True)
    return WorkshopUserOut.model_validate(user)


@router.post("/{user_id}/unblock", response_model=WorkshopUserOut)
async def unblock_user(user_id: uuid.UUID, owner: CurrentOwner, db: Session) -> WorkshopUserOut:
    user = await user_service.set_workshop_user_status(db, owner, user_id, blocked=False)
    return WorkshopUserOut.model_validate(user)
