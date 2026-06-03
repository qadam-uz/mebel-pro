"""Client app routes."""

from fastapi import APIRouter

from app.api.deps import AccountReadyPrincipal, Session
from app.schemas.client import (
    ClientBranchOption,
    ClientProfilePatchRequest,
    ClientProfileResponse,
)
from app.services.client import branch_options, get_client_profile, update_client_profile

router = APIRouter(prefix="/client", tags=["client"])


@router.get("/profile", response_model=ClientProfileResponse)
async def profile_show(
    principal: AccountReadyPrincipal,
    db: Session,
) -> ClientProfileResponse:
    client = await get_client_profile(db, principal=principal)
    return ClientProfileResponse.model_validate(client)


@router.patch("/profile", response_model=ClientProfileResponse)
async def profile_update(
    payload: ClientProfilePatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ClientProfileResponse:
    client = await update_client_profile(
        db,
        principal=principal,
        name=payload.name,
        preferred_branch_id=payload.preferred_branch_id,
        update_preferred_branch="preferred_branch_id" in payload.model_fields_set,
    )
    return ClientProfileResponse.model_validate(client)


@router.get("/branch-options", response_model=list[ClientBranchOption])
async def branch_options_index(
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
) -> list[ClientBranchOption]:
    return await branch_options(db, principal=principal, search=search)
