"""Cutting persistence + service — draft CRUD, optimise runs, result lifecycle.

Routes stay thin; this owns validation, persistence, and the order-facing
functions the orders module imports. The pure solver lives in
``cutting_optimizer``. Spec: docs/ref/features/cutting.md,
docs/ref/entities/cutting.md.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

import anyio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, forbidden, not_found
from app.core.principal import Principal
from app.models.catalog import BranchMaterial, Material
from app.models.cutting import (
    CuttingDraft,
    CuttingPlacement,
    CuttingResult,
    CuttingSheet,
)
from app.models.enums import (
    BranchStatus,
    CatalogStatus,
    CuttingResultStatus,
    MaterialKind,
)
from app.models.workshop import Branch
from app.services import audit
from app.services import cutting_optimizer as opt

BranchesMode = Literal["branches", "any", "none"]
MAX_OPEN_DRAFTS = 50


# --- draft access -----------------------------------------------------------


async def get_owned_draft(
    db: AsyncSession, client_id: uuid.UUID, draft_id: uuid.UUID
) -> CuttingDraft:
    draft = await db.get(CuttingDraft, draft_id)
    if draft is None:
        raise not_found("Cutting draft not found.")
    if draft.client_id != client_id:
        raise forbidden()
    return draft


async def list_drafts(db: AsyncSession, client_id: uuid.UUID) -> list[CuttingDraft]:
    stmt = (
        select(CuttingDraft)
        .where(CuttingDraft.client_id == client_id)
        .order_by(CuttingDraft.updated_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def create_draft(db: AsyncSession, principal: Principal) -> CuttingDraft:
    open_count = len(await list_drafts(db, principal.id))
    if open_count >= MAX_OPEN_DRAFTS:
        raise AppError(
            "draft_limit_exceeded",
            f"At most {MAX_OPEN_DRAFTS} open drafts; delete some first.",
            status_code=409,
        )
    draft = CuttingDraft(client_id=principal.id, parts_snapshot=[])
    db.add(draft)
    await db.flush()
    await audit.record_action(
        db,
        actor=principal,
        action="cutting_draft.created",
        entity_type="cutting_draft",
        entity_id=draft.id,
    )
    await db.refresh(draft)
    return draft


async def delete_draft(db: AsyncSession, principal: Principal, draft_id: uuid.UUID) -> None:
    draft = await get_owned_draft(db, principal.id, draft_id)
    await _delete_results_for_draft(db, draft.id)
    await db.delete(draft)
    await db.flush()
    await audit.record_action(
        db,
        actor=principal,
        action="cutting_draft.deleted",
        entity_type="cutting_draft",
        entity_id=draft_id,
    )


# --- parts validation + snapshot --------------------------------------------


async def _resolve_material(db: AsyncSession, material_id: uuid.UUID) -> Material:
    material = await db.get(Material, material_id)
    if (
        material is None
        or material.kind is not MaterialKind.SHEET
        or material.status is not CatalogStatus.ACTIVE
    ):
        raise AppError(
            "material_not_found",
            f"Material {material_id} is not an active platform sheet material.",
            status_code=422,
        )
    return material


def _part_to_snapshot(part: Any, part_ref: str) -> dict[str, Any]:
    return {
        "part_ref": part_ref,
        "material_id": str(part.material_id),
        "material_source": part.material_source.value,
        "length_mm": part.length_mm,
        "width_mm": part.width_mm,
        "quantity": part.quantity,
        "edge_top_mm": part.edge_top_mm,
        "edge_bottom_mm": part.edge_bottom_mm,
        "edge_left_mm": part.edge_left_mm,
        "edge_right_mm": part.edge_right_mm,
    }


async def replace_parts(
    db: AsyncSession, principal: Principal, draft_id: uuid.UUID, parts: list[Any]
) -> CuttingDraft:
    """Validate each part references an active platform sheet material, then
    store the snapshot. Clears the chosen result (a stale layout)."""
    draft = await get_owned_draft(db, principal.id, draft_id)
    if not 1 <= len(parts) <= opt.MAX_PARTS:
        raise AppError(
            "validation_error", f"A draft holds 1..{opt.MAX_PARTS} parts.", status_code=422
        )
    snapshot: list[dict[str, Any]] = []
    for part in parts:
        await _resolve_material(db, part.material_id)
        ref = str(part.part_ref) if part.part_ref else str(uuid.uuid4())
        snapshot.append(_part_to_snapshot(part, ref))
    draft.parts_snapshot = snapshot
    draft.chosen_result_id = None
    await db.flush()
    await audit.record_action(
        db,
        actor=principal,
        action="cutting_draft.parts_replaced",
        entity_type="cutting_draft",
        entity_id=draft.id,
        details={"parts": len(snapshot)},
    )
    await db.refresh(draft)
    return draft


# --- optimise ---------------------------------------------------------------


async def _build_specs(
    db: AsyncSession, snapshot: list[dict[str, Any]]
) -> dict[str, opt.SheetSpec]:
    specs: dict[str, opt.SheetSpec] = {}
    for raw in snapshot:
        mid = raw["material_id"]
        if mid in specs:
            continue
        material = await _resolve_material(db, uuid.UUID(mid))
        if material.sheet_length_mm is None or material.sheet_width_mm is None:
            raise AppError(
                "material_not_found",
                f"Material {mid} has no sheet dimensions.",
                status_code=422,
            )
        specs[mid] = opt.SheetSpec(
            material_id=mid,
            sheet_length_mm=material.sheet_length_mm,
            sheet_width_mm=material.sheet_width_mm,
            grain_direction=bool(material.grain_direction),
        )
    return specs


def _snapshot_to_parts(snapshot: list[dict[str, Any]]) -> list[opt.PartInput]:
    return [
        opt.PartInput(
            part_ref=raw["part_ref"],
            material_id=raw["material_id"],
            length_mm=raw["length_mm"],
            width_mm=raw["width_mm"],
            quantity=raw["quantity"],
            edge_top_mm=raw.get("edge_top_mm"),
            edge_bottom_mm=raw.get("edge_bottom_mm"),
            edge_left_mm=raw.get("edge_left_mm"),
            edge_right_mm=raw.get("edge_right_mm"),
        )
        for raw in snapshot
    ]


async def _delete_results_for_draft(
    db: AsyncSession, draft_id: uuid.UUID, *, only_candidate: bool = False
) -> None:
    stmt = select(CuttingResult).where(CuttingResult.draft_id == draft_id)
    if only_candidate:
        stmt = stmt.where(CuttingResult.status == CuttingResultStatus.CANDIDATE)
    results = list((await db.execute(stmt)).scalars().all())
    for result in results:
        await _delete_result_children(db, result.id)
        await db.delete(result)
    await db.flush()


async def _delete_result_children(db: AsyncSession, result_id: uuid.UUID) -> None:
    sheets = list(
        (await db.execute(select(CuttingSheet).where(CuttingSheet.cutting_result_id == result_id)))
        .scalars()
        .all()
    )
    for sheet in sheets:
        placements = list(
            (
                await db.execute(
                    select(CuttingPlacement).where(CuttingPlacement.cutting_sheet_id == sheet.id)
                )
            )
            .scalars()
            .all()
        )
        for placement in placements:
            await db.delete(placement)
        await db.delete(sheet)
    await db.flush()


async def _persist_result(
    db: AsyncSession, draft: CuttingDraft, ar: opt.AlgorithmResult
) -> CuttingResult:
    result = CuttingResult(
        draft_id=draft.id,
        algorithm_name=ar.algorithm_name,
        algorithm_version=ar.algorithm_version,
        status=CuttingResultStatus.CANDIDATE,
        kerf_mm=ar.kerf_mm,
        edge_trim_mm=ar.edge_trim_mm,
        sheets_used_by_material=ar.sheets_used_by_material,
        waste_percentage=ar.waste_percentage,
        total_cut_length_mm=ar.total_cut_length_mm,
        total_edge_length_mm=ar.total_edge_length_mm,
        edge_length_by_thickness=ar.edge_length_by_thickness,
    )
    db.add(result)
    await db.flush()
    for s in ar.sheets:
        sheet = CuttingSheet(
            cutting_result_id=result.id,
            material_id=uuid.UUID(s.material_id),
            sheet_index=s.sheet_index,
            waste_area_mm2=s.waste_area_mm2,
        )
        db.add(sheet)
        await db.flush()
        for p in s.placements:
            db.add(
                CuttingPlacement(
                    cutting_sheet_id=sheet.id,
                    part_ref=p.part_ref,
                    part_quantity_index=p.part_quantity_index,
                    x_mm=p.x_mm,
                    y_mm=p.y_mm,
                    length_mm=p.length_mm,
                    width_mm=p.width_mm,
                    rotated=p.rotated,
                )
            )
    await db.flush()
    return result


async def optimise(
    db: AsyncSession, principal: Principal, draft_id: uuid.UUID
) -> tuple[CuttingDraft, list[CuttingResult]]:
    """Validate parts, run all algorithms off the event loop, replace the
    previous run's candidate results, persist new ones, and set the chosen one
    (lowest weighted waste)."""
    draft = await get_owned_draft(db, principal.id, draft_id)
    snapshot = list(draft.parts_snapshot or [])
    if not snapshot:
        raise AppError("validation_error", "Add parts before optimising.", status_code=422)

    specs = await _build_specs(db, snapshot)
    parts = _snapshot_to_parts(snapshot)

    # CPU work off the event loop, with a wall-clock budget enforced inside.
    algorithm_results = await anyio.to_thread.run_sync(lambda: opt.optimise(parts, specs))

    # replace the previous run's candidates
    await _delete_results_for_draft(db, draft.id, only_candidate=True)

    persisted: list[CuttingResult] = []
    for ar in algorithm_results:
        persisted.append(await _persist_result(db, draft, ar))

    chosen_idx = algorithm_results.index(opt.winner(algorithm_results))
    chosen = persisted[chosen_idx]
    draft.chosen_result_id = chosen.id
    await db.flush()

    await audit.record_action(
        db,
        actor=principal,
        action="cutting_draft.optimised",
        entity_type="cutting_draft",
        entity_id=draft.id,
        details={
            "results": len(persisted),
            "chosen": str(chosen.id),
            "waste": float(chosen.waste_percentage),
        },
    )
    await db.refresh(draft)
    return draft, persisted


async def choose_result(
    db: AsyncSession, principal: Principal, draft_id: uuid.UUID, result_id: uuid.UUID
) -> CuttingDraft:
    draft = await get_owned_draft(db, principal.id, draft_id)
    result = await db.get(CuttingResult, result_id)
    if (
        result is None
        or result.draft_id != draft.id
        or result.status is not CuttingResultStatus.CANDIDATE
    ):
        raise not_found("Cutting result not found for this draft.")
    draft.chosen_result_id = result.id
    await db.flush()
    await audit.record_action(
        db,
        actor=principal,
        action="cutting_draft.result_chosen",
        entity_type="cutting_draft",
        entity_id=draft.id,
        details={"chosen": str(result.id)},
    )
    await db.refresh(draft)
    return draft


# --- result reads (with eager-loaded layout) --------------------------------


async def load_result_with_layout(
    db: AsyncSession, result_id: uuid.UUID
) -> tuple[CuttingResult, list[tuple[CuttingSheet, list[CuttingPlacement]]]]:
    result = await db.get(CuttingResult, result_id)
    if result is None:
        raise not_found("Cutting result not found.")
    sheets = list(
        (
            await db.execute(
                select(CuttingSheet)
                .where(CuttingSheet.cutting_result_id == result_id)
                .order_by(CuttingSheet.material_id, CuttingSheet.sheet_index)
            )
        )
        .scalars()
        .all()
    )
    layout: list[tuple[CuttingSheet, list[CuttingPlacement]]] = []
    for sheet in sheets:
        placements = list(
            (
                await db.execute(
                    select(CuttingPlacement).where(CuttingPlacement.cutting_sheet_id == sheet.id)
                )
            )
            .scalars()
            .all()
        )
        layout.append((sheet, placements))
    return result, layout


# --- branches indicator -----------------------------------------------------


async def branches_for_materials(
    db: AsyncSession, material_ids: list[uuid.UUID]
) -> tuple[BranchesMode, list[Branch], list[uuid.UUID]]:
    """Active (and temporarily-closed, visible) branches that carry every SHOP
    material in the draft.

    Returns ``(mode, branches, uncovered_material_ids)`` where mode is:

    * ``"any"`` — no shop materials (all-own): any active branch with a saw.
    * ``"branches"`` — at least one branch covers the whole composition.
    * ``"none"`` — no branch covers it; uncovered ids are listed.
    """
    visible_statuses = (BranchStatus.ACTIVE, BranchStatus.TEMPORARILY_CLOSED)

    branch_rows = list(
        (
            await db.execute(
                select(Branch).where(Branch.status.in_(visible_statuses)).order_by(Branch.name)
            )
        )
        .scalars()
        .all()
    )

    needed = set(material_ids)
    if not needed:
        # all-own composition → any active branch with a saw
        return "any", branch_rows, []

    # only consider materials that are active platform sheets
    active_materials = set(
        (
            await db.execute(
                select(Material.id).where(
                    Material.id.in_(needed),
                    Material.status == CatalogStatus.ACTIVE,
                    Material.kind == MaterialKind.SHEET,
                )
            )
        )
        .scalars()
        .all()
    )

    covering: list[Branch] = []
    uncovered_overall = set(needed)
    for branch in branch_rows:
        carried = set(
            (
                await db.execute(
                    select(BranchMaterial.material_id).where(
                        BranchMaterial.branch_id == branch.id,
                        BranchMaterial.material_id.in_(needed),
                        BranchMaterial.status == CatalogStatus.ACTIVE,
                    )
                )
            )
            .scalars()
            .all()
        )
        carried &= active_materials
        uncovered_overall -= carried
        if needed <= carried:
            covering.append(branch)

    if covering:
        return "branches", covering, []
    # name materials no visible branch (or the catalog) covers
    return "none", [], sorted(uncovered_overall, key=str)


# --- order-facing functions (imported by the orders module) -----------------


async def get_chosen_result(db: AsyncSession, draft: CuttingDraft) -> CuttingResult | None:
    """The result the client picked from the latest run, or None between edits."""
    if draft.chosen_result_id is None:
        return None
    return await db.get(CuttingResult, draft.chosen_result_id)


async def confirm_result_for_order(
    db: AsyncSession, draft: CuttingDraft, order_id: uuid.UUID
) -> CuttingResult:
    """Flip the chosen result to CONFIRMED and bind it to an order.

    Sets order_id + confirmed_at, clears draft_id, then deletes the draft and
    its other (unchosen) candidate results — per the cutting.md lifecycle.
    Returns the confirmed result. Raises ``cutting_result_not_usable`` if the
    draft has no chosen result or it isn't a candidate.
    """
    chosen = await get_chosen_result(db, draft)
    if chosen is None or chosen.status is not CuttingResultStatus.CANDIDATE:
        raise AppError(
            "cutting_result_not_usable",
            "This draft has no usable chosen cutting result.",
            status_code=409,
        )
    # discard the other candidates from the same run
    others = list(
        (
            await db.execute(
                select(CuttingResult).where(
                    CuttingResult.draft_id == draft.id,
                    CuttingResult.id != chosen.id,
                    CuttingResult.status == CuttingResultStatus.CANDIDATE,
                )
            )
        )
        .scalars()
        .all()
    )
    for other in others:
        await _delete_result_children(db, other.id)
        await db.delete(other)

    chosen.status = CuttingResultStatus.CONFIRMED
    chosen.order_id = order_id
    chosen.confirmed_at = datetime.now(UTC)
    chosen.draft_id = None
    await db.flush()

    await db.delete(draft)
    await db.flush()
    return chosen


async def invalidate_result(db: AsyncSession, result: CuttingResult) -> CuttingResult:
    """Mark a confirmed result invalidated (an order modify bound a fresher one).
    Kept forever for audit."""
    result.status = CuttingResultStatus.INVALIDATED
    result.invalidated_at = datetime.now(UTC)
    await db.flush()
    return result
