"""Client and workshop cutting routes."""

import uuid
from functools import partial
from typing import Annotated

import anyio.to_thread
from fastapi import APIRouter, File, Form, Query, Response, UploadFile, status

from app.api.deps import AccountReadyPrincipal, Session
from app.core.errors import APIError
from app.models.enums import MaterialKind
from app.modules.cutting.api import (
    choose_result,
    choose_workshop_result,
    client_catalog_materials,
    commit_imported_map,
    create_draft,
    create_workshop_draft,
    delete_draft,
    delete_workshop_draft,
    get_client_result,
    get_draft,
    get_workshop_draft,
    get_workshop_result,
    list_drafts,
    optimize_draft,
    optimize_workshop_draft,
    parse_import_file,
    render_cutting_pdf,
    render_cutting_svg,
    update_draft,
    update_workshop_draft,
    workshop_catalog_materials,
)
from app.modules.cutting.import_schemas import ImportParseResponse
from app.modules.cutting.imports.base import (
    MAX_IMPORT_FILE_BYTES,
    ImportParseError,
    parse_options_json,
)
from app.modules.cutting.schemas import (
    ClientCatalogMaterialOption,
    CuttingChooseResultRequest,
    CuttingDraftPatchRequest,
    CuttingDraftResponse,
    CuttingMapImportCommitRequest,
    WorkshopCuttingDraftCreateRequest,
)

router = APIRouter(tags=["cutting"])


@router.post("/client/cutting/import/parse", response_model=ImportParseResponse)
async def client_cutting_import_parse(
    principal: AccountReadyPrincipal,
    file: Annotated[UploadFile, File()],
    options: Annotated[str | None, Form()] = None,
) -> ImportParseResponse:
    del principal
    content = await file.read(MAX_IMPORT_FILE_BYTES + 1)
    try:
        parse_options = parse_options_json(options)
        return await anyio.to_thread.run_sync(
            partial(
                parse_import_file,
                filename=file.filename,
                content=content,
                options=parse_options,
            )
        )
    except ImportParseError as exc:
        raise APIError(
            exc.code,
            exc.message,
            status_code=exc.status_code,
            details=exc.details,
        ) from exc


@router.post("/client/cutting/import/map/commit", response_model=CuttingDraftResponse)
async def client_cutting_import_map_commit(
    payload: CuttingMapImportCommitRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> CuttingDraftResponse:
    return await commit_imported_map(db, principal=principal, payload=payload)


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
    limit: int | None = Query(default=None, ge=1, le=200),
) -> list[ClientCatalogMaterialOption]:
    return await client_catalog_materials(
        db,
        principal=principal,
        kind=kind,
        branch_id=branch_id,
        search=search,
        manufacturer_id=manufacturer_id,
        carried_only=carried_only,
        limit=limit,
    )


# ── Workshop staff acting for a walk-in client (manage_orders) ────────────────


@router.post(
    "/workshop/cutting-drafts",
    response_model=CuttingDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def workshop_cutting_drafts_create(
    payload: WorkshopCuttingDraftCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> CuttingDraftResponse:
    return await create_workshop_draft(
        db,
        principal=principal,
        client_id=payload.client_id,
        branch_id=payload.branch_id,
    )


@router.get("/workshop/cutting-drafts/{draft_id}", response_model=CuttingDraftResponse)
async def workshop_cutting_drafts_show(
    draft_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> CuttingDraftResponse:
    return await get_workshop_draft(db, principal=principal, draft_id=draft_id)


@router.patch("/workshop/cutting-drafts/{draft_id}", response_model=CuttingDraftResponse)
async def workshop_cutting_drafts_update(
    draft_id: uuid.UUID,
    payload: CuttingDraftPatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> CuttingDraftResponse:
    return await update_workshop_draft(
        db,
        principal=principal,
        draft_id=draft_id,
        preferred_branch_id_set="preferred_branch_id" in payload.model_fields_set,
        preferred_branch_id=payload.preferred_branch_id,
        parts_snapshot=payload.parts_snapshot,
    )


@router.delete("/workshop/cutting-drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def workshop_cutting_drafts_delete(
    draft_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> None:
    await delete_workshop_draft(db, principal=principal, draft_id=draft_id)


@router.post("/workshop/cutting-drafts/{draft_id}/optimize", response_model=CuttingDraftResponse)
async def workshop_cutting_drafts_optimize(
    draft_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> CuttingDraftResponse:
    return await optimize_workshop_draft(db, principal=principal, draft_id=draft_id)


@router.post(
    "/workshop/cutting-drafts/{draft_id}/chosen-result", response_model=CuttingDraftResponse
)
async def workshop_cutting_drafts_choose_result(
    draft_id: uuid.UUID,
    payload: CuttingChooseResultRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> CuttingDraftResponse:
    return await choose_workshop_result(
        db,
        principal=principal,
        draft_id=draft_id,
        result_id=payload.result_id,
    )


@router.get("/workshop/cutting-results/{result_id}/pdf")
async def workshop_cutting_results_pdf(
    result_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> Response:
    result = await get_workshop_result(db, principal=principal, result_id=result_id)
    headers = {"Content-Disposition": f'attachment; filename="cutting-{result.id}.pdf"'}
    return Response(render_cutting_pdf(result), media_type="application/pdf", headers=headers)


@router.get("/workshop/catalog/materials", response_model=list[ClientCatalogMaterialOption])
async def workshop_catalog_materials_index(
    principal: AccountReadyPrincipal,
    db: Session,
    kind: MaterialKind,
    branch_id: uuid.UUID,
    search: str | None = None,
    manufacturer_id: uuid.UUID | None = None,
    carried_only: bool = False,
    limit: int | None = Query(default=None, ge=1, le=200),
) -> list[ClientCatalogMaterialOption]:
    return await workshop_catalog_materials(
        db,
        principal=principal,
        kind=kind,
        branch_id=branch_id,
        search=search,
        manufacturer_id=manufacturer_id,
        carried_only=carried_only,
        limit=limit,
    )
