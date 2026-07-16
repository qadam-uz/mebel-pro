"""Client profile and visible branch use cases."""

import uuid

from fastapi import status
from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import (
    AuthenticatedPrincipalType,
    BranchStatus,
    MaterialStatus,
    WorkshopStatus,
)
from app.modules.access.contracts import Client
from app.modules.catalog.contracts import BranchMaterial, Manufacturer, Material
from app.modules.client_portal.schemas import (
    ClientBranchMaterialPreview,
    ClientBranchMaterialResponse,
    ClientBranchOption,
    ClientBranchResponse,
)
from app.modules.inventory.api import display_unit
from app.modules.support.api import record_action
from app.modules.workshop.contracts import Branch, Workshop


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
        .where(
            Workshop.status == WorkshopStatus.ACTIVE,
            Branch.status.in_([BranchStatus.ACTIVE, BranchStatus.TEMPORARILY_CLOSED]),
        )
        .order_by(Workshop.name, Branch.name)
    )
    normalized = search.strip() if search else ""
    if normalized:
        pattern = f"%{normalized.lower()}%"
        query = query.where(
            or_(
                Workshop.name.ilike(pattern),
                Branch.name.ilike(pattern),
                Branch.address.ilike(pattern),
            )
        )
    rows = (await db.execute(query)).all()
    return [
        ClientBranchOption(
            branch_id=branch.id,
            workshop_id=workshop.id,
            workshop_name=workshop.name,
            branch_name=branch.name,
            address=branch.address,
            status=branch.status,
            closed_reason=branch.closed_reason,
            today_hours=branch.today_hours(),
        )
        for branch, workshop in rows
    ]


async def _visible_branch(db: AsyncSession, branch_id: uuid.UUID) -> Branch:
    branch, _ = await _visible_branch_with_workshop(db, branch_id)
    return branch


async def visible_branch(db: AsyncSession, branch_id: uuid.UUID) -> Branch:
    """Return a branch visible to client-facing catalog flows."""

    return await _visible_branch(db, branch_id)


async def client_branches(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    search: str | None = None,
) -> list[ClientBranchResponse]:
    require_client(principal)
    query: Select[tuple[Branch, Workshop]] = (
        select(Branch, Workshop)
        .join(Workshop, Workshop.id == Branch.workshop_id)
        .where(
            Workshop.status == WorkshopStatus.ACTIVE,
            Branch.status.in_([BranchStatus.ACTIVE, BranchStatus.TEMPORARILY_CLOSED]),
        )
        .order_by(Workshop.name, Branch.name)
    )
    normalized = search.strip() if search else ""
    if normalized:
        pattern = f"%{normalized.lower()}%"
        query = query.where(or_(Workshop.name.ilike(pattern), Branch.name.ilike(pattern)))
    rows = (await db.execute(query)).all()
    previews, totals = await _branch_material_previews(db, [branch.id for branch, _ in rows])
    return [
        ClientBranchResponse(
            branch_id=branch.id,
            workshop_id=workshop.id,
            workshop_name=workshop.name,
            workshop_logo_file_id=workshop.logo_file_id,
            branch_name=branch.name,
            address=branch.address,
            phone=branch.phone,
            latitude=branch.latitude,
            longitude=branch.longitude,
            working_hours=branch.working_hours,
            status=branch.status,
            closed_reason=branch.closed_reason,
            materials_preview=previews.get(branch.id, []),
            materials_total=totals.get(branch.id, 0),
        )
        for branch, workshop in rows
    ]


_BRANCH_PREVIEW_LIMIT = 6


async def _branch_material_previews(
    db: AsyncSession,
    branch_ids: list[uuid.UUID],
) -> tuple[dict[uuid.UUID, list[ClientBranchMaterialPreview]], dict[uuid.UUID, int]]:
    """Top-N carried-material previews + total counts for many branches in ONE
    query, so the branches list avoids the per-branch N+1 (CB-13)."""
    previews: dict[uuid.UUID, list[ClientBranchMaterialPreview]] = {}
    totals: dict[uuid.UUID, int] = {}
    if not branch_ids:
        return previews, totals
    query = (
        select(BranchMaterial, Material, Manufacturer)
        .join(Material, Material.id == BranchMaterial.material_id)
        .join(Manufacturer, Manufacturer.id == Material.manufacturer_id)
        .where(
            BranchMaterial.branch_id.in_(branch_ids),
            BranchMaterial.status == MaterialStatus.ACTIVE,
            Material.status == MaterialStatus.ACTIVE,
            Manufacturer.status == MaterialStatus.ACTIVE,
        )
        .order_by(Manufacturer.name, Material.name)
    )
    for branch_material, material, manufacturer in (await db.execute(query)).all():
        branch_id = branch_material.branch_id
        totals[branch_id] = totals.get(branch_id, 0) + 1
        bucket = previews.setdefault(branch_id, [])
        if len(bucket) < _BRANCH_PREVIEW_LIMIT:
            bucket.append(
                ClientBranchMaterialPreview(
                    id=material.id,
                    manufacturer_name=manufacturer.name,
                    name=material.name,
                    price_tiyin=branch_material.price_tiyin,
                    display_unit=display_unit(material.kind),
                )
            )
    return previews, totals


async def client_branch_materials(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    search: str | None = None,
) -> list[ClientBranchMaterialResponse]:
    require_client(principal)
    await _visible_branch_with_workshop(db, branch_id)
    query = (
        select(BranchMaterial, Material, Manufacturer)
        .join(Material, Material.id == BranchMaterial.material_id)
        .join(Manufacturer, Manufacturer.id == Material.manufacturer_id)
        .where(
            BranchMaterial.branch_id == branch_id,
            BranchMaterial.status == MaterialStatus.ACTIVE,
            Material.status == MaterialStatus.ACTIVE,
            Manufacturer.status == MaterialStatus.ACTIVE,
        )
        .order_by(Manufacturer.name, Material.name)
    )
    normalized = search.strip() if search else ""
    if normalized:
        pattern = f"%{normalized.lower()}%"
        query = query.where(
            or_(
                Material.name.ilike(pattern),
                Material.color.ilike(pattern),
                Material.decor_code.ilike(pattern),
                Manufacturer.name.ilike(pattern),
            )
        )
    rows = (await db.execute(query)).all()
    return [
        ClientBranchMaterialResponse(
            id=material.id,
            kind=material.kind,
            manufacturer_name=manufacturer.name,
            type=material.type,
            name=material.name,
            thickness_mm=material.thickness_mm,
            color=material.color,
            decor_code=material.decor_code,
            panel_length_mm=material.panel_length_mm,
            panel_width_mm=material.panel_width_mm,
            grain_direction=material.grain_direction,
            image_file_id=material.image_file_id,
            price_tiyin=branch_material.price_tiyin,
            display_unit=display_unit(material.kind),
        )
        for branch_material, material, manufacturer in rows
    ]


async def _visible_branch_with_workshop(
    db: AsyncSession,
    branch_id: uuid.UUID,
) -> tuple[Branch, Workshop]:
    row = (
        await db.execute(
            select(Branch, Workshop)
            .join(Workshop, Workshop.id == Branch.workshop_id)
            .where(
                Branch.id == branch_id,
                Workshop.status == WorkshopStatus.ACTIVE,
                Branch.status.in_([BranchStatus.ACTIVE, BranchStatus.TEMPORARILY_CLOSED]),
            )
        )
    ).one_or_none()
    if row is None:
        raise APIError(
            "branch_not_found",
            "Branch not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    branch, workshop = row
    return branch, workshop
