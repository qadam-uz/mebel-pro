"""Workshop owner/staff use cases."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.core.security import PasswordPolicyError, hash_password, validate_password
from app.models.enums import (
    AuthenticatedPrincipalType,
    BranchStatus,
    Permission,
    UserStatus,
)
from app.modules.access.api import normalize_uz_phone, revoke_for_principal, revoke_session
from app.modules.access.contracts import PermissionGrant, Session, WorkshopUser
from app.modules.platform.api import generate_temp_password
from app.modules.support.api import record_action, record_status_change
from app.modules.workshop.contracts import Branch
from app.modules.workshop.schemas import (
    GrantInput,
    WorkshopUserCreateRequest,
    WorkshopUserPatchRequest,
)


@dataclass(frozen=True)
class CreatedWorkshopUser:
    user: WorkshopUser
    temp_password: str


@dataclass(frozen=True)
class BranchContext:
    branch: Branch
    permissions: frozenset[Permission]


def require_workshop_principal(principal: AuthenticatedPrincipal) -> uuid.UUID:
    if (
        principal.principal_type is not AuthenticatedPrincipalType.WORKSHOP_USER
        or principal.workshop_id is None
    ):
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    return principal.workshop_id


def require_workshop_owner(principal: AuthenticatedPrincipal) -> uuid.UUID:
    workshop_id = require_workshop_principal(principal)
    if not principal.is_owner:
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    return workshop_id


async def branch_context(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
) -> list[BranchContext]:
    workshop_id = require_workshop_principal(principal)
    query = (
        select(Branch)
        .where(
            Branch.workshop_id == workshop_id,
            Branch.status != BranchStatus.INACTIVE,
        )
        .order_by(Branch.name)
    )
    branches = list((await db.scalars(query)).all())
    if principal.is_owner:
        return [
            BranchContext(branch=branch, permissions=frozenset(Permission)) for branch in branches
        ]
    allowed_branch_ids = {grant.branch_id for grant in principal.grants}
    permissions_by_branch: dict[uuid.UUID, set[Permission]] = {}
    for grant in principal.grants:
        permissions_by_branch.setdefault(grant.branch_id, set()).add(grant.permission)
    return [
        BranchContext(
            branch=branch,
            permissions=frozenset(permissions_by_branch.get(branch.id, set())),
        )
        for branch in branches
        if branch.id in allowed_branch_ids
    ]


async def list_users(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    search: str | None = None,
    branch_id: uuid.UUID | None = None,
    status: UserStatus | None = None,
) -> list[WorkshopUser]:
    workshop_id = require_workshop_owner(principal)
    query = select(WorkshopUser).where(WorkshopUser.workshop_id == workshop_id)
    if status is not None:
        query = query.where(WorkshopUser.status == status)
    normalized_search = " ".join(search.strip().split()).lower() if search else ""
    if normalized_search:
        pattern = f"%{normalized_search}%"
        query = query.where(
            or_(
                func.lower(WorkshopUser.full_name).like(pattern),
                func.lower(WorkshopUser.login).like(pattern),
            )
        )
    if branch_id is not None:
        validated_branch_id = await _validate_home_branch(db, workshop_id, branch_id)
        grant_exists = exists().where(
            PermissionGrant.workshop_user_id == WorkshopUser.id,
            PermissionGrant.branch_id == validated_branch_id,
        )
        query = query.where(
            or_(
                WorkshopUser.home_branch_id == validated_branch_id,
                grant_exists,
            )
        )
    return list(
        (
            await db.scalars(query.order_by(WorkshopUser.is_owner.desc(), WorkshopUser.full_name))
        ).all()
    )


async def get_user(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    user_id: uuid.UUID,
) -> WorkshopUser:
    workshop_id = require_workshop_owner(principal)
    user = await db.get(WorkshopUser, user_id)
    if user is None or user.workshop_id != workshop_id:
        raise APIError("user_not_found", "User not found", status_code=status.HTTP_404_NOT_FOUND)
    return user


async def create_user(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: WorkshopUserCreateRequest,
) -> CreatedWorkshopUser:
    workshop_id = require_workshop_owner(principal)
    login = _required_text(payload.login, "login_required")
    if await _login_exists(db, workshop_id=workshop_id, login=login):
        raise APIError("login_exists", "Login already exists", status_code=status.HTTP_409_CONFLICT)
    home_branch_id = await _validate_home_branch(db, workshop_id, payload.home_branch_id)
    temp_password = payload.temp_password or generate_temp_password()
    try:
        validate_password(temp_password)
    except PasswordPolicyError as exc:
        raise APIError(
            "weak_password",
            str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc
    user = WorkshopUser(
        workshop_id=workshop_id,
        login=login,
        password_hash=hash_password(temp_password),
        full_name=_required_text(payload.full_name, "full_name_required"),
        phone=normalize_uz_phone(payload.phone),
        is_owner=False,
        home_branch_id=home_branch_id,
        status=UserStatus.ACTIVE,
        password_reset_required=True,
    )
    db.add(user)
    await db.flush()
    await _replace_grants(db, actor_id=principal.principal_id, user=user, grants=payload.grants)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="workshop.user.create",
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=workshop_id,
        summary=f"Created workshop user {user.login}",
        details={"login": user.login, "grant_count": len(payload.grants)},
    )
    return CreatedWorkshopUser(user=user, temp_password=temp_password)


async def update_user(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    user_id: uuid.UUID,
    payload: WorkshopUserPatchRequest,
) -> WorkshopUser:
    user = await get_user(db, principal=principal, user_id=user_id)
    _reject_owner_target(user)
    if payload.full_name is not None:
        user.full_name = _required_text(payload.full_name, "full_name_required")
    if payload.phone is not None:
        user.phone = normalize_uz_phone(payload.phone)
    if payload.login is not None:
        login = _required_text(payload.login, "login_required")
        if login.lower() != user.login.lower() and await _login_exists(
            db,
            workshop_id=user.workshop_id,
            login=login,
        ):
            raise APIError(
                "login_exists",
                "Login already exists",
                status_code=status.HTTP_409_CONFLICT,
            )
        user.login = login
    if "home_branch_id" in payload.model_fields_set:
        user.home_branch_id = await _validate_home_branch(
            db,
            user.workshop_id,
            payload.home_branch_id,
        )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="workshop.user.update",
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=user.workshop_id,
        summary=f"Updated workshop user {user.login}",
    )
    return user


async def replace_user_grants(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    user_id: uuid.UUID,
    grants: list[GrantInput],
) -> WorkshopUser:
    user = await get_user(db, principal=principal, user_id=user_id)
    _reject_owner_target(user)
    await _replace_grants(db, actor_id=principal.principal_id, user=user, grants=grants)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="workshop.user.grants.replace",
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=user.workshop_id,
        summary=f"Replaced grants for workshop user {user.login}",
        details={"grant_count": len(grants)},
    )
    return user


async def reset_user_password(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    user_id: uuid.UUID,
) -> CreatedWorkshopUser:
    user = await get_user(db, principal=principal, user_id=user_id)
    _reject_owner_target(user)
    temp_password = generate_temp_password()
    user.password_hash = hash_password(temp_password)
    user.password_reset_required = True
    await revoke_for_principal(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=user.id,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="workshop.user.password.reset",
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=user.workshop_id,
        summary=f"Reset password for workshop user {user.login}",
    )
    return CreatedWorkshopUser(user=user, temp_password=temp_password)


async def block_user(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    user_id: uuid.UUID,
    reason: str,
) -> WorkshopUser:
    user = await get_user(db, principal=principal, user_id=user_id)
    _reject_owner_target(user)
    normalized_reason = _required_text(reason, "reason_required")
    if user.status is UserStatus.BLOCKED:
        raise APIError(
            "invalid_status",
            "User is already blocked",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    from_status = user.status.value
    user.status = UserStatus.BLOCKED
    await revoke_for_principal(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=user.id,
    )
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action="workshop.user.block",
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=user.workshop_id,
        summary=f"Blocked workshop user {user.login}",
        details={"reason": normalized_reason},
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=user.workshop_id,
        from_status=from_status,
        to_status=user.status.value,
        reason=normalized_reason,
        action_log_id=action.id,
    )
    return user


async def unblock_user(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    user_id: uuid.UUID,
) -> WorkshopUser:
    user = await get_user(db, principal=principal, user_id=user_id)
    _reject_owner_target(user)
    if user.status is UserStatus.ACTIVE:
        raise APIError(
            "invalid_status",
            "User is already active",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    from_status = user.status.value
    user.status = UserStatus.ACTIVE
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action="workshop.user.unblock",
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=user.workshop_id,
        summary=f"Unblocked workshop user {user.login}",
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=user.workshop_id,
        from_status=from_status,
        to_status=user.status.value,
        action_log_id=action.id,
    )
    return user


async def list_user_sessions(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    user_id: uuid.UUID,
) -> list[Session]:
    user = await get_user(db, principal=principal, user_id=user_id)
    _reject_owner_target(user)
    return list(
        (
            await db.scalars(
                select(Session)
                .where(
                    Session.principal_type == AuthenticatedPrincipalType.WORKSHOP_USER,
                    Session.principal_id == user.id,
                )
                .order_by(Session.created_at.desc())
            )
        ).all()
    )


async def revoke_user_sessions(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    user_id: uuid.UUID,
) -> None:
    user = await get_user(db, principal=principal, user_id=user_id)
    _reject_owner_target(user)
    await revoke_for_principal(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=user.id,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="workshop.user.sessions.revoke_all",
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=user.workshop_id,
        summary=f"Revoked sessions for workshop user {user.login}",
    )


async def revoke_user_session(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    user = await get_user(db, principal=principal, user_id=user_id)
    _reject_owner_target(user)
    session = await db.get(Session, session_id)
    if (
        session is None
        or session.principal_type is not AuthenticatedPrincipalType.WORKSHOP_USER
        or session.principal_id != user.id
    ):
        raise APIError(
            "session_not_found",
            "Session not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    await revoke_session(db, session.id)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="workshop.user.sessions.revoke_one",
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=user.workshop_id,
        summary=f"Revoked one session for workshop user {user.login}",
    )


async def grants_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[PermissionGrant]:
    return list(
        (
            await db.scalars(
                select(PermissionGrant)
                .where(PermissionGrant.workshop_user_id == user_id)
                .order_by(PermissionGrant.branch_id, PermissionGrant.permission)
            )
        ).all()
    )


async def _replace_grants(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    user: WorkshopUser,
    grants: list[GrantInput],
) -> None:
    _reject_owner_target(user)
    normalized = {(grant.permission, grant.branch_id) for grant in grants}
    await _validate_grant_branches(
        db,
        workshop_id=user.workshop_id,
        branch_ids={branch_id for _, branch_id in normalized},
    )
    await db.execute(delete(PermissionGrant).where(PermissionGrant.workshop_user_id == user.id))
    now = datetime.now(UTC)
    for permission, branch_id in sorted(normalized, key=lambda item: (item[1].hex, item[0].value)):
        db.add(
            PermissionGrant(
                workshop_user_id=user.id,
                permission=permission,
                branch_id=branch_id,
                granted_by_user_id=actor_id,
                granted_at=now,
            )
        )
    await db.flush()


async def _validate_home_branch(
    db: AsyncSession,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID | None,
) -> uuid.UUID | None:
    if branch_id is None:
        return None
    branch = await db.get(Branch, branch_id)
    if (
        branch is None
        or branch.workshop_id != workshop_id
        or branch.status is BranchStatus.INACTIVE
    ):
        raise APIError(
            "branch_not_found",
            "Branch not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return branch.id


async def _validate_grant_branches(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    branch_ids: set[uuid.UUID],
) -> None:
    if not branch_ids:
        return
    rows = (
        await db.scalars(
            select(Branch).where(
                Branch.id.in_(branch_ids),
                Branch.workshop_id == workshop_id,
                Branch.status != BranchStatus.INACTIVE,
            )
        )
    ).all()
    if {row.id for row in rows} != branch_ids:
        raise APIError(
            "branch_not_found",
            "Branch not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )


async def _login_exists(db: AsyncSession, *, workshop_id: uuid.UUID, login: str) -> bool:
    existing = await db.scalar(
        select(WorkshopUser.id).where(
            WorkshopUser.workshop_id == workshop_id,
            func.lower(WorkshopUser.login) == login.lower(),
        )
    )
    return existing is not None


def _reject_owner_target(user: WorkshopUser) -> None:
    if user.is_owner:
        raise APIError("owner_target_forbidden", "Owner cannot be modified here", status_code=403)


def _required_text(value: str, code: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise APIError(code, "Required field is missing", status_code=status.HTTP_400_BAD_REQUEST)
    return normalized
