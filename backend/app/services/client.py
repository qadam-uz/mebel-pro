"""Client profile and visible branch use cases."""

import uuid

from fastapi import status
from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import AuthenticatedPrincipalType, BranchStatus
from app.models.identity import Client
from app.models.workshop import Branch, Workshop
from app.schemas.client import ClientBranchOption
from app.services.audit import record_action


def require_client(principal: AuthenticatedPrincipal) -> None:
    if principal.principal_type is not AuthenticatedPrincipalType.CLIENT:
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)


async def get_client_profile(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
) -> Client:
    require_client(principal)
    client = await db.get(Client, principal.principal_id)
    if client is None:
        raise APIError(
            "invalid_access_token",
            "Authentication required",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return client


async def update_client_profile(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    name: str | None,
    preferred_branch_id: uuid.UUID | None,
    update_preferred_branch: bool,
) -> Client:
    client = await get_client_profile(db, principal=principal)
    if name is not None:
        normalized_name = " ".join(name.strip().split())
        if not normalized_name or len(normalized_name) > 80:
            raise APIError("invalid_name", "Invalid name", status_code=status.HTTP_400_BAD_REQUEST)
        client.name = normalized_name
    if update_preferred_branch:
        if preferred_branch_id is not None:
            branch = await _visible_branch(db, preferred_branch_id)
            client.preferred_branch_id = branch.id
        else:
            client.preferred_branch_id = None
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="client.profile.update",
        entity_type="client",
        entity_id=client.id,
        summary="Updated client profile",
        details={
            "preferred_branch_id": str(client.preferred_branch_id)
            if client.preferred_branch_id
            else None,
        },
    )
    return client


async def branch_options(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    search: str | None = None,
) -> list[ClientBranchOption]:
    require_client(principal)
    query: Select[tuple[Branch, Workshop]] = (
        select(Branch, Workshop)
        .join(Workshop, Workshop.id == Branch.workshop_id)
        .where(Branch.status.in_([BranchStatus.ACTIVE, BranchStatus.TEMPORARILY_CLOSED]))
        .order_by(Workshop.name, Branch.name)
    )
    normalized = search.strip() if search else ""
    if normalized:
        pattern = f"%{normalized.lower()}%"
        query = query.where(or_(Workshop.name.ilike(pattern), Branch.name.ilike(pattern)))
    rows = (await db.execute(query)).all()
    return [
        ClientBranchOption(
            branch_id=branch.id,
            workshop_id=workshop.id,
            workshop_name=workshop.name,
            branch_name=branch.name,
            status=branch.status,
            closed_reason=branch.closed_reason,
        )
        for branch, workshop in rows
    ]


async def _visible_branch(db: AsyncSession, branch_id: uuid.UUID) -> Branch:
    branch = await db.get(Branch, branch_id)
    if branch is None or branch.status not in {
        BranchStatus.ACTIVE,
        BranchStatus.TEMPORARILY_CLOSED,
    }:
        raise APIError(
            "branch_not_found",
            "Branch not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return branch
