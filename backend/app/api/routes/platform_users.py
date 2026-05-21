"""Platform-user registry routes (superadmin app). Platform-scoped."""

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentPlatformUser, Session
from app.models.identity import PlatformUser
from app.schemas.identity import (
    CreatedSecretResponse,
    PlatformUserCreate,
    PlatformUserOut,
)
from app.services import users as user_service

router = APIRouter()


@router.get("", response_model=list[PlatformUserOut])
async def list_platform_users(_: CurrentPlatformUser, db: Session) -> list[PlatformUserOut]:
    rows = await user_service.list_platform_users(db)
    return [PlatformUserOut.model_validate(r) for r in rows]


@router.post("", response_model=CreatedSecretResponse, status_code=201)
async def create_platform_user(
    body: PlatformUserCreate, actor: CurrentPlatformUser, db: Session
) -> CreatedSecretResponse:
    created = await user_service.create_platform_user(
        db,
        actor,
        full_name=body.full_name,
        login=body.login,
        phone=body.phone,
        password=body.password,
    )
    return CreatedSecretResponse(
        id=created.user.id, login=created.user.login, temp_password=created.temp_password
    )


@router.post("/{user_id}/reset-password", response_model=CreatedSecretResponse)
async def reset_platform_password(
    user_id: uuid.UUID, actor: CurrentPlatformUser, db: Session
) -> CreatedSecretResponse:
    temp = await user_service.reset_platform_password(db, actor, user_id)
    user = await db.get(PlatformUser, user_id)
    assert user is not None
    return CreatedSecretResponse(id=user.id, login=user.login, temp_password=temp)


@router.post("/{user_id}/block", response_model=PlatformUserOut)
async def block_platform_user(
    user_id: uuid.UUID, actor: CurrentPlatformUser, db: Session
) -> PlatformUserOut:
    user = await user_service.set_platform_user_status(db, actor, user_id, blocked=True)
    return PlatformUserOut.model_validate(user)


@router.post("/{user_id}/unblock", response_model=PlatformUserOut)
async def unblock_platform_user(
    user_id: uuid.UUID, actor: CurrentPlatformUser, db: Session
) -> PlatformUserOut:
    user = await user_service.set_platform_user_status(db, actor, user_id, blocked=False)
    return PlatformUserOut.model_validate(user)
