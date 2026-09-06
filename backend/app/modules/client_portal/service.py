"""Client profile and visible branch use cases."""

import uuid
from typing import Any

from fastapi import status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.core.search_query import SearchPlan, run_search_tiers
from app.models.enums import (
    AuthenticatedPrincipalType,
    BranchStatus,
    MaterialStatus,
    WorkshopStatus,
)
from app.modules.access.contracts import Client

# One writer for the label and its snapshot vocabulary: catalog owns both, and
# a second copy here is how `18` and `18.0000000000` reach two endpoints.
from app.modules.catalog.api import (
    apply_decor_search,
    branch_material_label,
    format_dimension_arms,
    normalize_mm,
)
from app.modules.catalog.contracts import BranchMaterial, Decor, DecorFormat, Manufacturer
from app.modules.client_portal.schemas import (
    ClientBranchMaterialPreview,
    ClientBranchMaterialResponse,
    ClientBranchOption,
    ClientBranchResponse,
    ClientContact,
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


async def client_contact(db: AsyncSession, client_id: uuid.UUID) -> ClientContact | None:
    """Name+phone for an arbitrary client id, or `None` if it no longer
    resolves — the caller (e.g. the cutting PDF identity box) treats a torn-
    down client as an absent line, not an error."""
    client = await db.get(Client, client_id)
    if client is None:
        return None
    return ClientContact(id=client.id, name=client.name, phone=client.phone)


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
            kerf_mm=branch.kerf_mm,
            edge_trim_mm=branch.edge_trim_mm,
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
            additional_phones=branch.additional_phones,
            latitude=branch.latitude,
            longitude=branch.longitude,
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
    """Top-N carried-material previews + total counts for many branches.

    One decor now fans out to one row per format a branch carries, so both the
    preview and `materials_total` count *formats*, not decors — a branch with
    one decor in three thicknesses reports three.

    Two bounded queries rather than one unbounded read. This used to hydrate
    every matching row across every visible branch into three ORM entities and
    count them in Python, to keep six of them — tolerable while the price gate
    trimmed the set, wasteful the moment that gate came off (one real branch
    carries 518 formats, and this runs on every keystroke of the branch search).
    The count is now `COUNT(*)` grouped by branch, and the previews are cut to
    `_BRANCH_PREVIEW_LIMIT` per branch by a window function before any row
    leaves Postgres.
    """
    previews: dict[uuid.UUID, list[ClientBranchMaterialPreview]] = {}
    totals: dict[uuid.UUID, int] = {}
    if not branch_ids:
        return previews, totals

    def _visible() -> Select[tuple[BranchMaterial, DecorFormat, Decor, Manufacturer]]:
        return (
            select(BranchMaterial, DecorFormat, Decor, Manufacturer)
            .join(DecorFormat, DecorFormat.id == BranchMaterial.decor_format_id)
            .join(Decor, Decor.id == DecorFormat.decor_id)
            .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
            .where(
                BranchMaterial.branch_id.in_(branch_ids),
                BranchMaterial.status == MaterialStatus.ACTIVE,
                # No price gate — kept identical to `client_branch_materials` so
                # this preview's "+N more" count can never disagree with the
                # list it links to.
                Decor.status == MaterialStatus.ACTIVE,
                Manufacturer.status == MaterialStatus.ACTIVE,
                # Deliberately NOT gated on the FORMAT's status: a format the
                # maker has discontinued is still on the branch's shelf and
                # still sellable down to the last sheet (catalog-inventory.md,
                # "Three levels of off"). The branch retires its own row when
                # the shelf is empty; that is level three and it IS gated above.
            )
        )

    counted = await db.execute(
        _visible()
        .with_only_columns(BranchMaterial.branch_id, func.count())
        .group_by(BranchMaterial.branch_id)
    )
    totals = {branch_id: int(total) for branch_id, total in counted.all()}

    ranked = (
        _visible()
        .add_columns(
            func.row_number()
            .over(
                partition_by=BranchMaterial.branch_id,
                order_by=(Manufacturer.name, Decor.name, DecorFormat.thickness_mm),
            )
            .label("rank")
        )
        .subquery()
    )
    top = aliased(BranchMaterial, ranked)
    top_format = aliased(DecorFormat, ranked)
    top_decor = aliased(Decor, ranked)
    top_manufacturer = aliased(Manufacturer, ranked)
    rows = await db.execute(
        select(top, top_format, top_decor, top_manufacturer)
        .select_from(ranked)
        .where(ranked.c.rank <= _BRANCH_PREVIEW_LIMIT)
        .order_by(ranked.c.rank)
    )
    for branch_material, decor_format, decor, manufacturer in rows.all():
        previews.setdefault(branch_material.branch_id, []).append(
            ClientBranchMaterialPreview(
                id=branch_material.id,
                manufacturer_name=manufacturer.name,
                name=branch_material_label(decor_format, decor, manufacturer, branch_material.id),
                price_tiyin=branch_material.price_tiyin,
                display_unit=display_unit(decor_format.type),
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
        select(BranchMaterial, DecorFormat, Decor, Manufacturer)
        .join(DecorFormat, DecorFormat.id == BranchMaterial.decor_format_id)
        .join(Decor, Decor.id == DecorFormat.decor_id)
        .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
        .where(
            BranchMaterial.branch_id == branch_id,
            BranchMaterial.status == MaterialStatus.ACTIVE,
            # No price gate: a branch registers its format list long before it
            # prices it, and a client browsing the shelf should see what the
            # branch actually works with. The row carries `price_unset` so the
            # screen can label it, and confirming an order that sells an
            # unpriced material is blocked in `sales` instead. The branch-card
            # preview drops the same gate, so its "+N more" count still agrees
            # with this list — see _branch_material_previews.
            Decor.status == MaterialStatus.ACTIVE,
            Manufacturer.status == MaterialStatus.ACTIVE,
        )
    )

    async def run(plan: SearchPlan) -> list[Any]:
        # The catalog's one matcher again — the client browsing a branch's shelf
        # searches it by the same rules as the staff who registered it.
        searched = apply_decor_search(
            query,
            plan,
            ordering=(Manufacturer.name, Decor.name, DecorFormat.thickness_mm),
            dimension_arms=format_dimension_arms,
        )
        if plan.limit is not None:
            searched = searched.limit(plan.limit)
        return list((await db.execute(searched)).all())

    rows = await run_search_tiers(db, search, run)
    return [
        ClientBranchMaterialResponse(
            id=branch_material.id,
            type=decor_format.type,
            manufacturer_name=manufacturer.name,
            code=decor.code,
            name=decor.name,
            has_grain=decor.has_grain,
            image_file_id=decor.image_file_id,
            thickness_mm=normalize_mm(decor_format.thickness_mm),
            length_mm=decor_format.length_mm,
            width_mm=decor_format.width_mm,
            tape_width_mm=decor_format.tape_width_mm,
            finished_sides=decor_format.finished_sides,
            price_tiyin=branch_material.price_tiyin,
            display_unit=display_unit(decor_format.type),
        )
        for branch_material, decor_format, decor, manufacturer in rows
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
