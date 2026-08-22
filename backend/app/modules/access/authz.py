"""Tenant-scope helpers for workshop/branch access checks."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, PermissionGrantKey
from app.models.enums import AuthenticatedPrincipalType, BranchStatus, Permission
from app.modules.workshop.contracts import Branch


@dataclass(frozen=True)
class BranchScope:
    workshop_id: uuid.UUID
    branch_id: uuid.UUID


def visible_workshop_ids(principal: AuthenticatedPrincipal) -> frozenset[uuid.UUID] | None:
    """Return scoped workshop ids, or None for platform-wide visibility."""
    if principal.principal_type is AuthenticatedPrincipalType.PLATFORM_USER:
        return None
    if (
        principal.principal_type is AuthenticatedPrincipalType.WORKSHOP_USER
        and principal.workshop_id is not None
    ):
        return frozenset({principal.workshop_id})
    return frozenset()


def visible_branch_ids(principal: AuthenticatedPrincipal) -> frozenset[uuid.UUID] | None:
    """Return scoped branch ids, or None for platform-wide visibility."""
    if principal.principal_type is AuthenticatedPrincipalType.PLATFORM_USER:
        return None
    if principal.principal_type is AuthenticatedPrincipalType.WORKSHOP_USER:
        return frozenset(grant.branch_id for grant in principal.grants)
    return frozenset()


def can_access_branch(
    principal: AuthenticatedPrincipal,
    *,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID,
    permission: Permission,
) -> bool:
    if principal.principal_type is AuthenticatedPrincipalType.PLATFORM_USER:
        return True
    if principal.principal_type is not AuthenticatedPrincipalType.WORKSHOP_USER:
        return False
    if principal.workshop_id != workshop_id:
        return False
    if principal.is_owner:
        return True
    return PermissionGrantKey(permission=permission, branch_id=branch_id) in principal.grants


def require_manage_orders_workshop(principal: AuthenticatedPrincipal) -> uuid.UUID:
    """Require a workshop principal holding ``manage_orders`` on ≥1 branch;
    return their workshop id. Owner bypass applies (an owner holds every
    permission on every branch). Used to gate workshop-scoped surfaces (walk-in
    client resolve, staff cutting drafts) where no single branch is fixed yet.
    """
    if (
        principal.principal_type is not AuthenticatedPrincipalType.WORKSHOP_USER
        or principal.workshop_id is None
    ):
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    workshop_id = principal.workshop_id
    if principal.is_owner or any(
        can_access_branch(
            principal,
            workshop_id=workshop_id,
            branch_id=grant.branch_id,
            permission=Permission.MANAGE_ORDERS,
        )
        for grant in principal.grants
    ):
        return workshop_id
    raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)


async def resolve_branch_scope(
    db: AsyncSession,
    principal: AuthenticatedPrincipal,
    *,
    branch_id: uuid.UUID,
    permission: Permission,
    claimed_workshop_id: uuid.UUID | None = None,
) -> BranchScope:
    return await resolve_branch_scope_any(
        db,
        principal,
        branch_id=branch_id,
        permissions=(permission,),
        claimed_workshop_id=claimed_workshop_id,
    )


async def resolve_branch_scope_any(
    db: AsyncSession,
    principal: AuthenticatedPrincipal,
    *,
    branch_id: uuid.UUID,
    permissions: Sequence[Permission],
    claimed_workshop_id: uuid.UUID | None = None,
) -> BranchScope:
    """Resolve a branch scope that **any one** of ``permissions`` unlocks.

    A few reads are shared lookups rather than one grant's private data — the
    supplier list is both the warehouseman's arrival counterparty and the
    accountant's expense counterparty (QAD-169). Naming every permission that
    legitimately reads them keeps the alternative honest: a single-permission
    gate that the second reader has to work around.
    """
    branch = await db.get(Branch, branch_id)
    if branch is None or branch.status is BranchStatus.INACTIVE:
        raise APIError(
            "branch_not_found", "Branch not found", status_code=status.HTTP_404_NOT_FOUND
        )
    if claimed_workshop_id is not None and claimed_workshop_id != branch.workshop_id:
        raise APIError(
            "scope_mismatch",
            "Branch does not belong to the requested workshop",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if not any(
        can_access_branch(
            principal,
            workshop_id=branch.workshop_id,
            branch_id=branch.id,
            permission=permission,
        )
        for permission in permissions
    ):
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    return BranchScope(workshop_id=branch.workshop_id, branch_id=branch.id)
