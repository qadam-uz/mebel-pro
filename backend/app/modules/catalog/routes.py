"""Catalog routes: platform decors + decor formats, workshop branch materials."""

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import AccountReadyPrincipal, Session
from app.models.enums import DecorType, MaterialStatus
from app.modules.catalog.api import (
    BranchCatalogOption,
    BranchMaterialRecord,
    DecorFormatRecord,
    DecorRecord,
    attach_branch_materials,
    branch_material_response_from_models,
    create_decor,
    create_decor_format,
    create_manufacturer,
    decor_format_response_from_models,
    decor_response_from_models,
    get_decor,
    get_manufacturer,
    list_branch_catalog_facets,
    list_branch_catalog_formats,
    list_branch_catalog_options,
    list_branch_materials,
    list_decor_formats,
    list_decors,
    list_manufacturers,
    set_branch_material_status,
    set_decor_format_status,
    set_decor_status,
    set_manufacturer_status,
    update_branch_material,
    update_decor,
    update_manufacturer,
)
from app.modules.catalog.schemas import (
    BranchCatalogDecorOption,
    BranchCatalogFiltersResponse,
    BranchCatalogFormatOption,
    BranchCatalogManufacturerOption,
    BranchCatalogOptionsPage,
    BranchMaterialAttachRequest,
    BranchMaterialAttachResponse,
    BranchMaterialPatchRequest,
    BranchMaterialResponse,
    DecorCreateRequest,
    DecorFormatCreateRequest,
    DecorFormatResponse,
    DecorPatchRequest,
    DecorResponse,
    ManufacturerCreateRequest,
    ManufacturerPatchRequest,
    ManufacturerResponse,
)

router = APIRouter(tags=["catalog"])
# `status` is both a query param and a column name; the alias keeps the wire
# name while the Python argument stays unshadowed.
STATUS_QUERY = Query(default=None, alias="status")
# Opt-in limit/offset paging (house convention: bare-list response, client infers
# "has more" from a full page). Omitting limit returns the full list unchanged.
LIMIT_QUERY = Query(default=None, ge=1, le=200)
OFFSET_QUERY = Query(default=0, ge=0)
# Repeated query params (?manufacturer_ids=a&manufacturer_ids=b) → multi-select
# filters. Module-level singletons so the defaults aren't Query() calls (ruff B008).
MANUFACTURER_IDS_QUERY = Query(default=None)
# `type` / `types` on a decor surface mean "has at least one ACTIVE format of
# this substrate" — a decor itself has no type any more.
TYPE_QUERY = Query(default=None, alias="type")
TYPES_QUERY = Query(default=None, alias="types")


@router.get("/platform/catalog/manufacturers", response_model=list[ManufacturerResponse])
async def platform_manufacturers_index(
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    status_filter: MaterialStatus | None = STATUS_QUERY,
) -> list[ManufacturerResponse]:
    rows = await list_manufacturers(
        db,
        principal=principal,
        search=search,
        status_filter=status_filter,
    )
    return [ManufacturerResponse.model_validate(row) for row in rows]


@router.post(
    "/platform/catalog/manufacturers",
    response_model=ManufacturerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def platform_manufacturers_create(
    payload: ManufacturerCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ManufacturerResponse:
    row = await create_manufacturer(db, principal=principal, payload=payload)
    return ManufacturerResponse.model_validate(row)


@router.get(
    "/platform/catalog/manufacturers/{manufacturer_id}",
    response_model=ManufacturerResponse,
)
async def platform_manufacturers_show(
    manufacturer_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ManufacturerResponse:
    row = await get_manufacturer(db, principal=principal, manufacturer_id=manufacturer_id)
    return ManufacturerResponse.model_validate(row)


@router.patch(
    "/platform/catalog/manufacturers/{manufacturer_id}",
    response_model=ManufacturerResponse,
)
async def platform_manufacturers_update(
    manufacturer_id: uuid.UUID,
    payload: ManufacturerPatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ManufacturerResponse:
    row = await update_manufacturer(
        db,
        principal=principal,
        manufacturer_id=manufacturer_id,
        payload=payload,
    )
    return ManufacturerResponse.model_validate(row)


@router.post(
    "/platform/catalog/manufacturers/{manufacturer_id}/activate",
    response_model=ManufacturerResponse,
)
async def platform_manufacturers_activate(
    manufacturer_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ManufacturerResponse:
    row = await set_manufacturer_status(
        db,
        principal=principal,
        manufacturer_id=manufacturer_id,
        to_status=MaterialStatus.ACTIVE,
    )
    return ManufacturerResponse.model_validate(row)


@router.post(
    "/platform/catalog/manufacturers/{manufacturer_id}/deactivate",
    response_model=ManufacturerResponse,
)
async def platform_manufacturers_deactivate(
    manufacturer_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ManufacturerResponse:
    row = await set_manufacturer_status(
        db,
        principal=principal,
        manufacturer_id=manufacturer_id,
        to_status=MaterialStatus.INACTIVE,
    )
    return ManufacturerResponse.model_validate(row)


@router.get("/platform/catalog/decors", response_model=list[DecorResponse])
async def platform_decors_index(
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    type_: DecorType | None = TYPE_QUERY,
    types: list[DecorType] | None = TYPES_QUERY,
    manufacturer_id: uuid.UUID | None = None,
    manufacturer_ids: list[uuid.UUID] | None = MANUFACTURER_IDS_QUERY,
    status_filter: MaterialStatus | None = STATUS_QUERY,
    limit: int | None = LIMIT_QUERY,
    offset: int = OFFSET_QUERY,
) -> list[DecorResponse]:
    rows = await list_decors(
        db,
        principal=principal,
        search=search,
        type_=type_,
        types=types,
        manufacturer_id=manufacturer_id,
        manufacturer_ids=manufacturer_ids,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return [_decor_response(row) for row in rows]


@router.post(
    "/platform/catalog/decors",
    response_model=DecorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def platform_decors_create(
    payload: DecorCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> DecorResponse:
    row = await create_decor(db, principal=principal, payload=payload)
    return _decor_response(row)


@router.get("/platform/catalog/decors/{decor_id}", response_model=DecorResponse)
async def platform_decors_show(
    decor_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> DecorResponse:
    row = await get_decor(db, principal=principal, decor_id=decor_id)
    return _decor_response(row)


@router.patch("/platform/catalog/decors/{decor_id}", response_model=DecorResponse)
async def platform_decors_update(
    decor_id: uuid.UUID,
    payload: DecorPatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> DecorResponse:
    row = await update_decor(db, principal=principal, decor_id=decor_id, payload=payload)
    return _decor_response(row)


@router.post(
    "/platform/catalog/decors/{decor_id}/activate",
    response_model=DecorResponse,
)
async def platform_decors_activate(
    decor_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> DecorResponse:
    row = await set_decor_status(
        db,
        principal=principal,
        decor_id=decor_id,
        to_status=MaterialStatus.ACTIVE,
    )
    return _decor_response(row)


@router.post(
    "/platform/catalog/decors/{decor_id}/deactivate",
    response_model=DecorResponse,
)
async def platform_decors_deactivate(
    decor_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> DecorResponse:
    row = await set_decor_status(
        db,
        principal=principal,
        decor_id=decor_id,
        to_status=MaterialStatus.INACTIVE,
    )
    return _decor_response(row)


# ── Decor formats (platform) ────────────────────────────────────────────────
# No PATCH by design: a format is immutable. A wrong one is deactivated and a
# correct one created, because everything downstream resolves through this id.


@router.get(
    "/platform/catalog/decors/{decor_id}/formats",
    response_model=list[DecorFormatResponse],
)
async def platform_decor_formats_index(
    decor_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> list[DecorFormatResponse]:
    rows = await list_decor_formats(db, principal=principal, decor_id=decor_id)
    return [_decor_format_response(row) for row in rows]


@router.post(
    "/platform/catalog/decors/{decor_id}/formats",
    response_model=DecorFormatResponse,
    status_code=status.HTTP_201_CREATED,
)
async def platform_decor_formats_create(
    decor_id: uuid.UUID,
    payload: DecorFormatCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> DecorFormatResponse:
    row = await create_decor_format(db, principal=principal, decor_id=decor_id, payload=payload)
    return _decor_format_response(row)


@router.post(
    "/platform/catalog/decors/{decor_id}/formats/{decor_format_id}/activate",
    response_model=DecorFormatResponse,
)
async def platform_decor_formats_activate(
    decor_id: uuid.UUID,
    decor_format_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> DecorFormatResponse:
    row = await set_decor_format_status(
        db,
        principal=principal,
        decor_id=decor_id,
        decor_format_id=decor_format_id,
        to_status=MaterialStatus.ACTIVE,
    )
    return _decor_format_response(row)


@router.post(
    "/platform/catalog/decors/{decor_id}/formats/{decor_format_id}/deactivate",
    response_model=DecorFormatResponse,
)
async def platform_decor_formats_deactivate(
    decor_id: uuid.UUID,
    decor_format_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> DecorFormatResponse:
    row = await set_decor_format_status(
        db,
        principal=principal,
        decor_id=decor_id,
        decor_format_id=decor_format_id,
        to_status=MaterialStatus.INACTIVE,
    )
    return _decor_format_response(row)


@router.get(
    "/workshop/branches/{branch_id}/catalog/decors",
    response_model=BranchCatalogOptionsPage,
)
async def workshop_catalog_options_index(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    type_: DecorType | None = TYPE_QUERY,
    manufacturer_id: uuid.UUID | None = None,
    limit: int | None = LIMIT_QUERY,
    offset: int = OFFSET_QUERY,
) -> BranchCatalogOptionsPage:
    page = await list_branch_catalog_options(
        db,
        principal=principal,
        branch_id=branch_id,
        search=search,
        type_=type_,
        manufacturer_id=manufacturer_id,
        limit=limit,
        offset=offset,
    )
    return BranchCatalogOptionsPage(
        items=[_branch_catalog_option_response(row) for row in page.items],
        total=page.total,
    )


@router.get(
    "/workshop/branches/{branch_id}/catalog/decors/{decor_id}/formats",
    response_model=list[BranchCatalogFormatOption],
)
async def workshop_catalog_formats_index(
    branch_id: uuid.UUID,
    decor_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> list[BranchCatalogFormatOption]:
    """Step two of the attach sheet: this decor's active formats, carried flagged."""

    rows = await list_branch_catalog_formats(
        db,
        principal=principal,
        branch_id=branch_id,
        decor_id=decor_id,
    )
    return [
        BranchCatalogFormatOption(
            decor_format=_decor_format_response(row),
            carried=row.carried,
        )
        for row in rows
    ]


@router.get(
    "/workshop/branches/{branch_id}/catalog/filters",
    response_model=BranchCatalogFiltersResponse,
)
async def workshop_catalog_filters_show(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchCatalogFiltersResponse:
    facets = await list_branch_catalog_facets(db, principal=principal, branch_id=branch_id)
    return BranchCatalogFiltersResponse(
        manufacturers=[
            BranchCatalogManufacturerOption(id=row.id, name=row.name)
            for row in facets.manufacturers
        ],
    )


@router.get(
    "/workshop/branches/{branch_id}/materials",
    response_model=list[BranchMaterialResponse],
)
async def workshop_branch_materials_index(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    type_: DecorType | None = TYPE_QUERY,
    manufacturer_id: uuid.UUID | None = None,
    decor_id: uuid.UUID | None = None,
    status_filter: MaterialStatus | None = STATUS_QUERY,
    limit: int | None = LIMIT_QUERY,
    offset: int = OFFSET_QUERY,
) -> list[BranchMaterialResponse]:
    rows = await list_branch_materials(
        db,
        principal=principal,
        branch_id=branch_id,
        search=search,
        type_=type_,
        manufacturer_id=manufacturer_id,
        decor_id=decor_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return [_branch_material_response(row) for row in rows]


@router.post(
    "/workshop/branches/{branch_id}/materials",
    response_model=BranchMaterialAttachResponse,
    status_code=status.HTTP_201_CREATED,
)
async def workshop_branch_materials_create(
    branch_id: uuid.UUID,
    payload: BranchMaterialAttachRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchMaterialAttachResponse:
    """Carry several platform formats. All-or-nothing."""

    result = await attach_branch_materials(
        db, principal=principal, branch_id=branch_id, payload=payload
    )
    return BranchMaterialAttachResponse(
        created=[_branch_material_response(row) for row in result.created],
        skipped=result.skipped,
    )


@router.patch(
    "/workshop/branches/{branch_id}/materials/{branch_material_id}",
    response_model=BranchMaterialResponse,
)
async def workshop_branch_materials_update(
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    payload: BranchMaterialPatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchMaterialResponse:
    row = await update_branch_material(
        db,
        principal=principal,
        branch_id=branch_id,
        branch_material_id=branch_material_id,
        payload=payload,
    )
    return _branch_material_response(row)


@router.post(
    "/workshop/branches/{branch_id}/materials/{branch_material_id}/activate",
    response_model=BranchMaterialResponse,
)
async def workshop_branch_materials_activate(
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchMaterialResponse:
    row = await set_branch_material_status(
        db,
        principal=principal,
        branch_id=branch_id,
        branch_material_id=branch_material_id,
        to_status=MaterialStatus.ACTIVE,
    )
    return _branch_material_response(row)


@router.post(
    "/workshop/branches/{branch_id}/materials/{branch_material_id}/deactivate",
    response_model=BranchMaterialResponse,
)
async def workshop_branch_materials_deactivate(
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchMaterialResponse:
    row = await set_branch_material_status(
        db,
        principal=principal,
        branch_id=branch_id,
        branch_material_id=branch_material_id,
        to_status=MaterialStatus.INACTIVE,
    )
    return _branch_material_response(row)


def _decor_response(record: DecorRecord) -> DecorResponse:
    return decor_response_from_models(
        record.decor,
        record.manufacturer,
        record.branch_usage_count,
        record.format_count,
    )


def _decor_format_response(record: DecorFormatRecord) -> DecorFormatResponse:
    return decor_format_response_from_models(record.decor_format, record.decor, record.manufacturer)


def _branch_catalog_option_response(row: BranchCatalogOption) -> BranchCatalogDecorOption:
    return BranchCatalogDecorOption(
        decor=decor_response_from_models(row.decor, row.manufacturer),
        carried_format_count=row.carried_format_count,
        available_format_count=row.available_format_count,
    )


def _branch_material_response(row: BranchMaterialRecord) -> BranchMaterialResponse:
    return branch_material_response_from_models(
        row.branch_material, row.decor_format, row.decor, row.manufacturer
    )
