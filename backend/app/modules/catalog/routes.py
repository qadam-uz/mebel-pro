"""Catalog routes for platform dekorlar and workshop branch materials."""

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import AccountReadyPrincipal, Session
from app.models.enums import DekorType, MaterialStatus
from app.modules.catalog.api import (
    BranchCatalogOption,
    BranchMaterialRecord,
    DekorRecord,
    attach_branch_materials,
    branch_material_response_from_models,
    create_dekor,
    create_manufacturer,
    dekor_response_from_models,
    get_dekor,
    get_manufacturer,
    list_branch_catalog_facets,
    list_branch_catalog_options,
    list_branch_materials,
    list_dekorlar,
    list_manufacturers,
    set_branch_material_status,
    set_dekor_status,
    set_manufacturer_status,
    update_branch_material,
    update_dekor,
    update_manufacturer,
)
from app.modules.catalog.schemas import (
    BranchCatalogDekorOption,
    BranchCatalogFiltersResponse,
    BranchCatalogManufacturerOption,
    BranchCatalogOptionsPage,
    BranchMaterialAttachRequest,
    BranchMaterialAttachResponse,
    BranchMaterialFormatKey,
    BranchMaterialPatchRequest,
    BranchMaterialResponse,
    DekorCreateRequest,
    DekorPatchRequest,
    DekorResponse,
    ManufacturerCreateRequest,
    ManufacturerPatchRequest,
    ManufacturerResponse,
)

router = APIRouter(tags=["catalog"])
# The wire name stays `status` even though the dekor column is `holat`: the
# reshape already changes every payload, and renaming the query param too would
# break clients twice for no gain.
STATUS_QUERY = Query(default=None, alias="status")
# Opt-in limit/offset paging (house convention: bare-list response, client infers
# "has more" from a full page). Omitting limit returns the full list unchanged.
LIMIT_QUERY = Query(default=None, ge=1, le=200)
OFFSET_QUERY = Query(default=0, ge=0)
# Repeated query params (?manufacturer_ids=a&manufacturer_ids=b) → multi-select
# filters. Module-level singletons so the defaults aren't Query() calls (ruff B008).
MANUFACTURER_IDS_QUERY = Query(default=None)
TURLAR_QUERY = Query(default=None)


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


@router.get("/platform/catalog/dekorlar", response_model=list[DekorResponse])
async def platform_dekorlar_index(
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    tur: DekorType | None = None,
    turlar: list[DekorType] | None = TURLAR_QUERY,
    manufacturer_id: uuid.UUID | None = None,
    manufacturer_ids: list[uuid.UUID] | None = MANUFACTURER_IDS_QUERY,
    status_filter: MaterialStatus | None = STATUS_QUERY,
    limit: int | None = LIMIT_QUERY,
    offset: int = OFFSET_QUERY,
) -> list[DekorResponse]:
    rows = await list_dekorlar(
        db,
        principal=principal,
        search=search,
        tur=tur,
        turlar=turlar,
        manufacturer_id=manufacturer_id,
        manufacturer_ids=manufacturer_ids,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return [_dekor_response(row) for row in rows]


@router.post(
    "/platform/catalog/dekorlar",
    response_model=DekorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def platform_dekorlar_create(
    payload: DekorCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> DekorResponse:
    row = await create_dekor(db, principal=principal, payload=payload)
    return _dekor_response(row)


@router.get("/platform/catalog/dekorlar/{dekor_id}", response_model=DekorResponse)
async def platform_dekorlar_show(
    dekor_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> DekorResponse:
    row = await get_dekor(db, principal=principal, dekor_id=dekor_id)
    return _dekor_response(row)


@router.patch("/platform/catalog/dekorlar/{dekor_id}", response_model=DekorResponse)
async def platform_dekorlar_update(
    dekor_id: uuid.UUID,
    payload: DekorPatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> DekorResponse:
    row = await update_dekor(db, principal=principal, dekor_id=dekor_id, payload=payload)
    return _dekor_response(row)


@router.post(
    "/platform/catalog/dekorlar/{dekor_id}/activate",
    response_model=DekorResponse,
)
async def platform_dekorlar_activate(
    dekor_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> DekorResponse:
    row = await set_dekor_status(
        db,
        principal=principal,
        dekor_id=dekor_id,
        to_status=MaterialStatus.ACTIVE,
    )
    return _dekor_response(row)


@router.post(
    "/platform/catalog/dekorlar/{dekor_id}/deactivate",
    response_model=DekorResponse,
)
async def platform_dekorlar_deactivate(
    dekor_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> DekorResponse:
    row = await set_dekor_status(
        db,
        principal=principal,
        dekor_id=dekor_id,
        to_status=MaterialStatus.INACTIVE,
    )
    return _dekor_response(row)


@router.get(
    "/workshop/branches/{branch_id}/catalog/dekorlar",
    response_model=BranchCatalogOptionsPage,
)
async def workshop_catalog_options_index(
    branch_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
    search: str | None = None,
    tur: DekorType | None = None,
    manufacturer_id: uuid.UUID | None = None,
    limit: int | None = LIMIT_QUERY,
    offset: int = OFFSET_QUERY,
) -> BranchCatalogOptionsPage:
    page = await list_branch_catalog_options(
        db,
        principal=principal,
        branch_id=branch_id,
        search=search,
        tur=tur,
        manufacturer_id=manufacturer_id,
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
    tur: DekorType | None = None,
    manufacturer_id: uuid.UUID | None = None,
    dekor_id: uuid.UUID | None = None,
    status_filter: MaterialStatus | None = STATUS_QUERY,
    limit: int | None = LIMIT_QUERY,
    offset: int = OFFSET_QUERY,
) -> list[BranchMaterialResponse]:
    rows = await list_branch_materials(
        db,
        principal=principal,
        branch_id=branch_id,
        search=search,
        tur=tur,
        manufacturer_id=manufacturer_id,
        dekor_id=dekor_id,
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
    """Attach several dekorlar, each in one or more o'lchamlar. All-or-nothing."""

    result = await attach_branch_materials(
        db, principal=principal, branch_id=branch_id, payload=payload
    )
    return BranchMaterialAttachResponse(
        created=[_branch_material_response(row) for row in result.created],
        skipped=[
            BranchMaterialFormatKey(
                dekor_id=dekor_id,
                qalinlik_mm=fmt.qalinlik_mm,
                uzunlik_mm=fmt.uzunlik_mm,
                eni_mm=fmt.eni_mm,
                kromka_eni_mm=fmt.kromka_eni_mm,
            )
            for dekor_id, fmt in result.skipped
        ],
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


def _dekor_response(record: DekorRecord) -> DekorResponse:
    return dekor_response_from_models(record.dekor, record.manufacturer, record.branch_usage_count)


def _branch_catalog_option_response(row: BranchCatalogOption) -> BranchCatalogDekorOption:
    return BranchCatalogDekorOption(
        dekor=dekor_response_from_models(row.dekor, row.manufacturer),
        carried_format_count=row.carried_format_count,
    )


def _branch_material_response(row: BranchMaterialRecord) -> BranchMaterialResponse:
    return branch_material_response_from_models(row.branch_material, row.dekor, row.manufacturer)
