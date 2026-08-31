"""Client app routes."""

import uuid

from fastapi import APIRouter

from app.api.deps import AccountReadyPrincipal, Session
from app.modules.client_portal.api import (
    apply_entry,
    branch_options,
    client_branch_materials,
    client_branches,
    get_client_profile,
    my_workshops,
    update_client_profile,
)
from app.modules.client_portal.schemas import (
    ClientBranchMaterialResponse,
    ClientBranchOption,
    ClientBranchResponse,
    ClientEntryRequest,
    ClientEntryResponse,
    ClientProfilePatchRequest,
    ClientProfileResponse,
    ClientWorkshopResponse,
)

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


@router.post("/entry", response_model=ClientEntryResponse)
async def entry_apply(
    payload: ClientEntryRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ClientEntryResponse:
    return await apply_entry(
        db,
        principal=principal,
        code=payload.code,
        branch_id=payload.branch_id,
    )


@router.get("/my-workshops", response_model=list[ClientWorkshopResponse])
async def my_workshops_index(
    principal: AccountReadyPrincipal,
    db: Session,
) -> list[ClientWorkshopResponse]:
    return await my_workshops(db, principal=principal)


@router.get("/branch-options", response_model=list[ClientBranchOption])
async def branch_options_index(
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
) -> list[ClientBranchOption]:
    return await branch_options(db, principal=principal, search=search)


@router.get("/branches", response_model=list[ClientBranchResponse])
async def branches_index(
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
) -> list[ClientBranchResponse]:
    return await client_branches(db, principal=principal, search=search)


@router.get("/branches/{branch_id}/materials", response_model=list[ClientBranchMaterialResponse])
async def branch_materials_index(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
) -> list[ClientBranchMaterialResponse]:
    return await client_branch_materials(
        db,
        principal=principal,
        branch_id=branch_id,
        search=search,
    )
