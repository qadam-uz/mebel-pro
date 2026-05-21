"""Workshop self-service settings (workshop app). Owner-only profile."""

from fastapi import APIRouter

from app.api.deps import CurrentOwner, Session
from app.schemas.workshop import WorkshopOut, WorkshopProfileUpdate
from app.services import workshops as workshop_service

router = APIRouter()


@router.get("/profile", response_model=WorkshopOut)
async def get_profile(owner: CurrentOwner, db: Session) -> WorkshopOut:
    ws = await workshop_service.get_owner_workshop(db, owner)
    return WorkshopOut.model_validate(ws)


@router.patch("/profile", response_model=WorkshopOut)
async def edit_profile(
    body: WorkshopProfileUpdate, owner: CurrentOwner, db: Session
) -> WorkshopOut:
    assert owner.workshop_id is not None
    ws = await workshop_service.edit_workshop_profile(
        db,
        owner,
        owner.workshop_id,
        name=body.name,
        phone=body.phone,
        address=body.address,
        address_set="address" in body.model_fields_set,
        logo_file_id=body.logo_file_id,
        logo_file_id_set=body.logo_file_id_set,
    )
    return WorkshopOut.model_validate(ws)
