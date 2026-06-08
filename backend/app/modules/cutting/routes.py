"""Client and workshop cutting routes."""

import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import AccountReadyPrincipal, Session
from app.models.enums import MaterialKind
from app.modules.cutting.api import (
    choose_result,
    client_catalog_materials,
    create_draft,
    delete_draft,
    get_client_result,
    get_draft,
    get_workshop_cutting_plan,
    list_drafts,
    list_workshop_cutting_plans,
    optimize_draft,
    render_cutting_pdf,
    render_cutting_svg,
    update_draft,
)
from app.modules.cutting.schemas import (
    ClientCatalogMaterialOption,
    CuttingChooseResultRequest,
    CuttingDraftPatchRequest,
    CuttingDraftResponse,
    WorkshopCuttingPlanDetail,
    WorkshopCuttingPlanSummary,
)

router = APIRouter(tags=["cutting"])


@router.get("/client/cutting-drafts", response_model=list[CuttingDraftResponse])
async def client_cutting_drafts_index(
    principal: AccountReadyPrincipal,
    db: Session,
) -> list[CuttingDraftResponse]:
    return await list_drafts(db, principal=principal)


@router.post(
    "/client/cutting-drafts",
    response_model=CuttingDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def client_cutting_drafts_create(
    principal: AccountReadyPrincipal,
    db: Session,
) -> CuttingDraftResponse:
    return await create_draft(db, principal=principal)


@router.get("/client/cutting-drafts/{draft_id}", response_model=CuttingDraftResponse)
async def client_cutting_drafts_show(
    draft_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> CuttingDraftResponse:
    return await get_draft(db, principal=principal, draft_id=draft_id)


@router.patch("/client/cutting-drafts/{draft_id}", response_model=CuttingDraftResponse)
async def client_cutting_drafts_update(
    draft_id: uuid.UUID,
    payload: CuttingDraftPatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> CuttingDraftResponse:
    return await update_draft(
        db,
        principal=principal,
        draft_id=draft_id,
        preferred_branch_id_set="preferred_branch_id" in payload.model_fields_set,
        preferred_branch_id=payload.preferred_branch_id,
        parts_snapshot=payload.parts_snapshot,
    )


@router.delete("/client/cutting-drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def client_cutting_drafts_delete(
    draft_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> Response:
    await delete_draft(db, principal=principal, draft_id=draft_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/client/cutting-drafts/{draft_id}/optimize", response_model=CuttingDraftResponse)
async def client_cutting_drafts_optimize(
    draft_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> CuttingDraftResponse:
    return await optimize_draft(db, principal=principal, draft_id=draft_id)


@router.post("/client/cutting-drafts/{draft_id}/chosen-result", response_model=CuttingDraftResponse)
async def client_cutting_drafts_choose_result(
    draft_id: uuid.UUID,
    payload: CuttingChooseResultRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> CuttingDraftResponse:
    return await choose_result(
        db,
        principal=principal,
        draft_id=draft_id,
        result_id=payload.result_id,
    )


@router.get("/client/cutting-results/{result_id}/svg")
async def client_cutting_results_svg(
    result_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> Response:
    result = await get_client_result(db, principal=principal, result_id=result_id)
    return Response(render_cutting_svg(result), media_type="image/svg+xml")


@router.get("/client/cutting-results/{result_id}/pdf")
async def client_cutting_results_pdf(
    result_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> Response:
    result = await get_client_result(db, principal=principal, result_id=result_id)
    headers = {"Content-Disposition": f'attachment; filename="cutting-{result.id}.pdf"'}
    return Response(render_cutting_pdf(result), media_type="application/pdf", headers=headers)


@router.get("/client/catalog/materials", response_model=list[ClientCatalogMaterialOption])
async def client_catalog_materials_index(
    principal: AccountReadyPrincipal,
    db: Session,
    kind: MaterialKind,
    branch_id: uuid.UUID | None = None,
    search: str | None = None,
    manufacturer_id: uuid.UUID | None = None,
    carried_only: bool = True,
) -> list[ClientCatalogMaterialOption]:
    return await client_catalog_materials(
        db,
        principal=principal,
        kind=kind,
        branch_id=branch_id,
        search=search,
        manufacturer_id=manufacturer_id,
        carried_only=carried_only,
    )


@router.get("/workshop/cutting-plans", response_model=list[WorkshopCuttingPlanSummary])
async def workshop_cutting_plans_index(
    principal: AccountReadyPrincipal,
    db: Session,
) -> list[WorkshopCuttingPlanSummary]:
    return await list_workshop_cutting_plans(db, principal=principal)


@router.get("/workshop/cutting-plans/{result_id}", response_model=WorkshopCuttingPlanDetail)
async def workshop_cutting_plans_show(
    result_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopCuttingPlanDetail:
    return await get_workshop_cutting_plan(db, principal=principal, result_id=result_id)


@router.get("/workshop/cutting-plans/{result_id}/svg")
async def workshop_cutting_plans_svg(
    result_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> Response:
    plan = await get_workshop_cutting_plan(db, principal=principal, result_id=result_id)
    return Response(render_cutting_svg(plan.result), media_type="image/svg+xml")


@router.get("/workshop/cutting-plans/{result_id}/pdf")
async def workshop_cutting_plans_pdf(
    result_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> Response:
    plan = await get_workshop_cutting_plan(db, principal=principal, result_id=result_id)
    headers = {"Content-Disposition": f'attachment; filename="cutting-{plan.id}.pdf"'}
    return Response(render_cutting_pdf(plan.result), media_type="application/pdf", headers=headers)
