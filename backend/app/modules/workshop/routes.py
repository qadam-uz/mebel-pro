"""Workshop owner/staff routes."""

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, status

from app.api.deps import AccountReadyPrincipal, Session
from app.models.enums import UserStatus
from app.modules.access.contracts import PermissionGrant
from app.modules.access.schemas import PermissionGrantResponse, SessionResponse
from app.modules.workshop.api import (
    block_user,
    branch_context,
    create_user,
    get_user,
    grants_for_user,
    grants_for_users,
    list_user_sessions,
    list_users,
    replace_user_grants,
    reset_user_password,
    revoke_user_session,
    revoke_user_sessions,
    unblock_user,
    update_user,
)
from app.modules.workshop.schemas import (
    BlockWorkshopUserRequest,
    BranchContextItem,
    BranchContextResponse,
    GrantReplacementRequest,
    TempPasswordResponse,
    WorkshopUserCreateRequest,
    WorkshopUserCreateResponse,
    WorkshopUserPatchRequest,
    WorkshopUserResponse,
    WorkshopUserSessionsResponse,
)

router = APIRouter(prefix="/workshop", tags=["workshop"])


@router.get("/branch-context", response_model=BranchContextResponse)
async def branch_context_route(
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchContextResponse:
    contexts = await branch_context(db, principal=principal)
    return BranchContextResponse(
        branches=[
            BranchContextItem(
                id=context.branch.id,
                name=context.branch.name,
                address=context.branch.address,
                phone=context.branch.phone,
                status=context.branch.status,
                closed_reason=context.branch.closed_reason,
                kerf_mm=context.branch.kerf_mm,
                edge_trim_mm=context.branch.edge_trim_mm,
                edge_overhang_mm=context.branch.edge_overhang_mm,
                own_material_allowed=context.branch.own_material_allowed,
                permissions=sorted(context.permissions),
            )
            for context in contexts
        ]
    )


@router.get("/users", response_model=list[WorkshopUserResponse])
async def users_index(
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    branch_id: uuid.UUID | None = None,
    status: UserStatus | None = None,
) -> list[WorkshopUserResponse]:
    rows = await list_users(
        db,
        principal=principal,
        search=search,
        branch_id=branch_id,
        status=status,
    )
    # One grants query for the whole page. This was `[await _user_response(db, row)
    # for row in rows]` — a serial round trip per staff member, and the global
    # search calls this endpoint on every keystroke.
    grants = await grants_for_users(db, [row.id for row in rows])
    return [_user_response_with_grants(row, grants[row.id]) for row in rows]


@router.post(
    "/users",
    response_model=WorkshopUserCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def users_create(
    payload: WorkshopUserCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopUserCreateResponse:
    created = await create_user(db, principal=principal, payload=payload)
    return WorkshopUserCreateResponse(
        user=await _user_response(db, created.user),
        temp_password=created.temp_password,
    )


@router.get("/users/{user_id}", response_model=WorkshopUserResponse)
async def users_show(
    user_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopUserResponse:
    user = await get_user(db, principal=principal, user_id=user_id)
    return await _user_response(db, user)


@router.patch("/users/{user_id}", response_model=WorkshopUserResponse)
async def users_update(
    user_id: uuid.UUID,
    payload: WorkshopUserPatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopUserResponse:
    user = await update_user(db, principal=principal, user_id=user_id, payload=payload)
    return await _user_response(db, user)


@router.put("/users/{user_id}/grants", response_model=WorkshopUserResponse)
async def users_replace_grants(
    user_id: uuid.UUID,
    payload: GrantReplacementRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopUserResponse:
    user = await replace_user_grants(
        db,
        principal=principal,
        user_id=user_id,
        grants=payload.grants,
    )
    return await _user_response(db, user)


@router.post("/users/{user_id}/reset-password", response_model=TempPasswordResponse)
async def users_reset_password(
    user_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> TempPasswordResponse:
    reset = await reset_user_password(db, principal=principal, user_id=user_id)
    return TempPasswordResponse(
        user=await _user_response(db, reset.user),
        temp_password=reset.temp_password,
    )


@router.post("/users/{user_id}/block", response_model=WorkshopUserResponse)
async def users_block(
    user_id: uuid.UUID,
    payload: BlockWorkshopUserRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopUserResponse:
    user = await block_user(db, principal=principal, user_id=user_id, reason=payload.reason)
    return await _user_response(db, user)


@router.post("/users/{user_id}/unblock", response_model=WorkshopUserResponse)
async def users_unblock(
    user_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopUserResponse:
    user = await unblock_user(db, principal=principal, user_id=user_id)
    return await _user_response(db, user)


@router.get("/users/{user_id}/sessions", response_model=WorkshopUserSessionsResponse)
async def users_sessions(
    user_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopUserSessionsResponse:
    sessions = await list_user_sessions(db, principal=principal, user_id=user_id)
    return WorkshopUserSessionsResponse(
        sessions=[
            SessionResponse(
                id=row.id,
                created_at=row.created_at,
                last_used_at=row.last_used_at,
                access_token_expires_at=row.access_token_expires_at,
                refresh_token_expires_at=row.refresh_token_expires_at,
                device_info=row.device_info,
                is_current=False,
            )
            for row in sessions
        ]
    )


@router.delete("/users/{user_id}/sessions", status_code=status.HTTP_204_NO_CONTENT)
async def users_revoke_sessions(
    user_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> None:
    await revoke_user_sessions(db, principal=principal, user_id=user_id)


@router.delete("/users/{user_id}/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def users_revoke_session(
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> None:
    await revoke_user_session(
        db,
        principal=principal,
        user_id=user_id,
        session_id=session_id,
    )


async def _user_response(db: Session, user: object) -> WorkshopUserResponse:
    from app.modules.access.contracts import WorkshopUser

    if not isinstance(user, WorkshopUser):
        raise TypeError("expected WorkshopUser")
    return _user_response_with_grants(user, await grants_for_user(db, user.id))


def _user_response_with_grants(
    user: object, grants: Sequence[PermissionGrant]
) -> WorkshopUserResponse:
    """Shape one user, given grants already in hand.

    Split out so the list endpoint can fetch every row's grants in one query
    instead of one per row.
    """
    from app.modules.access.contracts import WorkshopUser

    if not isinstance(user, WorkshopUser):
        raise TypeError("expected WorkshopUser")
    return WorkshopUserResponse(
        id=user.id,
        workshop_id=user.workshop_id,
        login=user.login,
        full_name=user.full_name,
        phone=user.phone,
        is_owner=user.is_owner,
        home_branch_id=user.home_branch_id,
        status=user.status,
        password_reset_required=user.password_reset_required,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        grants=[
            PermissionGrantResponse(permission=grant.permission, branch_id=grant.branch_id)
            for grant in grants
        ],
    )
