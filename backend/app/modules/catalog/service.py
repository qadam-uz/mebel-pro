"""Platform catalog and branch material use cases."""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from fastapi import status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.models.enums import (
    AuthenticatedPrincipalType,
    MaterialKind,
    MaterialStatus,
    PanelMaterialType,
    Permission,
)
from app.modules.access.api import BranchScope, resolve_branch_scope
from app.modules.catalog.contracts import BranchMaterial, Manufacturer, Material
from app.modules.catalog.schemas import (
    BranchMaterialBulkCreateRequest,
    BranchMaterialBulkItem,
    BranchMaterialCreateRequest,
    BranchMaterialPatchRequest,
    ManufacturerCreateRequest,
    ManufacturerPatchRequest,
    MaterialCreateRequest,
    MaterialPatchRequest,
)
from app.modules.platform.api import require_platform_operator
from app.modules.support.api import (
    IMAGE_CONTENT_TYPES,
    attach_file,
    record_action,
    record_status_change,
    replace_attached_file,
)

_TYPE_LABELS: dict[PanelMaterialType, str] = {
    PanelMaterialType.DSP: "LDSP",
    PanelMaterialType.MDF: "MDF",
    PanelMaterialType.PLYWOOD: "Fanera",
    PanelMaterialType.NATURAL_WOOD: "Yog'och",
    PanelMaterialType.OTHER: "Panel",
}
_DIMENSION_SEPARATOR = "\N{MULTIPLICATION SIGN}"


@dataclass(frozen=True)
class MaterialRecord:
    material: Material
    manufacturer: Manufacturer
    branch_usage_count: int = 0


@dataclass(frozen=True)
class BranchMaterialRecord:
    branch_material: BranchMaterial
    material: Material
    manufacturer: Manufacturer


@dataclass(frozen=True)
class BranchMaterialBulkResult:
    created: list[BranchMaterialRecord]
    skipped_material_ids: list[uuid.UUID]


@dataclass(frozen=True)
class BranchCatalogOption:
    material: Material
    manufacturer: Manufacturer


@dataclass(frozen=True)
class BranchCatalogOptionsPage:
    items: list[BranchCatalogOption]
    total: int


@dataclass(frozen=True)
class BranchCatalogFacets:
    manufacturers: list[Manufacturer]
    thicknesses: list[Decimal]


def compose_material_name(
    *,
    kind: MaterialKind,
    manufacturer_name: str,
    type_value: PanelMaterialType | None,
    color: str,
    decor_code: str | None,
    thickness_mm: Decimal,
    panel_length_mm: int | None,
    panel_width_mm: int | None,
    edge_width_mm: int | None,
) -> str:
    """Compose the stored material identity from structured catalog fields."""

    decor = _optional_text(decor_code)
    first_segment_parts: list[str]
    if kind is MaterialKind.PANEL:
        type_label = _TYPE_LABELS[type_value or PanelMaterialType.OTHER]
        first_segment_parts = [type_label, manufacturer_name]
        if decor:
            first_segment_parts.append(decor)
        dimensions = (
            f"{panel_length_mm or 0}{_DIMENSION_SEPARATOR}"
            f"{panel_width_mm or 0}{_DIMENSION_SEPARATOR}{_fmt_mm(thickness_mm)} mm"
        )
    else:
        first_segment_parts = ["Kromka", manufacturer_name]
        if decor:
            first_segment_parts.append(decor)
        dimensions = f"{_fmt_mm(thickness_mm)}{_DIMENSION_SEPARATOR}{edge_width_mm or 0} mm"
    color_text = _required_text(color, "material_color_required")
    return f"{' '.join(first_segment_parts)} · {color_text} · {dimensions}"


async def list_manufacturers(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    search: str | None = None,
    status_filter: MaterialStatus | None = None,
) -> list[Manufacturer]:
    require_platform_operator(principal)
    query = select(Manufacturer).order_by(Manufacturer.name)
    if status_filter is not None:
        query = query.where(Manufacturer.status == status_filter)
    normalized = _optional_text(search)
    if normalized:
        query = query.where(Manufacturer.name.ilike(f"%{normalized}%"))
    return list((await db.scalars(query)).all())


async def create_manufacturer(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: ManufacturerCreateRequest,
) -> Manufacturer:
    require_platform_operator(principal)
    name = _required_text(payload.name, "manufacturer_name_required")
    await _ensure_manufacturer_name_available(db, name=name)
    row = Manufacturer(
        name=name,
        country=_optional_text(payload.country),
        note=_optional_text(payload.note),
        status=MaterialStatus.ACTIVE,
    )
    db.add(row)
    await db.flush()
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="catalog.manufacturer.create",
        entity_type="manufacturer",
        entity_id=row.id,
        summary=f"Created manufacturer {row.name}",
    )
    await db.refresh(row)
    return row


async def get_manufacturer(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    manufacturer_id: uuid.UUID,
) -> Manufacturer:
    require_platform_operator(principal)
    row = await db.get(Manufacturer, manufacturer_id)
    if row is None:
        raise APIError(
            "manufacturer_not_found",
            "Manufacturer not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return row


async def update_manufacturer(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    manufacturer_id: uuid.UUID,
    payload: ManufacturerPatchRequest,
) -> Manufacturer:
    row = await get_manufacturer(db, principal=principal, manufacturer_id=manufacturer_id)
    if "name" in payload.model_fields_set and payload.name is not None:
        name = _required_text(payload.name, "manufacturer_name_required")
        await _ensure_manufacturer_name_available(db, name=name, exclude_id=row.id)
        row.name = name
    if "country" in payload.model_fields_set:
        row.country = _optional_text(payload.country)
    if "note" in payload.model_fields_set:
        row.note = _optional_text(payload.note)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="catalog.manufacturer.update",
        entity_type="manufacturer",
        entity_id=row.id,
        summary=f"Updated manufacturer {row.name}",
    )
    await db.refresh(row)
    return row


async def set_manufacturer_status(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    manufacturer_id: uuid.UUID,
    to_status: MaterialStatus,
) -> Manufacturer:
    row = await get_manufacturer(db, principal=principal, manufacturer_id=manufacturer_id)
    if row.status is to_status:
        return row
    from_status = row.status.value
    row.status = to_status
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action=f"catalog.manufacturer.{to_status.value}",
        entity_type="manufacturer",
        entity_id=row.id,
        summary=f"Set manufacturer {row.name} to {to_status.value}",
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="manufacturer",
        entity_id=row.id,
        from_status=from_status,
        to_status=to_status.value,
        action_log_id=action.id,
    )
    await db.refresh(row)
    return row


async def list_materials(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    search: str | None = None,
    kind: MaterialKind | None = None,
    manufacturer_id: uuid.UUID | None = None,
    manufacturer_ids: list[uuid.UUID] | None = None,
    material_types: list[PanelMaterialType] | None = None,
    status_filter: MaterialStatus | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[MaterialRecord]:
    require_platform_operator(principal)
    # AB-22: aggregate a distinct-branch usage count per material via a LEFT JOIN
    # over BranchMaterial (catalog-owned), so the platform list can show how many
    # branches carry each material without a denormalized column.
    query = (
        select(Material, Manufacturer, func.count(func.distinct(BranchMaterial.branch_id)))
        .join(Manufacturer, Manufacturer.id == Material.manufacturer_id)
        .outerjoin(BranchMaterial, BranchMaterial.material_id == Material.id)
    )
    query = _material_filters(
        query,
        search=search,
        kind=kind,
        manufacturer_id=manufacturer_id,
        manufacturer_ids=manufacturer_ids,
        material_type=None,
        material_types=material_types,
        status_filter=status_filter,
    )
    query = query.group_by(Material.id, Manufacturer.id).order_by(
        Manufacturer.name, Material.name, Material.id
    )
    query = _paginate(query, limit=limit, offset=offset)
    return [
        MaterialRecord(
            material=material,
            manufacturer=manufacturer,
            branch_usage_count=int(usage or 0),
        )
        for material, manufacturer, usage in (await db.execute(query)).all()
    ]


async def create_material(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: MaterialCreateRequest,
) -> MaterialRecord:
    require_platform_operator(principal)
    manufacturer = await _active_manufacturer(db, payload.manufacturer_id)
    _validate_material_shape(
        kind=payload.kind,
        type_value=payload.type,
        thickness_mm=payload.thickness_mm,
        panel_length_mm=payload.panel_length_mm,
        panel_width_mm=payload.panel_width_mm,
        grain_direction=payload.grain_direction,
        edge_width_mm=payload.edge_width_mm,
    )
    color = _required_text(payload.color, "material_color_required")
    row = Material(
        kind=payload.kind,
        manufacturer_id=manufacturer.id,
        type=payload.type,
        name=compose_material_name(
            kind=payload.kind,
            manufacturer_name=manufacturer.name,
            type_value=payload.type,
            color=color,
            decor_code=payload.decor_code,
            thickness_mm=payload.thickness_mm,
            panel_length_mm=payload.panel_length_mm,
            panel_width_mm=payload.panel_width_mm,
            edge_width_mm=payload.edge_width_mm,
        ),
        thickness_mm=payload.thickness_mm,
        color=color,
        decor_code=_optional_text(payload.decor_code),
        panel_length_mm=payload.panel_length_mm,
        panel_width_mm=payload.panel_width_mm,
        grain_direction=payload.grain_direction,
        edge_width_mm=payload.edge_width_mm,
        status=MaterialStatus.ACTIVE,
    )
    db.add(row)
    await db.flush()
    row.image_file_id = await attach_file(
        db,
        principal=principal,
        file_id=payload.image_file_id,
        entity_type="material",
        entity_id=row.id,
        allowed_content_types=IMAGE_CONTENT_TYPES,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="catalog.material.create",
        entity_type="material",
        entity_id=row.id,
        summary=f"Created material {row.name}",
        details={"kind": row.kind.value, "manufacturer_id": str(row.manufacturer_id)},
    )
    await db.refresh(row)
    return MaterialRecord(material=row, manufacturer=manufacturer)


async def get_material(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    material_id: uuid.UUID,
) -> MaterialRecord:
    require_platform_operator(principal)
    record = await _material_record(db, material_id)
    if record is None:
        raise APIError(
            "material_not_found",
            "Material not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return record


async def update_material(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    material_id: uuid.UUID,
    payload: MaterialPatchRequest,
) -> MaterialRecord:
    record = await get_material(db, principal=principal, material_id=material_id)
    row = record.material
    manufacturer = record.manufacturer
    if "manufacturer_id" in payload.model_fields_set and payload.manufacturer_id is not None:
        manufacturer = await _active_manufacturer(db, payload.manufacturer_id)
        row.manufacturer_id = manufacturer.id
    if "thickness_mm" in payload.model_fields_set and payload.thickness_mm is not None:
        row.thickness_mm = payload.thickness_mm
    if "color" in payload.model_fields_set and payload.color is not None:
        row.color = _required_text(payload.color, "material_color_required")
    if "decor_code" in payload.model_fields_set:
        row.decor_code = _optional_text(payload.decor_code)
    if row.kind is MaterialKind.PANEL:
        if "type" in payload.model_fields_set:
            row.type = payload.type
        if "panel_length_mm" in payload.model_fields_set:
            row.panel_length_mm = payload.panel_length_mm
        if "panel_width_mm" in payload.model_fields_set:
            row.panel_width_mm = payload.panel_width_mm
        if "grain_direction" in payload.model_fields_set:
            row.grain_direction = payload.grain_direction
        if "edge_width_mm" in payload.model_fields_set and payload.edge_width_mm is not None:
            raise APIError(
                "invalid_panel_material",
                "Panel material cannot have edge width",
                status_code=400,
            )
        row.edge_width_mm = None
    elif any(
        field in payload.model_fields_set
        for field in ("type", "panel_length_mm", "panel_width_mm", "grain_direction")
    ):
        raise APIError(
            "invalid_edge_material",
            "Edge material cannot have panel fields",
            status_code=400,
        )
    elif "edge_width_mm" in payload.model_fields_set:
        row.edge_width_mm = payload.edge_width_mm
    if "image_file_id" in payload.model_fields_set:
        row.image_file_id = await replace_attached_file(
            db,
            principal=principal,
            file_id=payload.image_file_id,
            current_file_id=row.image_file_id,
            entity_type="material",
            entity_id=row.id,
            allowed_content_types=IMAGE_CONTENT_TYPES,
        )
    _validate_material_shape(
        kind=row.kind,
        type_value=row.type,
        thickness_mm=row.thickness_mm,
        panel_length_mm=row.panel_length_mm,
        panel_width_mm=row.panel_width_mm,
        grain_direction=row.grain_direction,
        edge_width_mm=row.edge_width_mm,
    )
    row.name = compose_material_name(
        kind=row.kind,
        manufacturer_name=manufacturer.name,
        type_value=row.type,
        color=row.color,
        decor_code=row.decor_code,
        thickness_mm=row.thickness_mm,
        panel_length_mm=row.panel_length_mm,
        panel_width_mm=row.panel_width_mm,
        edge_width_mm=row.edge_width_mm,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="catalog.material.update",
        entity_type="material",
        entity_id=row.id,
        summary=f"Updated material {row.name}",
    )
    await db.refresh(row)
    return MaterialRecord(material=row, manufacturer=manufacturer)


async def set_material_status(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    material_id: uuid.UUID,
    to_status: MaterialStatus,
) -> MaterialRecord:
    record = await get_material(db, principal=principal, material_id=material_id)
    row = record.material
    if row.status is to_status:
        return record
    from_status = row.status.value
    row.status = to_status
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action=f"catalog.material.{to_status.value}",
        entity_type="material",
        entity_id=row.id,
        summary=f"Set material {row.name} to {to_status.value}",
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="material",
        entity_id=row.id,
        from_status=from_status,
        to_status=to_status.value,
        action_log_id=action.id,
    )
    await db.refresh(row)
    return record


async def list_branch_catalog_options(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    search: str | None = None,
    kind: MaterialKind | None = None,
    manufacturer_id: uuid.UUID | None = None,
    material_type: PanelMaterialType | None = None,
    thickness_mm: Decimal | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> BranchCatalogOptionsPage:
    """Attachable platform materials for a branch, plus the unpaginated total.

    QAD-159: materials the branch already carries are excluded server-side rather
    than flagged, so paging, the total, and the picker's `Filtrdagi hammasi (N)`
    master checkbox all count the same set.
    """

    _require_workshop_user(principal)
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    attachable = _attachable_materials_query(scope.branch_id)
    filtered = _material_filters(
        attachable,
        search=search,
        kind=kind,
        manufacturer_id=manufacturer_id,
        material_type=material_type,
        thickness_mm=thickness_mm,
        status_filter=None,
    )
    total = await db.scalar(filtered.with_only_columns(func.count(Material.id)))
    query = _paginate(
        filtered.with_only_columns(Material, Manufacturer).order_by(
            Manufacturer.name, Material.name, Material.id
        ),
        limit=limit,
        offset=offset,
    )
    return BranchCatalogOptionsPage(
        items=[
            BranchCatalogOption(material=material, manufacturer=manufacturer)
            for material, manufacturer in (await db.execute(query)).all()
        ],
        total=int(total or 0),
    )


async def list_branch_catalog_facets(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
) -> BranchCatalogFacets:
    """Manufacturer and thickness values present in the branch's attachable set.

    Deliberately unfiltered by the picker's own filters: dropdown options that
    reshuffle as you pick from them are worse than a couple of empty results.
    """

    _require_workshop_user(principal)
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    attachable = _attachable_materials_query(scope.branch_id)
    manufacturers = list(
        (
            await db.scalars(
                attachable.with_only_columns(Manufacturer)
                .distinct()
                .order_by(Manufacturer.name, Manufacturer.id)
            )
        ).all()
    )
    # Trailing-zero scale differs by driver (Postgres gives "2", SQLite
    # "2.0000000000"); normalize so the picker's dropdown labels are stable.
    thicknesses = [
        Decimal(_fmt_mm(value))
        for value in (
            await db.scalars(
                attachable.with_only_columns(Material.thickness_mm)
                .distinct()
                .order_by(Material.thickness_mm)
            )
        ).all()
    ]
    return BranchCatalogFacets(manufacturers=manufacturers, thicknesses=thicknesses)


def _attachable_materials_query(branch_id: uuid.UUID) -> Any:
    """Active platform materials from active manufacturers this branch does not carry."""

    return (
        select(Material.id)
        .join(Manufacturer, Manufacturer.id == Material.manufacturer_id)
        .where(
            Material.status == MaterialStatus.ACTIVE,
            Manufacturer.status == MaterialStatus.ACTIVE,
            ~select(BranchMaterial.id)
            .where(
                BranchMaterial.branch_id == branch_id,
                BranchMaterial.material_id == Material.id,
            )
            .exists(),
        )
    )


async def list_branch_materials(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    search: str | None = None,
    kind: MaterialKind | None = None,
    manufacturer_id: uuid.UUID | None = None,
    material_type: PanelMaterialType | None = None,
    status_filter: MaterialStatus | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[BranchMaterialRecord]:
    _require_workshop_user(principal)
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    query = (
        select(BranchMaterial, Material, Manufacturer)
        .join(Material, Material.id == BranchMaterial.material_id)
        .join(Manufacturer, Manufacturer.id == Material.manufacturer_id)
        .where(BranchMaterial.branch_id == scope.branch_id)
        .order_by(Manufacturer.name, Material.name, Material.id)
    )
    if status_filter is not None:
        query = query.where(BranchMaterial.status == status_filter)
    query = _material_filters(
        query,
        search=search,
        kind=kind,
        manufacturer_id=manufacturer_id,
        material_type=material_type,
        status_filter=None,
    )
    query = _paginate(query, limit=limit, offset=offset)
    return [
        BranchMaterialRecord(branch_material=bm, material=material, manufacturer=manufacturer)
        for bm, material, manufacturer in (await db.execute(query)).all()
    ]


async def add_branch_material(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    payload: BranchMaterialCreateRequest,
) -> BranchMaterialRecord:
    _require_workshop_user(principal)
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    material_record = await _active_material_record(db, payload.material_id)
    _validate_branch_material_numbers(payload.price_tiyin, payload.min_stock)
    if await _branch_material_exists(
        db,
        branch_id=scope.branch_id,
        material_id=payload.material_id,
    ):
        raise APIError(
            "branch_material_exists",
            "Material is already selected for this branch",
            status_code=status.HTTP_409_CONFLICT,
        )
    row = BranchMaterial(
        branch_id=scope.branch_id,
        material_id=payload.material_id,
        price_tiyin=payload.price_tiyin,
        min_stock=payload.min_stock,
        status=MaterialStatus.ACTIVE,
    )
    db.add(row)
    await db.flush()
    from app.modules.inventory.api import ensure_stock_item_for_branch_material

    await ensure_stock_item_for_branch_material(
        db,
        branch_id=scope.branch_id,
        material_id=payload.material_id,
        min_stock=payload.min_stock,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="catalog.branch_material.create",
        entity_type="branch_material",
        entity_id=row.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Added material {material_record.material.name} to branch",
    )
    await db.refresh(row)
    return BranchMaterialRecord(
        branch_material=row,
        material=material_record.material,
        manufacturer=material_record.manufacturer,
    )


async def add_branch_materials_bulk(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    payload: BranchMaterialBulkCreateRequest,
) -> BranchMaterialBulkResult:
    """Attach many platform materials to a branch in one transaction.

    QAD-159: every row is validated before anything is written, so an invalid row
    attaches nothing and the error names the offending material. Materials the
    branch already carries are skipped rather than rejected — the picker excludes
    them, so a duplicate here is a concurrent attach, not user error.
    """

    _require_workshop_user(principal)
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    if not payload.items:
        raise APIError(
            "branch_materials_empty",
            "No materials selected",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    seen: set[uuid.UUID] = set()
    for item in payload.items:
        if item.material_id in seen:
            raise APIError(
                "branch_material_duplicate",
                "The same material appears twice in the batch",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        seen.add(item.material_id)

    # Validate the whole batch first — nothing is added to the session until every
    # row passes, so a rejection leaves the transaction untouched.
    validated: list[tuple[BranchMaterialBulkItem, MaterialRecord]] = []
    for item in payload.items:
        record = await _active_material_record(db, item.material_id)
        _validate_branch_material_numbers_named(
            item.price_tiyin, item.min_stock, material_name=record.material.name
        )
        validated.append((item, record))

    existing_ids = set(
        (
            await db.scalars(
                select(BranchMaterial.material_id).where(
                    BranchMaterial.branch_id == scope.branch_id,
                    BranchMaterial.material_id.in_(seen),
                )
            )
        ).all()
    )

    from app.modules.inventory.api import ensure_stock_item_for_branch_material

    created: list[BranchMaterialRecord] = []
    for item, record in validated:
        if item.material_id in existing_ids:
            continue
        row = BranchMaterial(
            branch_id=scope.branch_id,
            material_id=item.material_id,
            price_tiyin=item.price_tiyin,
            min_stock=item.min_stock,
            status=MaterialStatus.ACTIVE,
        )
        db.add(row)
        await db.flush()
        await ensure_stock_item_for_branch_material(
            db,
            branch_id=scope.branch_id,
            material_id=item.material_id,
            min_stock=item.min_stock,
        )
        created.append(
            BranchMaterialRecord(
                branch_material=row,
                material=record.material,
                manufacturer=record.manufacturer,
            )
        )
    if created:
        await record_action(
            db,
            actor=actor_from_principal(principal),
            action="catalog.branch_material.bulk_create",
            entity_type="branch",
            entity_id=scope.branch_id,
            workshop_id=scope.workshop_id,
            branch_id=scope.branch_id,
            summary=f"Added {len(created)} materials to branch",
            details={"material_ids": [str(row.branch_material.material_id) for row in created]},
        )
    return BranchMaterialBulkResult(
        created=created,
        skipped_material_ids=[
            item.material_id for item, _ in validated if item.material_id in existing_ids
        ],
    )


async def update_branch_material(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    payload: BranchMaterialPatchRequest,
) -> BranchMaterialRecord:
    _require_workshop_user(principal)
    record, scope = await _branch_material_record_for_write(
        db,
        principal=principal,
        branch_id=branch_id,
        branch_material_id=branch_material_id,
    )
    row = record.branch_material
    if payload.price_tiyin is not None:
        _validate_nonnegative(payload.price_tiyin, "invalid_price")
        row.price_tiyin = payload.price_tiyin
    if payload.min_stock is not None:
        _validate_nonnegative(payload.min_stock, "invalid_min_stock")
        row.min_stock = payload.min_stock
        from app.modules.inventory.api import sync_stock_item_min_stock

        await sync_stock_item_min_stock(
            db,
            branch_id=scope.branch_id,
            material_id=row.material_id,
            min_stock=row.min_stock,
        )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="catalog.branch_material.update",
        entity_type="branch_material",
        entity_id=row.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Updated branch material {record.material.name}",
    )
    await db.refresh(row)
    return record


async def set_branch_material_status(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
    to_status: MaterialStatus,
) -> BranchMaterialRecord:
    _require_workshop_user(principal)
    record, scope = await _branch_material_record_for_write(
        db,
        principal=principal,
        branch_id=branch_id,
        branch_material_id=branch_material_id,
    )
    row = record.branch_material
    if row.status is to_status:
        return record
    from_status = row.status.value
    row.status = to_status
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action=f"catalog.branch_material.{to_status.value}",
        entity_type="branch_material",
        entity_id=row.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Set branch material {record.material.name} to {to_status.value}",
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="branch_material",
        entity_id=row.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        from_status=from_status,
        to_status=to_status.value,
        action_log_id=action.id,
    )
    await db.refresh(row)
    return record


async def _branch_material_record_for_write(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    branch_material_id: uuid.UUID,
) -> tuple[BranchMaterialRecord, BranchScope]:
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    result = await db.execute(
        select(BranchMaterial, Material, Manufacturer)
        .join(Material, Material.id == BranchMaterial.material_id)
        .join(Manufacturer, Manufacturer.id == Material.manufacturer_id)
        .where(BranchMaterial.id == branch_material_id, BranchMaterial.branch_id == scope.branch_id)
    )
    row = result.one_or_none()
    if row is None:
        raise APIError(
            "branch_material_not_found",
            "Branch material not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    bm, material, manufacturer = row
    return BranchMaterialRecord(bm, material, manufacturer), scope


async def _material_record(db: AsyncSession, material_id: uuid.UUID) -> MaterialRecord | None:
    row = (
        await db.execute(
            select(Material, Manufacturer)
            .join(Manufacturer, Manufacturer.id == Material.manufacturer_id)
            .where(Material.id == material_id)
        )
    ).one_or_none()
    if row is None:
        return None
    material, manufacturer = row
    return MaterialRecord(material=material, manufacturer=manufacturer)


async def _active_material_record(db: AsyncSession, material_id: uuid.UUID) -> MaterialRecord:
    record = await _material_record(db, material_id)
    if (
        record is None
        or record.material.status is not MaterialStatus.ACTIVE
        or record.manufacturer.status is not MaterialStatus.ACTIVE
    ):
        raise APIError(
            "material_not_found",
            "Material not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return record


async def _active_manufacturer(db: AsyncSession, manufacturer_id: uuid.UUID) -> Manufacturer:
    row = await db.get(Manufacturer, manufacturer_id)
    if row is None or row.status is not MaterialStatus.ACTIVE:
        raise APIError(
            "manufacturer_not_found",
            "Manufacturer not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return row


async def _ensure_manufacturer_name_available(
    db: AsyncSession,
    *,
    name: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    query = select(Manufacturer.id).where(func.lower(Manufacturer.name) == name.lower())
    if exclude_id is not None:
        query = query.where(Manufacturer.id != exclude_id)
    if await db.scalar(query) is not None:
        raise APIError(
            "manufacturer_name_exists",
            "Manufacturer name already exists",
            status_code=status.HTTP_409_CONFLICT,
        )


async def _branch_material_exists(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    material_id: uuid.UUID,
) -> bool:
    existing = await db.scalar(
        select(BranchMaterial.id).where(
            BranchMaterial.branch_id == branch_id,
            BranchMaterial.material_id == material_id,
        )
    )
    return existing is not None


# Catalog list endpoints paginate with the house limit/offset convention
# (sales, inventory, audit): the caller opts in by passing a limit, the response
# stays a bare list, and the client infers "has more" from a full page. A None
# limit means unbounded — preserving the pre-pagination behavior for callers (and
# tests) that don't ask for a page. Ordering carries a Material.id tiebreaker so
# offset paging is deterministic across requests.
MATERIALS_MAX_LIMIT = 200


def _bounded_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    return max(1, min(limit, MATERIALS_MAX_LIMIT))


def _paginate(query: Any, *, limit: int | None, offset: int) -> Any:
    bounded = _bounded_limit(limit)
    if bounded is None:
        return query
    return query.limit(bounded).offset(max(0, offset))


def _material_filters(
    query: Any,
    *,
    search: str | None,
    kind: MaterialKind | None,
    manufacturer_id: uuid.UUID | None,
    material_type: PanelMaterialType | None,
    status_filter: MaterialStatus | None,
    manufacturer_ids: list[uuid.UUID] | None = None,
    material_types: list[PanelMaterialType] | None = None,
    thickness_mm: Decimal | None = None,
) -> Any:
    if kind is not None:
        query = query.where(Material.kind == kind)
    if thickness_mm is not None:
        query = query.where(Material.thickness_mm == thickness_mm)
    if manufacturer_id is not None:
        query = query.where(Material.manufacturer_id == manufacturer_id)
    if manufacturer_ids:
        query = query.where(Material.manufacturer_id.in_(manufacturer_ids))
    if material_type is not None:
        query = query.where(Material.type == material_type)
    if material_types:
        query = query.where(Material.type.in_(material_types))
    if status_filter is not None:
        query = query.where(Material.status == status_filter)
    normalized = _optional_text(search)
    if normalized:
        pattern = f"%{normalized}%"
        query = query.where(
            or_(
                Material.name.ilike(pattern),
                Material.color.ilike(pattern),
                Material.decor_code.ilike(pattern),
                Manufacturer.name.ilike(pattern),
            )
        )
    return query


def _validate_material_shape(
    *,
    kind: MaterialKind,
    type_value: object,
    thickness_mm: Decimal,
    panel_length_mm: int | None,
    panel_width_mm: int | None,
    grain_direction: bool | None,
    edge_width_mm: int | None,
) -> None:
    if thickness_mm <= 0:
        raise APIError("invalid_thickness", "Thickness must be positive", status_code=400)
    if kind is MaterialKind.PANEL:
        if edge_width_mm is not None:
            raise APIError(
                "invalid_panel_material",
                "Panel material cannot have edge width",
                status_code=400,
            )
        if type_value is None or panel_length_mm is None or panel_width_mm is None:
            raise APIError(
                "invalid_panel_material",
                "Panel material fields are required",
                status_code=400,
            )
        if panel_length_mm <= 0 or panel_width_mm <= 0 or panel_length_mm < panel_width_mm:
            raise APIError("invalid_panel_size", "Panel size is invalid", status_code=400)
        if grain_direction is None:
            raise APIError("invalid_grain", "Grain direction is required", status_code=400)
        return
    if type_value is not None or panel_length_mm is not None or panel_width_mm is not None:
        raise APIError(
            "invalid_edge_material",
            "Edge material cannot have panel fields",
            status_code=400,
        )
    if grain_direction is not None:
        raise APIError("invalid_edge_material", "Edge material cannot have grain", status_code=400)
    if edge_width_mm is None:
        raise APIError("invalid_edge_width", "Edge width is required", status_code=400)
    if edge_width_mm <= 0:
        raise APIError("invalid_edge_width", "Edge width must be positive", status_code=400)


def _validate_branch_material_numbers(price_tiyin: int, min_stock: int) -> None:
    _validate_nonnegative(price_tiyin, "invalid_price")
    _validate_nonnegative(min_stock, "invalid_min_stock")


def _validate_branch_material_numbers_named(
    price_tiyin: int, min_stock: int, *, material_name: str
) -> None:
    """Bulk-attach validation. The batch is all-or-nothing, so the message has to
    name the row that killed it — an anonymous `invalid_price` over 40 materials is
    useless to the person who has to fix it."""

    if price_tiyin <= 0:
        raise APIError(
            "invalid_price",
            f"«{material_name}» uchun narx kiritilmagan",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if min_stock < 0:
        raise APIError(
            "invalid_min_stock",
            f"«{material_name}» uchun chegara noto'g'ri",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def _validate_nonnegative(value: int, code: str) -> None:
    if value < 0:
        raise APIError(code, "Value must be non-negative", status_code=status.HTTP_400_BAD_REQUEST)


def _require_workshop_user(principal: AuthenticatedPrincipal) -> None:
    if principal.principal_type is not AuthenticatedPrincipalType.WORKSHOP_USER:
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)


def _required_text(value: str, code: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise APIError(code, "Required field is missing", status_code=status.HTTP_400_BAD_REQUEST)
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized or None


def _fmt_mm(value: Decimal) -> str:
    return format(value.normalize(), "f")
