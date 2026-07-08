"""Cutting draft/result use cases."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import status
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import (
    CuttingResultStatus,
    MaterialKind,
    MaterialStatus,
)
from app.modules.catalog.contracts import BranchMaterial, Manufacturer, Material
from app.modules.client_portal.api import get_client_profile, require_client, visible_branch
from app.modules.cutting.contracts import (
    CuttingDraft,
    CuttingPanel,
    CuttingPlacement,
    CuttingResult,
)
from app.modules.cutting.optimizer import (
    EDGE_TRIM_MM,
    EdgeBandInput,
    OptimizerError,
    PanelSpec,
    PartInput,
    run_all_algorithms,
)
from app.modules.cutting.schemas import (
    ClientCatalogMaterialOption,
    CuttingDraftResponse,
    CuttingPanelResponse,
    CuttingPart,
    CuttingPlacementResponse,
    CuttingResultResponse,
)
from app.modules.inventory.api import display_unit
from app.modules.sales.contracts import Order
from app.modules.support.api import record_action

DRAFT_LIMIT = 50


async def create_draft(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
) -> CuttingDraftResponse:
    client = await get_client_profile(db, principal=principal)
    # Staff-minted drafts (created_via_workshop_id set) never count toward the
    # client's own draft budget — the limit is a client-path backstop only.
    count = await db.scalar(
        select(func.count(CuttingDraft.id)).where(
            CuttingDraft.client_id == client.id,
            CuttingDraft.created_via_workshop_id.is_(None),
        )
    )
    if count is not None and count >= DRAFT_LIMIT:
        raise APIError(
            "draft_limit_exceeded",
            "Draft limit exceeded",
            status_code=status.HTTP_409_CONFLICT,
        )
    draft = CuttingDraft(
        client_id=client.id,
        preferred_branch_id=client.preferred_branch_id,
        parts_snapshot=[],
    )
    db.add(draft)
    await db.flush()
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="cutting_draft.create",
        entity_type="cutting_draft",
        entity_id=draft.id,
        summary="Created cutting draft",
    )
    return await _draft_response(db, draft)


async def list_drafts(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
) -> list[CuttingDraftResponse]:
    client = await get_client_profile(db, principal=principal)
    rows = (
        await db.execute(
            select(CuttingDraft)
            # Staff-minted drafts stay invisible on the client's own surface
            # until the order is placed (symmetric privacy).
            .where(
                CuttingDraft.client_id == client.id,
                CuttingDraft.created_via_workshop_id.is_(None),
            )
            .order_by(CuttingDraft.updated_at.desc(), CuttingDraft.created_at.desc())
        )
    ).scalars()
    # Drafts list omits per-panel placements (CB-39) — the list cards only show
    # waste %, panel counts, and material labels.
    return [await _draft_response(db, draft, summary=True) for draft in rows]


async def get_draft(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
) -> CuttingDraftResponse:
    draft = await _client_draft(db, principal=principal, draft_id=draft_id)
    return await _draft_response(db, draft)


async def update_draft(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
    preferred_branch_id_set: bool,
    preferred_branch_id: uuid.UUID | None,
    parts_snapshot: list[CuttingPart] | None,
) -> CuttingDraftResponse:
    draft = await _client_draft(db, principal=principal, draft_id=draft_id)
    resolved_branch_id = preferred_branch_id
    if preferred_branch_id_set and preferred_branch_id is not None:
        # Client browsability check (public catalog); tenancy is not the concern
        # on the client path.
        resolved_branch_id = (await visible_branch(db, preferred_branch_id)).id
    return await _apply_update(
        db,
        draft=draft,
        principal=principal,
        preferred_branch_id_set=preferred_branch_id_set,
        preferred_branch_id=resolved_branch_id,
        parts_snapshot=parts_snapshot,
    )


async def _apply_update(
    db: AsyncSession,
    *,
    draft: CuttingDraft,
    principal: AuthenticatedPrincipal,
    preferred_branch_id_set: bool,
    preferred_branch_id: uuid.UUID | None,
    parts_snapshot: list[CuttingPart] | None,
) -> CuttingDraftResponse:
    """Shared update body: branch id is already resolved/authorized by the caller."""
    parts_changed = parts_snapshot is not None
    if preferred_branch_id_set:
        draft.preferred_branch_id = preferred_branch_id
    if parts_changed:
        normalized_parts, _, _, _ = await _validate_parts(db, parts_snapshot or [])
        draft.parts_snapshot = normalized_parts
        draft.chosen_result_id = None
        await _delete_candidate_results(db, draft.id)
    draft.updated_at = datetime.now(UTC)
    await db.flush()
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="cutting_draft.update",
        entity_type="cutting_draft",
        entity_id=draft.id,
        summary="Updated cutting draft",
        details={
            "preferred_branch_id": str(draft.preferred_branch_id)
            if draft.preferred_branch_id
            else None,
            "parts_changed": parts_changed,
        },
    )
    return await _draft_response(db, draft)


async def delete_draft(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
) -> None:
    draft = await _client_draft(db, principal=principal, draft_id=draft_id)
    await _apply_delete(db, draft=draft, principal=principal)


async def _apply_delete(
    db: AsyncSession,
    *,
    draft: CuttingDraft,
    principal: AuthenticatedPrincipal,
) -> None:
    draft.chosen_result_id = None
    await db.flush()
    await _delete_candidate_results(db, draft.id)
    await db.delete(draft)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="cutting_draft.delete",
        entity_type="cutting_draft",
        entity_id=draft.id,
        summary="Deleted cutting draft",
    )


async def optimize_draft(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
) -> CuttingDraftResponse:
    draft = await _client_draft(db, principal=principal, draft_id=draft_id)
    return await _apply_optimize(db, draft=draft, principal=principal)


async def _apply_optimize(
    db: AsyncSession,
    *,
    draft: CuttingDraft,
    principal: AuthenticatedPrincipal,
) -> CuttingDraftResponse:
    if not draft.parts_snapshot:
        raise APIError("empty_parts", "At least one part is required")
    parts, optimizer_parts, panel_specs, material_snapshots = await _validate_parts(
        db,
        [CuttingPart.model_validate(part) for part in draft.parts_snapshot],
        require_non_empty=True,
    )
    draft.parts_snapshot = parts
    try:
        optimizer_results = run_all_algorithms(optimizer_parts, panel_specs)
    except OptimizerError as exc:
        raise APIError(
            exc.code,
            exc.message,
            details=_optimizer_error_details(exc),
        ) from exc

    draft.chosen_result_id = None
    await db.flush()
    await _delete_candidate_results(db, draft.id)
    now = datetime.now(UTC)
    created_results: list[CuttingResult] = []
    for optimizer_result in optimizer_results:
        result = CuttingResult(
            draft_id=draft.id,
            algorithm_name=optimizer_result.algorithm_name,
            algorithm_version=optimizer_result.algorithm_version,
            status=CuttingResultStatus.CANDIDATE,
            kerf_mm=optimizer_result.kerf_mm,
            edge_trim_mm=optimizer_result.edge_trim_mm,
            panels_used_by_material=optimizer_result.panels_used_by_material,
            waste_percentage=optimizer_result.waste_percentage,
            total_cut_length_mm=optimizer_result.total_cut_length_mm,
            total_edge_length_mm=optimizer_result.total_edge_length_mm,
            edge_length_by_material=optimizer_result.edge_length_by_material,
            parts_snapshot=parts,
            material_snapshots=material_snapshots,
            edge_length_shop_by_material=optimizer_result.edge_length_shop_by_material,
            edge_length_own_by_material=optimizer_result.edge_length_own_by_material,
            edge_consumed_shop_by_material=optimizer_result.edge_consumed_shop_by_material,
            edge_consumed_own_by_material=optimizer_result.edge_consumed_own_by_material,
            edge_banded_sides_by_material=optimizer_result.edge_banded_sides_by_material,
            created_at=now,
        )
        db.add(result)
        await db.flush()
        for panel in optimizer_result.panels:
            panel_row = CuttingPanel(
                cutting_result_id=result.id,
                material_id=panel.material_id,
                panel_index=panel.panel_index,
                waste_area_mm2=panel.waste_area_mm2,
            )
            db.add(panel_row)
            await db.flush()
            for placement in panel.placements:
                db.add(
                    CuttingPlacement(
                        cutting_panel_id=panel_row.id,
                        part_ref=placement.part_ref,
                        part_quantity_index=placement.part_quantity_index,
                        x_mm=placement.x_mm,
                        y_mm=placement.y_mm,
                        length_mm=placement.length_mm,
                        width_mm=placement.width_mm,
                        rotated=placement.rotated,
                    )
                )
        created_results.append(result)
    winner = min(created_results, key=lambda item: (item.waste_percentage, item.algorithm_name))
    draft.chosen_result_id = winner.id
    draft.updated_at = now
    await db.flush()
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="cutting_draft.optimize",
        entity_type="cutting_draft",
        entity_id=draft.id,
        summary="Optimized cutting draft",
        details={"result_ids": [str(result.id) for result in created_results]},
    )
    return await _draft_response(db, draft)


async def choose_result(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
    result_id: uuid.UUID,
) -> CuttingDraftResponse:
    draft = await _client_draft(db, principal=principal, draft_id=draft_id)
    return await _apply_choose(db, draft=draft, principal=principal, result_id=result_id)


async def _apply_choose(
    db: AsyncSession,
    *,
    draft: CuttingDraft,
    principal: AuthenticatedPrincipal,
    result_id: uuid.UUID,
) -> CuttingDraftResponse:
    result = await db.get(CuttingResult, result_id)
    if (
        result is None
        or result.draft_id != draft.id
        or result.status is not CuttingResultStatus.CANDIDATE
    ):
        raise APIError(
            "cutting_result_not_found",
            "Cutting result not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    draft.chosen_result_id = result.id
    draft.updated_at = datetime.now(UTC)
    await db.flush()
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="cutting_result.choose",
        entity_type="cutting_result",
        entity_id=result.id,
        summary="Chose cutting result",
    )
    return await _draft_response(db, draft)


async def get_client_result(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    result_id: uuid.UUID,
) -> CuttingResultResponse:
    require_client(principal)
    result = await db.get(CuttingResult, result_id)
    if result is None:
        raise APIError(
            "cutting_result_not_found",
            "Cutting result not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if result.status is CuttingResultStatus.CANDIDATE:
        draft = await db.get(CuttingDraft, result.draft_id) if result.draft_id else None
        # Candidate results of staff-minted drafts stay hidden from the client
        # until the order is placed (then the order-ownership branch applies).
        if (
            draft is None
            or draft.client_id != principal.principal_id
            or draft.created_via_workshop_id is not None
        ):
            raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    else:
        order = await db.get(Order, result.order_id) if result.order_id else None
        if order is None or order.client_id != principal.principal_id:
            raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)
    return await _result_response(db, result)


async def client_catalog_materials(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    kind: MaterialKind,
    branch_id: uuid.UUID | None = None,
    search: str | None = None,
    manufacturer_id: uuid.UUID | None = None,
    carried_only: bool = True,
    limit: int | None = None,
) -> list[ClientCatalogMaterialOption]:
    require_client(principal)
    if branch_id is not None:
        await visible_branch(db, branch_id)
    return await _catalog_materials(
        db,
        kind=kind,
        branch_id=branch_id,
        search=search,
        manufacturer_id=manufacturer_id,
        carried_only=carried_only,
        limit=limit,
    )


async def _catalog_materials(
    db: AsyncSession,
    *,
    kind: MaterialKind,
    branch_id: uuid.UUID | None,
    search: str | None,
    manufacturer_id: uuid.UUID | None,
    carried_only: bool,
    limit: int | None,
) -> list[ClientCatalogMaterialOption]:
    """Catalog listing shared by the client and workshop editors — the caller
    authorizes the branch (public browsability vs workshop tenancy) first."""
    query = (
        select(Material, Manufacturer, BranchMaterial)
        .join(Manufacturer, Manufacturer.id == Material.manufacturer_id)
        .outerjoin(
            BranchMaterial,
            and_(
                BranchMaterial.material_id == Material.id,
                BranchMaterial.branch_id == branch_id,
                BranchMaterial.status == MaterialStatus.ACTIVE,
            ),
        )
        .where(
            Material.kind == kind,
            Material.status == MaterialStatus.ACTIVE,
            Manufacturer.status == MaterialStatus.ACTIVE,
        )
        .order_by(Manufacturer.name, Material.name)
    )
    if branch_id is not None and carried_only:
        query = query.where(BranchMaterial.id.is_not(None))
    if manufacturer_id is not None:
        query = query.where(Material.manufacturer_id == manufacturer_id)
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
    # Cap the result set when asked (CB-40) — the client passes a limit only for the
    # unbounded no-preferred-branch load, so a fresh draft doesn't pull the whole
    # catalog. A branch-scoped load stays unlimited (CB-84 filters + CB-19/86 recovery
    # need the full per-branch list client-side). Deterministic with the ORDER BY above.
    if limit is not None:
        query = query.limit(limit)
    rows = (await db.execute(query)).all()
    return [
        ClientCatalogMaterialOption(
            id=material.id,
            kind=material.kind,
            manufacturer_id=material.manufacturer_id,
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
            branch_carried=branch_material is not None,
            price_tiyin=branch_material.price_tiyin if branch_material is not None else None,
            display_unit=display_unit(material.kind),
        )
        for material, manufacturer, branch_material in rows
    ]


async def cutting_result_response(
    db: AsyncSession,
    result: CuttingResult,
) -> CuttingResultResponse:
    return await _result_response(db, result)


async def _client_draft(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    draft_id: uuid.UUID,
) -> CuttingDraft:
    client = await get_client_profile(db, principal=principal)
    draft = await db.get(CuttingDraft, draft_id)
    # Staff-minted drafts (created_via_workshop_id set) are not part of the
    # client's own surface pre-order — same 404 as a foreign draft.
    if draft is None or draft.client_id != client.id or draft.created_via_workshop_id is not None:
        raise APIError(
            "cutting_draft_not_found",
            "Cutting draft not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return draft


async def _validate_parts(
    db: AsyncSession,
    parts: list[CuttingPart],
    *,
    require_non_empty: bool = False,
) -> tuple[
    list[dict[str, Any]],
    list[PartInput],
    dict[uuid.UUID, PanelSpec],
    dict[str, dict[str, Any]],
]:
    if require_non_empty and not parts:
        raise APIError("empty_parts", "At least one part is required")
    if sum(part.quantity for part in parts) > 100:
        raise APIError("too_many_parts", "Too many parts for one optimization")
    errors: list[dict[str, Any]] = []
    seen_part_refs: set[str] = set()
    material_ids: set[uuid.UUID] = set()
    for row_index, part in enumerate(parts, start=1):
        part.part_ref = part.part_ref.strip()
        if not part.part_ref:
            errors.append(_row_error(part, row_index, "invalid_part_ref", part.material_id))
        elif part.part_ref in seen_part_refs:
            errors.append(_row_error(part, row_index, "duplicate_part_ref", part.material_id))
        else:
            seen_part_refs.add(part.part_ref)
        material_ids.add(part.material_id)
        for side in ("edge_top", "edge_bottom", "edge_left", "edge_right"):
            edge = getattr(part, side)
            if edge is not None:
                material_ids.add(edge.material_id)
    material_rows = await _material_rows(db, material_ids)
    panel_specs: dict[uuid.UUID, PanelSpec] = {}
    material_snapshots: dict[str, dict[str, Any]] = {}
    optimizer_parts: list[PartInput] = []

    for row_index, part in enumerate(parts, start=1):
        panel_row = material_rows.get(part.material_id)
        if panel_row is None:
            errors.append(_row_error(part, row_index, "material_not_found", part.material_id))
            continue
        panel, panel_manufacturer = panel_row
        if panel.kind is not MaterialKind.PANEL:
            errors.append(_row_error(part, row_index, "invalid_panel_material", panel.id))
            continue
        if part.quantity < 1:
            errors.append(_row_error(part, row_index, "invalid_quantity", panel.id))
        if part.length_mm < 50 or part.width_mm < 50:
            errors.append(_row_error(part, row_index, "part_too_small", panel.id))
        if panel.panel_length_mm is None or panel.panel_width_mm is None:
            errors.append(_row_error(part, row_index, "invalid_panel_material", panel.id))
            continue
        usable_length = panel.panel_length_mm - 2 * EDGE_TRIM_MM
        usable_width = panel.panel_width_mm - 2 * EDGE_TRIM_MM
        fits_normal = part.length_mm <= usable_length and part.width_mm <= usable_width
        fits_rotated = part.width_mm <= usable_length and part.length_mm <= usable_width
        locked = bool(panel.grain_direction) and part.follow_grain
        if locked and not fits_normal:
            errors.append(_row_error(part, row_index, "impossible_grain", panel.id))
        elif not locked and not (fits_normal or fits_rotated):
            errors.append(_row_error(part, row_index, "part_too_large", panel.id))
        edge_inputs: dict[str, EdgeBandInput | None] = {}
        for field_name in ("edge_top", "edge_bottom", "edge_left", "edge_right"):
            edge = getattr(part, field_name)
            if edge is None:
                edge_inputs[field_name] = None
                continue
            edge_row = material_rows.get(edge.material_id)
            if edge_row is None:
                errors.append(
                    _row_error(part, row_index, "material_not_found", edge.material_id, field_name)
                )
                edge_inputs[field_name] = None
                continue
            edge_material, edge_manufacturer = edge_row
            if edge_material.kind is not MaterialKind.EDGE:
                errors.append(
                    _row_error(
                        part,
                        row_index,
                        "invalid_edge_material",
                        edge.material_id,
                        field_name,
                    )
                )
                edge_inputs[field_name] = None
                continue
            material_snapshots[str(edge_material.id)] = _material_snapshot(
                edge_material, edge_manufacturer
            )
            edge_inputs[field_name] = EdgeBandInput(
                material_id=edge.material_id,
                source=edge.source,
            )
        material_snapshots[str(panel.id)] = _material_snapshot(panel, panel_manufacturer)
        panel_specs[panel.id] = PanelSpec(
            material_id=panel.id,
            length_mm=panel.panel_length_mm,
            width_mm=panel.panel_width_mm,
            grain_direction=bool(panel.grain_direction),
        )
        optimizer_parts.append(
            PartInput(
                part_ref=part.part_ref,
                row_index=row_index,
                material_id=part.material_id,
                material_source=part.material_source,
                follow_grain=part.follow_grain,
                length_mm=part.length_mm,
                width_mm=part.width_mm,
                quantity=part.quantity,
                edge_top=edge_inputs["edge_top"],
                edge_bottom=edge_inputs["edge_bottom"],
                edge_left=edge_inputs["edge_left"],
                edge_right=edge_inputs["edge_right"],
            )
        )
    if errors:
        raise APIError("invalid_cutting_parts", "Invalid cutting parts", details={"errors": errors})
    return (
        [part.model_dump(mode="json") for part in parts],
        optimizer_parts,
        panel_specs,
        material_snapshots,
    )


async def _material_rows(
    db: AsyncSession,
    material_ids: set[uuid.UUID],
) -> dict[uuid.UUID, tuple[Material, Manufacturer]]:
    if not material_ids:
        return {}
    rows = (
        await db.execute(
            select(Material, Manufacturer)
            .join(Manufacturer, Manufacturer.id == Material.manufacturer_id)
            .where(
                Material.id.in_(material_ids),
                Material.status == MaterialStatus.ACTIVE,
                Manufacturer.status == MaterialStatus.ACTIVE,
            )
        )
    ).all()
    return {material.id: (material, manufacturer) for material, manufacturer in rows}


def _row_error(
    part: CuttingPart,
    row_index: int,
    code: str,
    material_id: uuid.UUID,
    side: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "row_index": row_index,
        "part_ref": part.part_ref,
        "code": code,
        "material_id": str(material_id),
    }
    if side is not None:
        body["side"] = side
    return body


def _optimizer_error_details(exc: OptimizerError) -> dict[str, Any]:
    details: dict[str, Any] = {}
    if exc.part_ref is not None:
        details["part_ref"] = exc.part_ref
    if exc.row_index is not None:
        details["row_index"] = exc.row_index
    if exc.material_id is not None:
        details["material_id"] = str(exc.material_id)
    return details


def _material_snapshot(material: Material, manufacturer: Manufacturer) -> dict[str, Any]:
    return {
        "id": str(material.id),
        "kind": material.kind.value,
        "manufacturer_id": str(material.manufacturer_id),
        "manufacturer_name": manufacturer.name,
        "type": material.type.value if material.type is not None else None,
        "name": material.name,
        "thickness_mm": str(material.thickness_mm),
        "color": material.color,
        "decor_code": material.decor_code,
        "panel_length_mm": material.panel_length_mm,
        "panel_width_mm": material.panel_width_mm,
        "grain_direction": material.grain_direction,
        "image_file_id": str(material.image_file_id) if material.image_file_id else None,
    }


async def _delete_candidate_results(db: AsyncSession, draft_id: uuid.UUID) -> None:
    result_ids = (
        (
            await db.execute(
                select(CuttingResult.id).where(
                    CuttingResult.draft_id == draft_id,
                    CuttingResult.status == CuttingResultStatus.CANDIDATE,
                )
            )
        )
        .scalars()
        .all()
    )
    if not result_ids:
        return
    panel_ids = (
        (
            await db.execute(
                select(CuttingPanel.id).where(CuttingPanel.cutting_result_id.in_(result_ids))
            )
        )
        .scalars()
        .all()
    )
    if panel_ids:
        await db.execute(
            delete(CuttingPlacement).where(CuttingPlacement.cutting_panel_id.in_(panel_ids))
        )
        await db.execute(delete(CuttingPanel).where(CuttingPanel.id.in_(panel_ids)))
    await db.execute(delete(CuttingResult).where(CuttingResult.id.in_(result_ids)))


async def _draft_response(
    db: AsyncSession,
    draft: CuttingDraft,
    *,
    summary: bool = False,
) -> CuttingDraftResponse:
    result_rows = (
        await db.execute(
            select(CuttingResult)
            .where(CuttingResult.draft_id == draft.id)
            .order_by(CuttingResult.waste_percentage.asc(), CuttingResult.algorithm_name.asc())
        )
    ).scalars()
    return CuttingDraftResponse(
        id=draft.id,
        client_id=draft.client_id,
        preferred_branch_id=draft.preferred_branch_id,
        parts_snapshot=_parts_snapshot_response(draft.parts_snapshot),
        chosen_result_id=draft.chosen_result_id,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        results=[await _result_response(db, result, summary=summary) for result in result_rows],
    )


async def _result_response(
    db: AsyncSession,
    result: CuttingResult,
    *,
    summary: bool = False,
) -> CuttingResultResponse:
    # List views (CB-39) only need the headline metrics + material_snapshots, never
    # the per-panel placements — skip those two queries + their serialization.
    panels: list[CuttingPanelResponse] = []
    if not summary:
        panel_rows = (
            (
                await db.execute(
                    select(CuttingPanel)
                    .where(CuttingPanel.cutting_result_id == result.id)
                    .order_by(CuttingPanel.material_id, CuttingPanel.panel_index)
                )
            )
            .scalars()
            .all()
        )
        panel_ids = [panel.id for panel in panel_rows]
        placements_by_panel: dict[uuid.UUID, list[CuttingPlacement]] = {
            panel.id: [] for panel in panel_rows
        }
        if panel_ids:
            placement_rows = (
                await db.execute(
                    select(CuttingPlacement)
                    .where(CuttingPlacement.cutting_panel_id.in_(panel_ids))
                    .order_by(
                        CuttingPlacement.cutting_panel_id,
                        CuttingPlacement.part_ref,
                        CuttingPlacement.part_quantity_index,
                    )
                )
            ).scalars()
            for placement in placement_rows:
                placements_by_panel[placement.cutting_panel_id].append(placement)
        panels = [
            CuttingPanelResponse(
                id=panel.id,
                material_id=panel.material_id,
                panel_index=panel.panel_index,
                waste_area_mm2=panel.waste_area_mm2,
                placements=[
                    CuttingPlacementResponse.model_validate(placement)
                    for placement in placements_by_panel[panel.id]
                ],
            )
            for panel in panel_rows
        ]
    return CuttingResultResponse(
        id=result.id,
        draft_id=result.draft_id,
        algorithm_name=result.algorithm_name,
        algorithm_version=result.algorithm_version,
        status=result.status,
        kerf_mm=result.kerf_mm,
        edge_trim_mm=result.edge_trim_mm,
        panels_used_by_material=result.panels_used_by_material,
        waste_percentage=result.waste_percentage,
        total_cut_length_mm=result.total_cut_length_mm,
        total_edge_length_mm=result.total_edge_length_mm,
        edge_length_by_material=result.edge_length_by_material,
        parts_snapshot=_parts_snapshot_response(result.parts_snapshot),
        material_snapshots=result.material_snapshots,
        edge_length_shop_by_material=result.edge_length_shop_by_material,
        edge_length_own_by_material=result.edge_length_own_by_material,
        edge_consumed_shop_by_material=result.edge_consumed_shop_by_material,
        edge_consumed_own_by_material=result.edge_consumed_own_by_material,
        edge_banded_sides_by_material=result.edge_banded_sides_by_material,
        order_id=result.order_id,
        created_at=result.created_at,
        confirmed_at=result.confirmed_at,
        invalidated_at=result.invalidated_at,
        panels=panels,
    )


def _parts_snapshot_response(parts_snapshot: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [CuttingPart.model_validate(part).model_dump(mode="json") for part in parts_snapshot]
