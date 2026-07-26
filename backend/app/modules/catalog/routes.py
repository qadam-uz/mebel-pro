"""Catalog routes for platform and workshop branch selection."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Query, status

from app.api.deps import AccountReadyPrincipal, Session
from app.models.enums import MaterialKind, MaterialStatus, PanelMaterialType
from app.modules.catalog.api import (
    BranchCatalogOption,
    BranchMaterialRecord,
    MaterialRecord,
    add_branch_material,
    add_branch_materials_bulk,
    create_manufacturer,
    create_material,
    get_manufacturer,
    get_material,
    list_branch_catalog_facets,
    list_branch_catalog_options,
    list_branch_materials,
    list_manufacturers,
    list_materials,
    material_response_from_models,
    set_branch_material_status,
    set_manufacturer_status,
    set_material_status,
    update_branch_material,
    update_manufacturer,
    update_material,
)
from app.modules.catalog.schemas import (
    BranchCatalogFiltersResponse,
    BranchCatalogManufacturerOption,
    BranchCatalogMaterialOption,
    BranchCatalogOptionsPage,
    BranchMaterialBulkCreateRequest,
    BranchMaterialBulkResponse,
    BranchMaterialCreateRequest,
    BranchMaterialPatchRequest,
    BranchMaterialResponse,
    ManufacturerCreateRequest,
    ManufacturerPatchRequest,
    ManufacturerResponse,
    MaterialCreateRequest,
    MaterialPatchRequest,
    MaterialResponse,
)

router = APIRouter(tags=["catalog"])
MATERIAL_STATUS_QUERY = Query(default=None, alias="status")
# Opt-in limit/offset paging (house convention: bare-list response, client infers
# "has more" from a full page). Omitting limit returns the full list unchanged.
LIMIT_QUERY = Query(default=None, ge=1, le=200)
OFFSET_QUERY = Query(default=0, ge=0)
# Repeated query params (?manufacturer_ids=a&manufacturer_ids=b) → multi-select
# filters. Module-level singletons so the defaults aren't Query() calls (ruff B008).
MANUFACTURER_IDS_QUERY = Query(default=None)
MATERIAL_TYPES_QUERY = Query(default=None)


@router.get("/platform/catalog/manufacturers", response_model=list[ManufacturerResponse])
async def platform_manufacturers_index(
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    status_filter: MaterialStatus | None = MATERIAL_STATUS_QUERY,
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


@router.get("/platform/catalog/materials", response_model=list[MaterialResponse])
async def platform_materials_index(
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    kind: MaterialKind | None = None,
    manufacturer_id: uuid.UUID | None = None,
    manufacturer_ids: list[uuid.UUID] | None = MANUFACTURER_IDS_QUERY,
    material_types: list[PanelMaterialType] | None = MATERIAL_TYPES_QUERY,
    status_filter: MaterialStatus | None = MATERIAL_STATUS_QUERY,
    limit: int | None = LIMIT_QUERY,
    offset: int = OFFSET_QUERY,
) -> list[MaterialResponse]:
    rows = await list_materials(
        db,
        principal=principal,
        search=search,
        kind=kind,
        manufacturer_id=manufacturer_id,
        manufacturer_ids=manufacturer_ids,
        material_types=material_types,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return [_material_response(row) for row in rows]


@router.post(
    "/platform/catalog/materials",
    response_model=MaterialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def platform_materials_create(
    payload: MaterialCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> MaterialResponse:
    row = await create_material(db, principal=principal, payload=payload)
    return _material_response(row)


@router.get("/platform/catalog/materials/{material_id}", response_model=MaterialResponse)
async def platform_materials_show(
    material_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> MaterialResponse:
    row = await get_material(db, principal=principal, material_id=material_id)
    return _material_response(row)


@router.patch("/platform/catalog/materials/{material_id}", response_model=MaterialResponse)
async def platform_materials_update(
    material_id: uuid.UUID,
    payload: MaterialPatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> MaterialResponse:
    row = await update_material(db, principal=principal, material_id=material_id, payload=payload)
    return _material_response(row)


@router.post(
    "/platform/catalog/materials/{material_id}/activate",
    response_model=MaterialResponse,
)
async def platform_materials_activate(
    material_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> MaterialResponse:
    row = await set_material_status(
        db,
        principal=principal,
        material_id=material_id,
        to_status=MaterialStatus.ACTIVE,
    )
    return _material_response(row)


@router.post(
    "/platform/catalog/materials/{material_id}/deactivate",
    response_model=MaterialResponse,
)
async def platform_materials_deactivate(
    material_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> MaterialResponse:
    row = await set_material_status(
        db,
        principal=principal,
        material_id=material_id,
        to_status=MaterialStatus.INACTIVE,
    )
    return _material_response(row)


@router.get(
    "/workshop/branches/{branch_id}/catalog/materials",
    response_model=BranchCatalogOptionsPage,
)
async def workshop_catalog_options_index(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    kind: MaterialKind | None = None,
    manufacturer_id: uuid.UUID | None = None,
    material_type: PanelMaterialType | None = None,
    thickness_mm: Decimal | None = None,
    limit: int | None = LIMIT_QUERY,
    offset: int = OFFSET_QUERY,
) -> BranchCatalogOptionsPage:
    page = await list_branch_catalog_options(
        db,
        principal=principal,
        branch_id=branch_id,
        search=search,
        kind=kind,
        manufacturer_id=manufacturer_id,
        material_type=material_type,
        thickness_mm=thickness_mm,
        limit=limit,
        offset=offset,
    )
    return BranchCatalogOptionsPage(
        items=[_branch_catalog_option_response(row) for row in page.items],
        total=page.total,
    )


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
        thicknesses=facets.thicknesses,
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
    kind: MaterialKind | None = None,
    manufacturer_id: uuid.UUID | None = None,
    material_type: PanelMaterialType | None = None,
    status_filter: MaterialStatus | None = MATERIAL_STATUS_QUERY,
    limit: int | None = LIMIT_QUERY,
    offset: int = OFFSET_QUERY,
) -> list[BranchMaterialResponse]:
    rows = await list_branch_materials(
        db,
        principal=principal,
        branch_id=branch_id,
        search=search,
        kind=kind,
        manufacturer_id=manufacturer_id,
        material_type=material_type,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return [_branch_material_response(row) for row in rows]


@router.post(
    "/workshop/branches/{branch_id}/materials",
    response_model=BranchMaterialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def workshop_branch_materials_create(
    branch_id: uuid.UUID,
    payload: BranchMaterialCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchMaterialResponse:
    row = await add_branch_material(db, principal=principal, branch_id=branch_id, payload=payload)
    return _branch_material_response(row)


@router.post(
    "/workshop/branches/{branch_id}/materials/bulk",
    response_model=BranchMaterialBulkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def workshop_branch_materials_bulk_create(
    branch_id: uuid.UUID,
    payload: BranchMaterialBulkCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> BranchMaterialBulkResponse:
    result = await add_branch_materials_bulk(
        db, principal=principal, branch_id=branch_id, payload=payload
    )
    return BranchMaterialBulkResponse(
        created=[_branch_material_response(row) for row in result.created],
        skipped_material_ids=result.skipped_material_ids,
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


def _material_response(record: MaterialRecord) -> MaterialResponse:
    return material_response_from_models(
        record.material, record.manufacturer, record.branch_usage_count
    )


def _branch_catalog_option_response(row: BranchCatalogOption) -> BranchCatalogMaterialOption:
    return BranchCatalogMaterialOption(
        material=material_response_from_models(row.material, row.manufacturer),
    )


def _branch_material_response(row: BranchMaterialRecord) -> BranchMaterialResponse:
    branch_material = row.branch_material
    return BranchMaterialResponse(
        id=branch_material.id,
        branch_id=branch_material.branch_id,
        material_id=branch_material.material_id,
        material=material_response_from_models(row.material, row.manufacturer),
        price_tiyin=branch_material.price_tiyin,
        min_stock=branch_material.min_stock,
        status=branch_material.status,
        created_at=branch_material.created_at,
        updated_at=branch_material.updated_at,
    )
