"""Client-side cutting routes — drafts, optimise, choose, branches, PDF.

The cutting wizard lives at ``/c/cutting/:id``. All draft routes are scoped to
the authenticated client; results are private until confirmed. A workshop-side
read fetches a confirmed result's layout for the saw.
"""

import uuid

from fastapi import APIRouter, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentClient, CurrentWorkshopUser, Session
from app.core.errors import forbidden, not_found
from app.models.catalog import Material
from app.models.cutting import CuttingResult
from app.models.enums import CuttingResultStatus
from app.schemas.cutting import (
    BranchAvailability,
    BranchesOut,
    DraftOut,
    DraftUpdate,
    OptimiseOut,
    PlacementOut,
    ResultOut,
    SheetOut,
)
from app.services import cutting as service
from app.services import cutting_pdf

client_router = APIRouter()
workshop_router = APIRouter()


# --- draft CRUD -------------------------------------------------------------


@client_router.post("", response_model=DraftOut, status_code=201)
async def create_draft(principal: CurrentClient, db: Session) -> DraftOut:
    draft = await service.create_draft(db, principal)
    return DraftOut.model_validate(draft)


@client_router.get("", response_model=list[DraftOut])
async def list_drafts(principal: CurrentClient, db: Session) -> list[DraftOut]:
    drafts = await service.list_drafts(db, principal.id)
    return [DraftOut.model_validate(d) for d in drafts]


@client_router.get("/{draft_id}", response_model=DraftOut)
async def get_draft(draft_id: uuid.UUID, principal: CurrentClient, db: Session) -> DraftOut:
    draft = await service.get_owned_draft(db, principal.id, draft_id)
    return DraftOut.model_validate(draft)


@client_router.put("/{draft_id}", response_model=DraftOut)
async def replace_parts(
    draft_id: uuid.UUID, body: DraftUpdate, principal: CurrentClient, db: Session
) -> DraftOut:
    draft = await service.replace_parts(db, principal, draft_id, body.parts)
    return DraftOut.model_validate(draft)


@client_router.delete("/{draft_id}", status_code=204)
async def delete_draft(draft_id: uuid.UUID, principal: CurrentClient, db: Session) -> Response:
    await service.delete_draft(db, principal, draft_id)
    return Response(status_code=204)


# --- optimise / choose ------------------------------------------------------


async def _result_out(db: AsyncSession, result: CuttingResult) -> ResultOut:
    loaded, layout = await service.load_result_with_layout(db, result.id)
    out = ResultOut.model_validate(loaded)
    out.sheets = [
        SheetOut(
            id=sheet.id,
            material_id=sheet.material_id,
            sheet_index=sheet.sheet_index,
            waste_area_mm2=sheet.waste_area_mm2,
            placements=[PlacementOut.model_validate(p) for p in placements],
        )
        for sheet, placements in layout
    ]
    return out


@client_router.post("/{draft_id}/optimise", response_model=OptimiseOut)
async def optimise(draft_id: uuid.UUID, principal: CurrentClient, db: Session) -> OptimiseOut:
    draft, results = await service.optimise(db, principal, draft_id)
    return OptimiseOut(
        draft_id=draft.id,
        chosen_result_id=draft.chosen_result_id,
        results=[await _result_out(db, r) for r in results],
    )


@client_router.post("/{draft_id}/choose/{result_id}", response_model=DraftOut)
async def choose_result(
    draft_id: uuid.UUID, result_id: uuid.UUID, principal: CurrentClient, db: Session
) -> DraftOut:
    draft = await service.choose_result(db, principal, draft_id, result_id)
    return DraftOut.model_validate(draft)


# --- branches indicator -----------------------------------------------------


@client_router.get("/{draft_id}/branches", response_model=BranchesOut)
async def branches(draft_id: uuid.UUID, principal: CurrentClient, db: Session) -> BranchesOut:
    draft = await service.get_owned_draft(db, principal.id, draft_id)
    shop_material_ids = sorted(
        {
            uuid.UUID(p["material_id"])
            for p in (draft.parts_snapshot or [])
            if p.get("material_source") == "shop"
        },
        key=str,
    )
    mode, branch_rows, uncovered = await service.branches_for_materials(db, shop_material_ids)
    return BranchesOut(
        mode=mode,
        branches=[BranchAvailability(branch_id=b.id, name=b.name) for b in branch_rows],
        uncovered_material_ids=uncovered,
    )


# --- PDF --------------------------------------------------------------------


async def _render_pdf(db: Session, result_id: uuid.UUID) -> bytes:
    result, layout = await service.load_result_with_layout(db, result_id)
    material_ids = {str(sheet.material_id) for sheet, _ in layout}
    sheet_dims: dict[str, tuple[int, int]] = {}
    labels: dict[str, str] = {}
    for mid in material_ids:
        material = await db.get(Material, uuid.UUID(mid))
        if material is not None:
            sheet_dims[mid] = (
                material.sheet_length_mm or 2800,
                material.sheet_width_mm or 2070,
            )
            labels[mid] = f"{material.name} {material.thickness_mm}mm"
    return cutting_pdf.render_cutting_pdf(
        result, layout, sheet_dims=sheet_dims, material_labels=labels
    )


def _pdf_response(content: bytes, result_id: uuid.UUID) -> Response:
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="cutting-{result_id}.pdf"'},
    )


@client_router.get("/{draft_id}/pdf")
async def draft_pdf(draft_id: uuid.UUID, principal: CurrentClient, db: Session) -> Response:
    draft = await service.get_owned_draft(db, principal.id, draft_id)
    if draft.chosen_result_id is None:
        raise not_found("No chosen result to render; optimise first.")
    content = await _render_pdf(db, draft.chosen_result_id)
    return _pdf_response(content, draft.chosen_result_id)


@client_router.get("/results/{result_id}/pdf")
async def result_pdf(result_id: uuid.UUID, principal: CurrentClient, db: Session) -> Response:
    result = await service.load_result_with_layout(db, result_id)
    cutting_result = result[0]
    # gate to the draft's owner while candidate; confirmed/invalidated are bound
    # to an order (the client owns it too — checked via the draft for candidates).
    if cutting_result.status is CuttingResultStatus.CANDIDATE:
        if cutting_result.draft_id is None:
            raise not_found("Cutting result not found.")
        await service.get_owned_draft(db, principal.id, cutting_result.draft_id)
    content = await _render_pdf(db, result_id)
    return _pdf_response(content, result_id)


# --- workshop read of a confirmed result ------------------------------------


@workshop_router.get("/{result_id}", response_model=ResultOut)
async def workshop_result(result_id: uuid.UUID, _: CurrentWorkshopUser, db: Session) -> ResultOut:
    result, _layout = await service.load_result_with_layout(db, result_id)
    if result.status is CuttingResultStatus.CANDIDATE or result.order_id is None:
        raise forbidden("Only confirmed cutting results are visible to the workshop.")
    return await _result_out(db, result)
