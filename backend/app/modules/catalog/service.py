"""Platform dekor catalog and branch material use cases.

The split this module enforces: the platform owns *identity* (`dekorlar`), a
branch owns *format* (`branch_materials`). Nothing on the platform surface may
accept a thickness, a size or a price, and nothing on the branch surface may
edit identity.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.material_label import edge_label, material_label
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.core.search_fold import fold
from app.models.enums import (
    AuthenticatedPrincipalType,
    DekorType,
    MaterialStatus,
    Permission,
)
from app.modules.access.api import BranchScope, resolve_branch_scope
from app.modules.catalog.contracts import BranchMaterial, Dekor, Manufacturer, is_tape
from app.modules.catalog.schemas import (
    BranchMaterialAttachRequest,
    BranchMaterialPatchRequest,
    DekorCreateRequest,
    DekorPatchRequest,
    ManufacturerCreateRequest,
    ManufacturerPatchRequest,
)
from app.modules.platform.api import require_platform_operator
from app.modules.support.api import (
    IMAGE_CONTENT_TYPES,
    attach_file,
    record_action,
    record_status_change,
    replace_attached_file,
)

# The `files` table stores this literal for catalog images and the reshape
# migration re-pointed those rows' `entity_id` at the new dekor id *without*
# rewriting the string. Changing it here would 403 every historical photo, so
# the wire value stays "material" while the Python vocabulary moved on.
_IMAGE_ENTITY_TYPE = "material"


@dataclass(frozen=True)
class DekorRecord:
    dekor: Dekor
    manufacturer: Manufacturer
    branch_usage_count: int = 0


@dataclass(frozen=True)
class BranchMaterialRecord:
    branch_material: BranchMaterial
    dekor: Dekor
    manufacturer: Manufacturer


@dataclass(frozen=True)
class BranchMaterialFormat:
    """A validated, normalized format tuple — the branch-scoped identity of a row.

    Normalized means: thickness at a stable scale, and `uzunlik_mm >= eni_mm` for
    panel-shaped dekorlar, so 2750x1830 and 1830x2750 are the same format rather
    than two rows that cut identically.
    """

    qalinlik_mm: Decimal
    uzunlik_mm: int | None
    eni_mm: int | None
    kromka_eni_mm: int | None


@dataclass(frozen=True)
class BranchMaterialAttachResult:
    created: list[BranchMaterialRecord]
    skipped: list[BranchMaterialFormat]


@dataclass(frozen=True)
class BranchCatalogOption:
    dekor: Dekor
    manufacturer: Manufacturer
    carried_format_count: int = 0


@dataclass(frozen=True)
class BranchCatalogOptionsPage:
    items: list[BranchCatalogOption]
    total: int


@dataclass(frozen=True)
class BranchCatalogFacets:
    manufacturers: list[Manufacturer]


# --------------------------------------------------------------------------- #
# Labels and snapshots
# --------------------------------------------------------------------------- #


def dekor_snapshot(dekor: Dekor, manufacturer: Manufacturer) -> dict[str, Any]:
    """Identity half of a material snapshot — no format, so no dimensions print."""

    return {
        "manufacturer_name": manufacturer.name,
        "tur": dekor.tur.value,
        "kod": dekor.kod,
        "nomi": dekor.nomi,
        "tolali": dekor.tolali,
    }


def branch_material_snapshot(
    branch_material: BranchMaterial,
    dekor: Dekor,
    manufacturer: Manufacturer,
) -> dict[str, Any]:
    """The canonical snapshot shape for a branch material.

    One writer for the key vocabulary that `app/core/material_label.py` reads and
    that cutting/sales freeze into history. Thickness goes out as a *string* so
    the label formatter renders it (it ignores non-str thickness), sizes as ints.
    """

    return {
        **dekor_snapshot(dekor, manufacturer),
        "qalinlik_mm": _fmt_mm(branch_material.qalinlik_mm),
        "uzunlik_mm": branch_material.uzunlik_mm,
        "eni_mm": branch_material.eni_mm,
        "kromka_eni_mm": branch_material.kromka_eni_mm,
    }


def dekor_label(dekor: Dekor, manufacturer: Manufacturer) -> str:
    """Display string for a dekor, e.g. `LDSP Egger H1334 · Sonoma eman`."""

    snapshot = dekor_snapshot(dekor, manufacturer)
    if is_tape(dekor.tur):
        return edge_label(snapshot, dekor.id)
    return material_label(snapshot, dekor.id)


def branch_material_label(
    branch_material: BranchMaterial,
    dekor: Dekor,
    manufacturer: Manufacturer,
) -> str:
    """Display string for a carried format, dimensions included."""

    snapshot = branch_material_snapshot(branch_material, dekor, manufacturer)
    if is_tape(dekor.tur):
        return edge_label(snapshot, branch_material.id)
    return material_label(snapshot, branch_material.id)


# --------------------------------------------------------------------------- #
# Manufacturers
# --------------------------------------------------------------------------- #


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
    renamed = False
    if "name" in payload.model_fields_set and payload.name is not None:
        name = _required_text(payload.name, "manufacturer_name_required")
        renamed = name != row.name
        await _ensure_manufacturer_name_available(db, name=name, exclude_id=row.id)
        row.name = name
    if "country" in payload.model_fields_set:
        row.country = _optional_text(payload.country)
    if "note" in payload.model_fields_set:
        row.note = _optional_text(payload.note)
    if renamed:
        # search_key embeds the manufacturer name, so a rename silently rots
        # search for every dekor of this maker unless they are recomputed here.
        await _recompute_search_keys_for_manufacturer(db, row)
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


# --------------------------------------------------------------------------- #
# Dekorlar (platform)
# --------------------------------------------------------------------------- #


async def list_dekorlar(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    search: str | None = None,
    tur: DekorType | None = None,
    turlar: list[DekorType] | None = None,
    manufacturer_id: uuid.UUID | None = None,
    manufacturer_ids: list[uuid.UUID] | None = None,
    status_filter: MaterialStatus | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[DekorRecord]:
    require_platform_operator(principal)
    # AB-22: aggregate a distinct-branch usage count per dekor via a LEFT JOIN over
    # BranchMaterial, so the platform list can show how many branches carry each
    # dekor without a denormalized column. Counting distinct *branches* (not rows)
    # keeps the number stable as a branch adds formats.
    query = (
        select(Dekor, Manufacturer, func.count(func.distinct(BranchMaterial.branch_id)))
        .join(Manufacturer, Manufacturer.id == Dekor.manufacturer_id)
        .outerjoin(BranchMaterial, BranchMaterial.dekor_id == Dekor.id)
    )
    query = _dekor_filters(
        query,
        search=search,
        tur=tur,
        turlar=turlar,
        manufacturer_id=manufacturer_id,
        manufacturer_ids=manufacturer_ids,
        status_filter=status_filter,
    )
    query = query.group_by(Dekor.id, Manufacturer.id).order_by(
        Manufacturer.name, Dekor.nomi, Dekor.id
    )
    query = _paginate(query, limit=limit, offset=offset)
    return [
        DekorRecord(
            dekor=dekor,
            manufacturer=manufacturer,
            branch_usage_count=int(usage or 0),
        )
        for dekor, manufacturer, usage in (await db.execute(query)).all()
    ]


async def create_dekor(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: DekorCreateRequest,
) -> DekorRecord:
    require_platform_operator(principal)
    manufacturer = await _active_manufacturer(db, payload.manufacturer_id)
    nomi = _required_text(payload.nomi, "dekor_nomi_required")
    kod = _optional_text(payload.kod)
    await _ensure_dekor_identity_available(
        db,
        manufacturer_id=manufacturer.id,
        tur=payload.tur,
        kod=kod,
        nomi=nomi,
    )
    row = Dekor(
        manufacturer_id=manufacturer.id,
        tur=payload.tur,
        kod=kod,
        nomi=nomi,
        tolali=payload.tolali,
        holat=MaterialStatus.ACTIVE,
        search_key=_search_key(nomi=nomi, kod=kod, manufacturer_name=manufacturer.name),
    )
    db.add(row)
    await db.flush()
    row.image_file_id = await attach_file(
        db,
        principal=principal,
        file_id=payload.image_file_id,
        entity_type=_IMAGE_ENTITY_TYPE,
        entity_id=row.id,
        allowed_content_types=IMAGE_CONTENT_TYPES,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="catalog.dekor.create",
        entity_type="dekor",
        entity_id=row.id,
        summary=f"Created dekor {dekor_label(row, manufacturer)}",
        details={"tur": row.tur.value, "manufacturer_id": str(row.manufacturer_id)},
    )
    await db.refresh(row)
    return DekorRecord(dekor=row, manufacturer=manufacturer)


async def get_dekor(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    dekor_id: uuid.UUID,
) -> DekorRecord:
    require_platform_operator(principal)
    record = await _dekor_record(db, dekor_id)
    if record is None:
        raise APIError(
            "dekor_not_found",
            "Dekor not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return record


async def update_dekor(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    dekor_id: uuid.UUID,
    payload: DekorPatchRequest,
) -> DekorRecord:
    record = await get_dekor(db, principal=principal, dekor_id=dekor_id)
    row = record.dekor
    manufacturer = record.manufacturer
    if "manufacturer_id" in payload.model_fields_set and payload.manufacturer_id is not None:
        manufacturer = await _active_manufacturer(db, payload.manufacturer_id)
        row.manufacturer_id = manufacturer.id
    if "tur" in payload.model_fields_set and payload.tur is not None:
        row.tur = payload.tur
    if "nomi" in payload.model_fields_set and payload.nomi is not None:
        row.nomi = _required_text(payload.nomi, "dekor_nomi_required")
    if "kod" in payload.model_fields_set:
        row.kod = _optional_text(payload.kod)
    if "tolali" in payload.model_fields_set and payload.tolali is not None:
        row.tolali = payload.tolali
    if "image_file_id" in payload.model_fields_set:
        row.image_file_id = await replace_attached_file(
            db,
            principal=principal,
            file_id=payload.image_file_id,
            current_file_id=row.image_file_id,
            entity_type=_IMAGE_ENTITY_TYPE,
            entity_id=row.id,
            allowed_content_types=IMAGE_CONTENT_TYPES,
        )
    await _ensure_dekor_identity_available(
        db,
        manufacturer_id=row.manufacturer_id,
        tur=row.tur,
        kod=row.kod,
        nomi=row.nomi,
        exclude_id=row.id,
    )
    # Recomputed unconditionally: every input to the key (nomi, kod, maker) is
    # patchable, and an unchanged write costs one fold() call.
    row.search_key = _search_key(nomi=row.nomi, kod=row.kod, manufacturer_name=manufacturer.name)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="catalog.dekor.update",
        entity_type="dekor",
        entity_id=row.id,
        summary=f"Updated dekor {dekor_label(row, manufacturer)}",
    )
    await db.refresh(row)
    return DekorRecord(dekor=row, manufacturer=manufacturer)


async def set_dekor_status(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    dekor_id: uuid.UUID,
    to_status: MaterialStatus,
) -> DekorRecord:
    record = await get_dekor(db, principal=principal, dekor_id=dekor_id)
    row = record.dekor
    if row.holat is to_status:
        return record
    from_status = row.holat.value
    row.holat = to_status
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action=f"catalog.dekor.{to_status.value}",
        entity_type="dekor",
        entity_id=row.id,
        summary=f"Set dekor {dekor_label(row, record.manufacturer)} to {to_status.value}",
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="dekor",
        entity_id=row.id,
        from_status=from_status,
        to_status=to_status.value,
        action_log_id=action.id,
    )
    await db.refresh(row)
    return record


# --------------------------------------------------------------------------- #
# Branch attach picker
# --------------------------------------------------------------------------- #


async def list_branch_catalog_options(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    search: str | None = None,
    tur: DekorType | None = None,
    manufacturer_id: uuid.UUID | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> BranchCatalogOptionsPage:
    """Attachable dekorlar for a branch, plus the unpaginated total.

    Unlike the pre-reshape picker this hides nothing: a branch legitimately
    carries the same dekor at several thicknesses, so "already carried" is no
    longer a reason to drop a row. Each option reports how many formats the
    branch already has instead.
    """

    _require_workshop_user(principal)
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    attachable = _attachable_dekorlar_query()
    filtered = _dekor_filters(
        attachable,
        search=search,
        tur=tur,
        manufacturer_id=manufacturer_id,
        status_filter=None,
    )
    total = await db.scalar(filtered.with_only_columns(func.count(Dekor.id)))
    carried_count = (
        select(func.count(BranchMaterial.id))
        .where(
            BranchMaterial.branch_id == scope.branch_id,
            BranchMaterial.dekor_id == Dekor.id,
        )
        .scalar_subquery()
    )
    query = _paginate(
        filtered.with_only_columns(Dekor, Manufacturer, carried_count).order_by(
            Manufacturer.name, Dekor.nomi, Dekor.id
        ),
        limit=limit,
        offset=offset,
    )
    return BranchCatalogOptionsPage(
        items=[
            BranchCatalogOption(
                dekor=dekor,
                manufacturer=manufacturer,
                carried_format_count=int(carried or 0),
            )
            for dekor, manufacturer, carried in (await db.execute(query)).all()
        ],
        total=int(total or 0),
    )


async def list_branch_catalog_facets(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
) -> BranchCatalogFacets:
    """Manufacturer values present in the attachable set.

    Deliberately unfiltered by the picker's own filters: dropdown options that
    reshuffle as you pick from them are worse than a couple of empty results.
    """

    _require_workshop_user(principal)
    await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    attachable = _attachable_dekorlar_query()
    manufacturers = list(
        (
            await db.scalars(
                attachable.with_only_columns(Manufacturer)
                .distinct()
                .order_by(Manufacturer.name, Manufacturer.id)
            )
        ).all()
    )
    return BranchCatalogFacets(manufacturers=manufacturers)


def _attachable_dekorlar_query() -> Any:
    """Active dekorlar from active manufacturers."""

    return (
        select(Dekor.id)
        .join(Manufacturer, Manufacturer.id == Dekor.manufacturer_id)
        .where(
            Dekor.holat == MaterialStatus.ACTIVE,
            Manufacturer.status == MaterialStatus.ACTIVE,
        )
    )


# --------------------------------------------------------------------------- #
# Branch materials
# --------------------------------------------------------------------------- #


async def list_branch_materials(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    search: str | None = None,
    tur: DekorType | None = None,
    manufacturer_id: uuid.UUID | None = None,
    dekor_id: uuid.UUID | None = None,
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
        select(BranchMaterial, Dekor, Manufacturer)
        .join(Dekor, Dekor.id == BranchMaterial.dekor_id)
        .join(Manufacturer, Manufacturer.id == Dekor.manufacturer_id)
        .where(BranchMaterial.branch_id == scope.branch_id)
        .order_by(
            Manufacturer.name,
            Dekor.nomi,
            BranchMaterial.qalinlik_mm,
            BranchMaterial.id,
        )
    )
    if status_filter is not None:
        query = query.where(BranchMaterial.status == status_filter)
    if dekor_id is not None:
        query = query.where(BranchMaterial.dekor_id == dekor_id)
    query = _dekor_filters(
        query,
        search=search,
        tur=tur,
        manufacturer_id=manufacturer_id,
        status_filter=None,
    )
    query = _paginate(query, limit=limit, offset=offset)
    return [
        BranchMaterialRecord(branch_material=bm, dekor=dekor, manufacturer=manufacturer)
        for bm, dekor, manufacturer in (await db.execute(query)).all()
    ]


async def attach_branch_materials(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    payload: BranchMaterialAttachRequest,
) -> BranchMaterialAttachResult:
    """Attach one dekor in one or more formats, in a single transaction.

    Every row is validated before anything is written, so an invalid format
    attaches nothing and the error names the dekor. Formats the branch already
    carries are skipped rather than rejected — the picker shows what is carried,
    so a duplicate here is a concurrent attach, not user error.
    """

    _require_workshop_user(principal)
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    if not payload.formats:
        raise APIError(
            "branch_materials_empty",
            "No formats selected",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    record = await _active_dekor_record(db, payload.dekor_id)
    label = dekor_label(record.dekor, record.manufacturer)

    # Validate the whole batch first — nothing is added to the session until every
    # row passes, so a rejection leaves the transaction untouched.
    validated: list[tuple[BranchMaterialFormat, int, int]] = []
    seen: set[BranchMaterialFormat] = set()
    for item in payload.formats:
        fmt = _validate_branch_material_format(
            tur=record.dekor.tur,
            qalinlik_mm=item.qalinlik_mm,
            uzunlik_mm=item.uzunlik_mm,
            eni_mm=item.eni_mm,
            kromka_eni_mm=item.kromka_eni_mm,
            label=label,
        )
        _validate_branch_material_numbers(item.price_tiyin, item.min_stock, label=label)
        if fmt in seen:
            raise APIError(
                "branch_material_duplicate",
                f"«{label}» uchun bir xil format ikki marta kiritilgan",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        seen.add(fmt)
        validated.append((fmt, item.price_tiyin, item.min_stock))

    existing = await _carried_formats(db, branch_id=scope.branch_id, dekor_id=record.dekor.id)

    from app.modules.inventory.api import ensure_stock_item_for_branch_material

    created: list[BranchMaterialRecord] = []
    skipped: list[BranchMaterialFormat] = []
    for fmt, price_tiyin, min_stock in validated:
        if fmt in existing:
            skipped.append(fmt)
            continue
        row = BranchMaterial(
            branch_id=scope.branch_id,
            dekor_id=record.dekor.id,
            qalinlik_mm=fmt.qalinlik_mm,
            uzunlik_mm=fmt.uzunlik_mm,
            eni_mm=fmt.eni_mm,
            kromka_eni_mm=fmt.kromka_eni_mm,
            price_tiyin=price_tiyin,
            min_stock=min_stock,
            status=MaterialStatus.ACTIVE,
        )
        db.add(row)
        await db.flush()
        await ensure_stock_item_for_branch_material(
            db,
            branch_id=scope.branch_id,
            branch_material_id=row.id,
            min_stock=min_stock,
        )
        created.append(
            BranchMaterialRecord(
                branch_material=row,
                dekor=record.dekor,
                manufacturer=record.manufacturer,
            )
        )
    if created:
        await record_action(
            db,
            actor=actor_from_principal(principal),
            action="catalog.branch_material.attach",
            entity_type="branch",
            entity_id=scope.branch_id,
            workshop_id=scope.workshop_id,
            branch_id=scope.branch_id,
            summary=f"Added {len(created)} formats of {label} to branch",
            details={
                "dekor_id": str(record.dekor.id),
                "branch_material_ids": [str(row.branch_material.id) for row in created],
            },
        )
    return BranchMaterialAttachResult(created=created, skipped=skipped)


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
    label = dekor_label(record.dekor, record.manufacturer)
    format_fields = ("qalinlik_mm", "uzunlik_mm", "eni_mm", "kromka_eni_mm")
    if any(field in payload.model_fields_set for field in format_fields):
        # A mistyped sheet size has to be fixable in place: stock, cutting panels
        # and order items all FK this row, so deleting and re-attaching is not an
        # option. The merged shape is re-validated as a whole.
        fmt = _validate_branch_material_format(
            tur=record.dekor.tur,
            qalinlik_mm=_patched(payload, "qalinlik_mm", row.qalinlik_mm),
            uzunlik_mm=_patched(payload, "uzunlik_mm", row.uzunlik_mm),
            eni_mm=_patched(payload, "eni_mm", row.eni_mm),
            kromka_eni_mm=_patched(payload, "kromka_eni_mm", row.kromka_eni_mm),
            label=label,
        )
        await _ensure_branch_material_format_available(
            db,
            branch_id=scope.branch_id,
            dekor_id=row.dekor_id,
            fmt=fmt,
            current=row,
            label=label,
        )
        row.qalinlik_mm = fmt.qalinlik_mm
        row.uzunlik_mm = fmt.uzunlik_mm
        row.eni_mm = fmt.eni_mm
        row.kromka_eni_mm = fmt.kromka_eni_mm
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
            branch_material_id=row.id,
            min_stock=row.min_stock,
        )
    updated_label = branch_material_label(row, record.dekor, record.manufacturer)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="catalog.branch_material.update",
        entity_type="branch_material",
        entity_id=row.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Updated branch material {updated_label}",
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
    label = branch_material_label(row, record.dekor, record.manufacturer)
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
        summary=f"Set branch material {label} to {to_status.value}",
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


# --------------------------------------------------------------------------- #
# Lookups
# --------------------------------------------------------------------------- #


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
        select(BranchMaterial, Dekor, Manufacturer)
        .join(Dekor, Dekor.id == BranchMaterial.dekor_id)
        .join(Manufacturer, Manufacturer.id == Dekor.manufacturer_id)
        .where(BranchMaterial.id == branch_material_id, BranchMaterial.branch_id == scope.branch_id)
    )
    row = result.one_or_none()
    if row is None:
        raise APIError(
            "branch_material_not_found",
            "Branch material not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    bm, dekor, manufacturer = row
    return BranchMaterialRecord(bm, dekor, manufacturer), scope


async def _dekor_record(db: AsyncSession, dekor_id: uuid.UUID) -> DekorRecord | None:
    row = (
        await db.execute(
            select(Dekor, Manufacturer)
            .join(Manufacturer, Manufacturer.id == Dekor.manufacturer_id)
            .where(Dekor.id == dekor_id)
        )
    ).one_or_none()
    if row is None:
        return None
    dekor, manufacturer = row
    return DekorRecord(dekor=dekor, manufacturer=manufacturer)


async def _active_dekor_record(db: AsyncSession, dekor_id: uuid.UUID) -> DekorRecord:
    record = await _dekor_record(db, dekor_id)
    if (
        record is None
        or record.dekor.holat is not MaterialStatus.ACTIVE
        or record.manufacturer.status is not MaterialStatus.ACTIVE
    ):
        raise APIError(
            "dekor_not_found",
            "Dekor not found",
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


async def _ensure_dekor_identity_available(
    db: AsyncSession,
    *,
    manufacturer_id: uuid.UUID,
    tur: DekorType,
    kod: str | None,
    nomi: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """Mirror of the two partial unique indexes on `dekorlar`.

    Checked here as well as in the DB because the indexes are `postgresql_where`
    and do not exist on SQLite, and because a 409 with a message beats an
    IntegrityError 500 either way.
    """

    query = select(Dekor.id).where(
        Dekor.manufacturer_id == manufacturer_id,
        Dekor.tur == tur,
    )
    if kod is not None:
        query = query.where(func.lower(Dekor.kod) == kod.lower())
    else:
        query = query.where(Dekor.kod.is_(None), func.lower(Dekor.nomi) == nomi.lower())
    if exclude_id is not None:
        query = query.where(Dekor.id != exclude_id)
    if await db.scalar(query) is not None:
        raise APIError(
            "dekor_exists",
            "This manufacturer already has a dekor with that code",
            status_code=status.HTTP_409_CONFLICT,
        )


async def _carried_formats(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    dekor_id: uuid.UUID,
) -> set[BranchMaterialFormat]:
    rows = (
        await db.execute(
            select(
                BranchMaterial.qalinlik_mm,
                BranchMaterial.uzunlik_mm,
                BranchMaterial.eni_mm,
                BranchMaterial.kromka_eni_mm,
            ).where(
                BranchMaterial.branch_id == branch_id,
                BranchMaterial.dekor_id == dekor_id,
            )
        )
    ).all()
    return {
        BranchMaterialFormat(normalize_mm(qalinlik), uzunlik, eni, kromka_eni)
        for qalinlik, uzunlik, eni, kromka_eni in rows
    }


async def _ensure_branch_material_format_available(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    dekor_id: uuid.UUID,
    fmt: BranchMaterialFormat,
    current: BranchMaterial,
    label: str,
) -> None:
    carried = await _carried_formats(db, branch_id=branch_id, dekor_id=dekor_id)
    # The row being edited is in the carried set by definition; a no-op edit of
    # its own format must not collide with itself.
    carried.discard(
        BranchMaterialFormat(
            normalize_mm(current.qalinlik_mm),
            current.uzunlik_mm,
            current.eni_mm,
            current.kromka_eni_mm,
        )
    )
    if fmt in carried:
        raise APIError(
            "branch_material_exists",
            f"«{label}» bu formatda allaqachon mavjud",
            status_code=status.HTTP_409_CONFLICT,
        )


async def _recompute_search_keys_for_manufacturer(
    db: AsyncSession, manufacturer: Manufacturer
) -> None:
    rows = (await db.scalars(select(Dekor).where(Dekor.manufacturer_id == manufacturer.id))).all()
    for dekor in rows:
        dekor.search_key = _search_key(
            nomi=dekor.nomi, kod=dekor.kod, manufacturer_name=manufacturer.name
        )


# --------------------------------------------------------------------------- #
# Filters, paging, validation
# --------------------------------------------------------------------------- #

# Catalog list endpoints paginate with the house limit/offset convention
# (sales, inventory, audit): the caller opts in by passing a limit, the response
# stays a bare list, and the client infers "has more" from a full page. A None
# limit means unbounded — preserving the pre-pagination behavior for callers (and
# tests) that don't ask for a page. Ordering carries a Dekor.id tiebreaker so
# offset paging is deterministic across requests.
DEKORLAR_MAX_LIMIT = 200


def _bounded_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    return max(1, min(limit, DEKORLAR_MAX_LIMIT))


def _paginate(query: Any, *, limit: int | None, offset: int) -> Any:
    bounded = _bounded_limit(limit)
    if bounded is None:
        return query
    return query.limit(bounded).offset(max(0, offset))


def _dekor_filters(
    query: Any,
    *,
    search: str | None,
    tur: DekorType | None,
    manufacturer_id: uuid.UUID | None,
    status_filter: MaterialStatus | None,
    turlar: list[DekorType] | None = None,
    manufacturer_ids: list[uuid.UUID] | None = None,
) -> Any:
    if tur is not None:
        query = query.where(Dekor.tur == tur)
    if turlar:
        query = query.where(Dekor.tur.in_(turlar))
    if manufacturer_id is not None:
        query = query.where(Dekor.manufacturer_id == manufacturer_id)
    if manufacturer_ids:
        query = query.where(Dekor.manufacturer_id.in_(manufacturer_ids))
    if status_filter is not None:
        query = query.where(Dekor.holat == status_filter)
    # ILIKEs over the folded key replace the old four-column OR: `сонома`,
    # `Sonoma` and `sonoma` all fold to the same string, which no per-column
    # ILIKE over the raw text could match.
    #
    # Tokenized and ANDed because `search_key` is a *concatenation* of nomi, kod
    # and manufacturer with the separators folded away — "egger sonoma" as one
    # blob would never match "sonomah1334egger", so each word is matched on its
    # own and all of them must hit.
    for word in (search or "").split():
        folded = fold(word)
        if folded:
            query = query.where(Dekor.search_key.ilike(f"%{folded}%"))
    return query


def _search_key(*, nomi: str, kod: str | None, manufacturer_name: str) -> str:
    return fold(f"{nomi} {kod or ''} {manufacturer_name}")


def _validate_branch_material_format(
    *,
    tur: DekorType,
    qalinlik_mm: Decimal | None,
    uzunlik_mm: int | None,
    eni_mm: int | None,
    kromka_eni_mm: int | None,
    label: str,
) -> BranchMaterialFormat:
    """The panel/tape shape rule the DB cannot express.

    `tur` lives on `dekorlar`, so a CHECK on `branch_materials` cannot see it and
    only the column-local halves are enforced there. This is the whole rule, and
    it also normalizes orientation so a format is stored one way only.
    """

    # `None` reaches here only from a PATCH that explicitly nulls the thickness.
    if qalinlik_mm is None or qalinlik_mm <= 0:
        raise APIError(
            "invalid_thickness",
            f"«{label}» uchun qalinlik noto'g'ri",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    thickness = normalize_mm(qalinlik_mm)
    if is_tape(tur):
        if uzunlik_mm is not None or eni_mm is not None:
            raise APIError(
                "invalid_kromka_format",
                f"«{label}» kromka: uzunlik va eni kiritilmaydi",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if kromka_eni_mm is None:
            raise APIError(
                "invalid_kromka_format",
                f"«{label}» uchun kromka eni kerak",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if kromka_eni_mm <= 0:
            raise APIError(
                "invalid_kromka_eni",
                f"«{label}» uchun kromka eni noto'g'ri",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return BranchMaterialFormat(thickness, None, None, kromka_eni_mm)
    if kromka_eni_mm is not None:
        raise APIError(
            "invalid_panel_format",
            f"«{label}» list: kromka eni kiritilmaydi",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if uzunlik_mm is None or eni_mm is None:
        raise APIError(
            "invalid_panel_format",
            f"«{label}» uchun uzunlik va eni kerak",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if uzunlik_mm <= 0 or eni_mm <= 0:
        raise APIError(
            "invalid_panel_size",
            f"«{label}» uchun o'lcham noto'g'ri",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    # Normalize rather than reject: 1830x2750 and 2750x1830 are the same sheet,
    # and the unique index compares the columns literally.
    length, width = max(uzunlik_mm, eni_mm), min(uzunlik_mm, eni_mm)
    return BranchMaterialFormat(thickness, length, width, None)


def _validate_branch_material_numbers(price_tiyin: int, min_stock: int, *, label: str) -> None:
    """Price and threshold rules — shared by attach and patch so they can't drift.

    Price 0 is legal and means "not priced yet": a branch registers its format
    list first and prices it later. Client-facing listings drop unpriced rows;
    workshop-facing ones flag them.
    """

    if price_tiyin < 0:
        raise APIError(
            "invalid_price",
            f"«{label}» uchun narx noto'g'ri",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if min_stock < 0:
        raise APIError(
            "invalid_min_stock",
            f"«{label}» uchun chegara noto'g'ri",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def _validate_nonnegative(value: int, code: str) -> None:
    if value < 0:
        raise APIError(code, "Value must be non-negative", status_code=status.HTTP_400_BAD_REQUEST)


def _patched(payload: BranchMaterialPatchRequest, field: str, current: Any) -> Any:
    """Patch semantics for a nullable field: absent keeps, present (even null) sets."""

    if field in payload.model_fields_set:
        return getattr(payload, field)
    return current


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


def normalize_mm(value: Decimal) -> Decimal:
    """Trailing-zero scale differs by driver (Postgres "2", SQLite "2.0000000000").

    Normalizing keeps stored thicknesses, response payloads and the format-key
    comparison all reading the same value. Published through `catalog.api`
    because every module that puts a thickness on the wire needs it — a second
    copy is how `18` and `18.0000000000` end up on two different endpoints.
    """

    return Decimal(_fmt_mm(value))
