"""Platform decor catalog, decor format and branch material use cases.

The split this module enforces: the platform owns the *product* — the decor's
identity (`decors`) and every concrete format it is made in (`decor_formats`) —
while a branch owns only the *commercial decision* (`branch_materials`: we carry
this format, at this price, with this threshold). Nothing on the branch surface
may create or edit a format, and nothing on the platform surface may name a
price.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from fastapi import status
from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.material_label import edge_label, material_label
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.core.search_fold import fold
from app.models.enums import (
    AuthenticatedPrincipalType,
    DecorType,
    MaterialStatus,
    Permission,
)
from app.modules.access.api import BranchScope, resolve_branch_scope
from app.modules.catalog.contracts import (
    BranchMaterial,
    Decor,
    DecorFormat,
    Manufacturer,
    is_tape,
    requires_finished_sides,
)
from app.modules.catalog.schemas import (
    BranchMaterialAttachRequest,
    BranchMaterialPatchRequest,
    DecorCreateRequest,
    DecorFormatCreateRequest,
    DecorPatchRequest,
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
# migration re-pointed those rows' `entity_id` at the new decor id *without*
# rewriting the string. Changing it here would 403 every historical photo, so
# the wire value stays "material" while the Python vocabulary moved on.
_IMAGE_ENTITY_TYPE = "material"
# Same reasoning for the audit trail: `action_log` and `status_change_log` hold
# years of rows typed `dekor`, and the platform audit screen filters on that
# literal. Renaming it would split one entity's history in two streams. The
# stored vocabulary stays; only the Python vocabulary moved.
_DECOR_ENTITY_TYPE = "dekor"
_DECOR_FORMAT_ENTITY_TYPE = "decor_format"


@dataclass(frozen=True)
class DecorRecord:
    decor: Decor
    manufacturer: Manufacturer
    branch_usage_count: int = 0
    # Active formats. The admin table's "how finished is this decor's entry"
    # column: a decor with zero formats is a name nobody can attach.
    format_count: int = 0


@dataclass(frozen=True)
class DecorFormatRecord:
    decor_format: DecorFormat
    decor: Decor
    manufacturer: Manufacturer
    # Set only by the workshop attach list: does this branch already carry it.
    carried: bool = False


@dataclass(frozen=True)
class BranchMaterialRecord:
    branch_material: BranchMaterial
    decor_format: DecorFormat
    decor: Decor
    manufacturer: Manufacturer


@dataclass(frozen=True)
class DecorFormatShape:
    """A validated, normalized format tuple — the natural key of a format.

    Normalized means: thickness at a stable scale, and `length_mm >= width_mm`
    for panel-shaped formats, so 2070x2800 and 2800x2070 are the same product
    rather than two rows that cut identically.
    """

    type: DecorType
    thickness_mm: Decimal
    length_mm: int | None
    width_mm: int | None
    tape_width_mm: int | None
    finished_sides: int | None


@dataclass(frozen=True)
class BranchMaterialAttachResult:
    created: list[BranchMaterialRecord]
    # Formats this branch already carried. A batch spans decors, so a skip has
    # to name the format it came from.
    skipped: list[uuid.UUID]


@dataclass(frozen=True)
class BranchCatalogOption:
    decor: Decor
    manufacturer: Manufacturer
    carried_format_count: int = 0
    # Active formats the platform offers for this decor. `carried == available`
    # is what the picker greys out as "nothing left to add".
    available_format_count: int = 0


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


def decor_snapshot(decor: Decor, manufacturer: Manufacturer) -> dict[str, Any]:
    """Identity half of a material snapshot — no format, so no dimensions print."""

    return {
        "manufacturer_name": manufacturer.name,
        "code": decor.code,
        "name": decor.name,
        "has_grain": decor.has_grain,
    }


def decor_format_snapshot(decor_format: DecorFormat) -> dict[str, Any]:
    """Format half of a material snapshot — what the sheet or tape physically is.

    Thickness goes out as a *string* so the label formatter renders it (it
    ignores a non-str thickness); the size fields stay ints.
    """

    return {
        "type": decor_format.type.value,
        "thickness_mm": _fmt_mm(decor_format.thickness_mm),
        "length_mm": decor_format.length_mm,
        "width_mm": decor_format.width_mm,
        "tape_width_mm": decor_format.tape_width_mm,
        "finished_sides": decor_format.finished_sides,
    }


def branch_material_snapshot(
    decor_format: DecorFormat,
    decor: Decor,
    manufacturer: Manufacturer,
) -> dict[str, Any]:
    """The canonical snapshot shape for a branch material.

    One writer for the key vocabulary that `app/core/material_label.py` reads and
    that cutting/sales freeze into history. The branch row itself contributes
    nothing to it: price and threshold are not identity, and everything that
    prints comes from the format and its decor.

    Keep this in step with `cutting/service.py::_material_snapshot` — nothing
    mechanical catches a divergence, the picker and the order history just start
    printing different names for the same sheet.
    """

    return {
        **decor_snapshot(decor, manufacturer),
        **decor_format_snapshot(decor_format),
    }


def decor_label(decor: Decor, manufacturer: Manufacturer) -> str:
    """Display string for a decor pattern, e.g. `Egger H1334 ST9 · Sonoma eman`.

    No substrate prefix and no dimensions: a decor is no longer an LDSP or a
    kromka, it is a pattern that exists in both. What it is physically prints
    from the format — see `decor_format_label`.
    """

    return material_label(decor_snapshot(decor, manufacturer), decor.id)


def decor_format_label(
    decor_format: DecorFormat,
    decor: Decor,
    manufacturer: Manufacturer,
) -> str:
    """Display string for one concrete product, dimensions included."""

    snapshot = branch_material_snapshot(decor_format, decor, manufacturer)
    if is_tape(decor_format.type):
        return edge_label(snapshot, decor_format.id)
    return material_label(snapshot, decor_format.id)


def branch_material_label(
    decor_format: DecorFormat,
    decor: Decor,
    manufacturer: Manufacturer,
    branch_material_id: uuid.UUID | None = None,
) -> str:
    """Display string for a carried format.

    Identical to `decor_format_label` by construction — a branch row adds no
    printable fact — but kept as its own name because the id used for the empty-
    snapshot fallback differs, and because every caller reads better naming the
    thing it holds.
    """

    snapshot = branch_material_snapshot(decor_format, decor, manufacturer)
    fallback_id = branch_material_id or decor_format.id
    if is_tape(decor_format.type):
        return edge_label(snapshot, fallback_id)
    return material_label(snapshot, fallback_id)


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
        # search for every decor of this maker unless they are recomputed here.
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
# Decors (platform)
# --------------------------------------------------------------------------- #


async def list_decors(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    search: str | None = None,
    type_: DecorType | None = None,
    types: list[DecorType] | None = None,
    manufacturer_id: uuid.UUID | None = None,
    manufacturer_ids: list[uuid.UUID] | None = None,
    status_filter: MaterialStatus | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[DecorRecord]:
    require_platform_operator(principal)
    # AB-22: aggregate a distinct-branch usage count per decor via a LEFT JOIN so
    # the platform list can show how many branches carry each decor without a
    # denormalized column. Counting distinct *branches* (not rows) keeps the
    # number stable as a branch adds formats.
    query = (
        select(
            Decor,
            Manufacturer,
            func.count(func.distinct(BranchMaterial.branch_id)),
            _active_format_count_subquery(),
        )
        .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
        .outerjoin(DecorFormat, DecorFormat.decor_id == Decor.id)
        .outerjoin(
            BranchMaterial,
            and_(BranchMaterial.decor_format_id == DecorFormat.id),
        )
    )
    query = _decor_filters(
        query,
        search=search,
        type_=type_,
        types=types,
        manufacturer_id=manufacturer_id,
        manufacturer_ids=manufacturer_ids,
        status_filter=status_filter,
    )
    query = query.group_by(Decor.id, Manufacturer.id).order_by(
        Manufacturer.name, Decor.name, Decor.id
    )
    query = _paginate(query, limit=limit, offset=offset)
    return [
        DecorRecord(
            decor=decor,
            manufacturer=manufacturer,
            branch_usage_count=int(usage or 0),
            format_count=int(formats or 0),
        )
        for decor, manufacturer, usage, formats in (await db.execute(query)).all()
    ]


async def create_decor(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: DecorCreateRequest,
) -> DecorRecord:
    require_platform_operator(principal)
    manufacturer = await _active_manufacturer(db, payload.manufacturer_id)
    name = _required_text(payload.name, "decor_name_required")
    code = _optional_text(payload.code)
    await _ensure_decor_identity_available(
        db,
        manufacturer_id=manufacturer.id,
        code=code,
        name=name,
    )
    row = Decor(
        manufacturer_id=manufacturer.id,
        code=code,
        name=name,
        has_grain=payload.has_grain,
        status=MaterialStatus.ACTIVE,
        search_key=_search_key(name=name, code=code, manufacturer_name=manufacturer.name),
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
        entity_type=_DECOR_ENTITY_TYPE,
        entity_id=row.id,
        summary=f"Created decor {decor_label(row, manufacturer)}",
        details={"manufacturer_id": str(row.manufacturer_id)},
    )
    await db.refresh(row)
    return DecorRecord(decor=row, manufacturer=manufacturer)


async def get_decor(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    decor_id: uuid.UUID,
) -> DecorRecord:
    require_platform_operator(principal)
    record = await _decor_record(db, decor_id)
    if record is None:
        raise APIError(
            "decor_not_found",
            "Decor not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return record


async def update_decor(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    decor_id: uuid.UUID,
    payload: DecorPatchRequest,
) -> DecorRecord:
    record = await get_decor(db, principal=principal, decor_id=decor_id)
    row = record.decor
    manufacturer = record.manufacturer
    if "manufacturer_id" in payload.model_fields_set and payload.manufacturer_id is not None:
        manufacturer = await _active_manufacturer(db, payload.manufacturer_id)
        row.manufacturer_id = manufacturer.id
    if "name" in payload.model_fields_set and payload.name is not None:
        row.name = _required_text(payload.name, "decor_name_required")
    if "code" in payload.model_fields_set:
        row.code = _optional_text(payload.code)
    if "has_grain" in payload.model_fields_set and payload.has_grain is not None:
        row.has_grain = payload.has_grain
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
    await _ensure_decor_identity_available(
        db,
        manufacturer_id=row.manufacturer_id,
        code=row.code,
        name=row.name,
        exclude_id=row.id,
    )
    # Recomputed unconditionally: every input to the key (name, code, maker) is
    # patchable, and an unchanged write costs one fold() call.
    row.search_key = _search_key(name=row.name, code=row.code, manufacturer_name=manufacturer.name)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="catalog.dekor.update",
        entity_type=_DECOR_ENTITY_TYPE,
        entity_id=row.id,
        summary=f"Updated decor {decor_label(row, manufacturer)}",
    )
    await db.refresh(row)
    return DecorRecord(decor=row, manufacturer=manufacturer)


async def set_decor_status(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    decor_id: uuid.UUID,
    to_status: MaterialStatus,
) -> DecorRecord:
    record = await get_decor(db, principal=principal, decor_id=decor_id)
    row = record.decor
    if row.status is to_status:
        return record
    from_status = row.status.value
    row.status = to_status
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action=f"catalog.dekor.{to_status.value}",
        entity_type=_DECOR_ENTITY_TYPE,
        entity_id=row.id,
        summary=f"Set decor {decor_label(row, record.manufacturer)} to {to_status.value}",
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type=_DECOR_ENTITY_TYPE,
        entity_id=row.id,
        from_status=from_status,
        to_status=to_status.value,
        action_log_id=action.id,
    )
    await db.refresh(row)
    return record


# --------------------------------------------------------------------------- #
# Decor formats (platform)
# --------------------------------------------------------------------------- #


async def list_decor_formats(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    decor_id: uuid.UUID,
) -> list[DecorFormatRecord]:
    """Every format of one decor, active first — the platform's own view."""

    record = await get_decor(db, principal=principal, decor_id=decor_id)
    rows = (
        await db.scalars(
            select(DecorFormat)
            .where(DecorFormat.decor_id == record.decor.id)
            .order_by(*_format_ordering())
        )
    ).all()
    return [
        DecorFormatRecord(
            decor_format=row,
            decor=record.decor,
            manufacturer=record.manufacturer,
        )
        for row in rows
    ]


async def create_decor_format(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    decor_id: uuid.UUID,
    payload: DecorFormatCreateRequest,
) -> DecorFormatRecord:
    """Add one concrete product to a decor. Platform-only, and immutable after."""

    record = await get_decor(db, principal=principal, decor_id=decor_id)
    if record.decor.status is not MaterialStatus.ACTIVE:
        raise APIError(
            "decor_inactive",
            "Cannot add a format to an inactive decor",
            status_code=status.HTTP_409_CONFLICT,
        )
    shape = validate_decor_format_shape(
        type_=payload.type,
        thickness_mm=payload.thickness_mm,
        length_mm=payload.length_mm,
        width_mm=payload.width_mm,
        tape_width_mm=payload.tape_width_mm,
        finished_sides=payload.finished_sides,
    )
    existing = await _find_decor_format(db, decor_id=record.decor.id, shape=shape)
    if existing is not None:
        raise APIError(
            "decor_format_exists",
            "This decor already has that format",
            status_code=status.HTTP_409_CONFLICT,
            details={"decor_format_id": str(existing.id)},
        )
    row = DecorFormat(
        decor_id=record.decor.id,
        type=shape.type,
        thickness_mm=shape.thickness_mm,
        length_mm=shape.length_mm,
        width_mm=shape.width_mm,
        tape_width_mm=shape.tape_width_mm,
        finished_sides=shape.finished_sides,
        status=MaterialStatus.ACTIVE,
    )
    db.add(row)
    await db.flush()
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="catalog.decor_format.create",
        entity_type=_DECOR_FORMAT_ENTITY_TYPE,
        entity_id=row.id,
        summary=f"Created format {decor_format_label(row, record.decor, record.manufacturer)}",
        details={"decor_id": str(record.decor.id), "type": row.type.value},
    )
    await db.refresh(row)
    return DecorFormatRecord(
        decor_format=row,
        decor=record.decor,
        manufacturer=record.manufacturer,
    )


async def set_decor_format_status(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    decor_id: uuid.UUID,
    decor_format_id: uuid.UUID,
    to_status: MaterialStatus,
) -> DecorFormatRecord:
    """Status is the only mutable column of a format — see the model docstring.

    Deactivating one never cascades into branch rows: the branch keeps selling
    the remainder on its shelf and keeps receiving arrivals, because a supplier
    may still have stock of a product the maker has stopped producing. The
    branch retires its own row when the shelf is empty.
    """

    record = await get_decor(db, principal=principal, decor_id=decor_id)
    row = await db.get(DecorFormat, decor_format_id)
    if row is None or row.decor_id != record.decor.id:
        raise APIError(
            "decor_format_not_found",
            "Decor format not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    result = DecorFormatRecord(
        decor_format=row,
        decor=record.decor,
        manufacturer=record.manufacturer,
    )
    if row.status is to_status:
        return result
    from_status = row.status.value
    row.status = to_status
    label = decor_format_label(row, record.decor, record.manufacturer)
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action=f"catalog.decor_format.{to_status.value}",
        entity_type=_DECOR_FORMAT_ENTITY_TYPE,
        entity_id=row.id,
        summary=f"Set format {label} to {to_status.value}",
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type=_DECOR_FORMAT_ENTITY_TYPE,
        entity_id=row.id,
        from_status=from_status,
        to_status=to_status.value,
        action_log_id=action.id,
    )
    await db.refresh(row)
    return result


# --------------------------------------------------------------------------- #
# Branch attach picker
# --------------------------------------------------------------------------- #


async def list_branch_catalog_options(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    search: str | None = None,
    type_: DecorType | None = None,
    manufacturer_id: uuid.UUID | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> BranchCatalogOptionsPage:
    """Attachable decors for a branch, plus the unpaginated total.

    Nothing is hidden: a branch legitimately carries the same decor in several
    formats, so "already carried" is no reason to drop a row. Each option
    reports what it carries against what the platform offers instead.
    """

    _require_workshop_user(principal)
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    attachable = _attachable_decors_query()
    filtered = _decor_filters(
        attachable,
        search=search,
        type_=type_,
        manufacturer_id=manufacturer_id,
        status_filter=None,
    )
    total = await db.scalar(filtered.with_only_columns(func.count(Decor.id)))
    available = _active_format_count_subquery()
    carried = (
        select(func.count(BranchMaterial.id))
        .join(DecorFormat, DecorFormat.id == BranchMaterial.decor_format_id)
        .where(
            BranchMaterial.branch_id == scope.branch_id,
            DecorFormat.decor_id == Decor.id,
            DecorFormat.status == MaterialStatus.ACTIVE,
        )
        .correlate(Decor)
        .scalar_subquery()
    )
    query = _paginate(
        filtered.with_only_columns(Decor, Manufacturer, carried, available).order_by(
            Manufacturer.name, Decor.name, Decor.id
        ),
        limit=limit,
        offset=offset,
    )
    return BranchCatalogOptionsPage(
        items=[
            BranchCatalogOption(
                decor=decor,
                manufacturer=manufacturer,
                carried_format_count=int(carried_count or 0),
                available_format_count=int(available_count or 0),
            )
            for decor, manufacturer, carried_count, available_count in (
                await db.execute(query)
            ).all()
        ],
        total=int(total or 0),
    )


async def list_branch_catalog_formats(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    decor_id: uuid.UUID,
) -> list[DecorFormatRecord]:
    """Step two of the attach sheet: the decor's ACTIVE formats, carried flagged.

    Inactive formats are absent rather than disabled — the platform has said the
    product is no longer made, and offering a branch the chance to start
    carrying one would be offering a dead end.
    """

    _require_workshop_user(principal)
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    record = await _decor_record(db, decor_id)
    if record is None:
        raise APIError(
            "decor_not_found",
            "Decor not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    carried_ids = set(
        (
            await db.scalars(
                select(BranchMaterial.decor_format_id).where(
                    BranchMaterial.branch_id == scope.branch_id
                )
            )
        ).all()
    )
    rows = (
        await db.scalars(
            select(DecorFormat)
            .where(
                DecorFormat.decor_id == record.decor.id,
                DecorFormat.status == MaterialStatus.ACTIVE,
            )
            .order_by(*_format_ordering())
        )
    ).all()
    return [
        DecorFormatRecord(
            decor_format=row,
            decor=record.decor,
            manufacturer=record.manufacturer,
            carried=row.id in carried_ids,
        )
        for row in rows
    ]


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
    attachable = _attachable_decors_query()
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


def _attachable_decors_query() -> Any:
    """Active decors from active manufacturers that have at least one format.

    A decor with no active format is a name nobody can attach anything of, so it
    is not an option — showing it would mean a two-step picker whose step two is
    empty.
    """

    return (
        select(Decor.id)
        .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
        .where(
            Decor.status == MaterialStatus.ACTIVE,
            Manufacturer.status == MaterialStatus.ACTIVE,
            _has_active_format(),
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
    type_: DecorType | None = None,
    manufacturer_id: uuid.UUID | None = None,
    decor_id: uuid.UUID | None = None,
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
        branch_material_join()
        .where(BranchMaterial.branch_id == scope.branch_id)
        .order_by(
            Manufacturer.name,
            Decor.name,
            DecorFormat.thickness_mm,
            BranchMaterial.id,
        )
    )
    if status_filter is not None:
        query = query.where(BranchMaterial.status == status_filter)
    if decor_id is not None:
        query = query.where(DecorFormat.decor_id == decor_id)
    if type_ is not None:
        # Read straight off the format here: the join already has it, and
        # "carries a kromka" is a fact about the row, not about the decor.
        query = query.where(DecorFormat.type == type_)
    query = _decor_filters(
        query,
        search=search,
        manufacturer_id=manufacturer_id,
        status_filter=None,
    )
    query = _paginate(query, limit=limit, offset=offset)
    return [
        BranchMaterialRecord(
            branch_material=bm,
            decor_format=decor_format,
            decor=decor,
            manufacturer=manufacturer,
        )
        for bm, decor_format, decor, manufacturer in (await db.execute(query)).all()
    ]


def branch_material_join() -> Any:
    """The one join every branch-material read walks.

    stock → branch_material → decor_format → decor → manufacturer. Published so
    inventory, cutting, sales and the client portal compose the same four-table
    chain instead of four drifting copies of it.
    """

    return (
        select(BranchMaterial, DecorFormat, Decor, Manufacturer)
        .join(DecorFormat, DecorFormat.id == BranchMaterial.decor_format_id)
        .join(Decor, Decor.id == DecorFormat.decor_id)
        .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
    )


async def attach_branch_materials(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    payload: BranchMaterialAttachRequest,
) -> BranchMaterialAttachResult:
    """Carry several platform formats, in ONE transaction.

    Every row is validated before anything is written, so one bad format
    attaches nothing. A format the branch already carries is skipped rather than
    rejected — the picker shows what is carried, so a duplicate here is a
    concurrent attach, not user error.
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
            "No formats selected",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Validate the whole batch first — nothing is added to the session until
    # every row passes, so a rejection leaves the transaction untouched.
    validated: list[tuple[DecorFormatRecord, int, int]] = []
    seen: set[uuid.UUID] = set()
    for item in payload.items:
        record = await _attachable_format_record(db, item.decor_format_id)
        label = decor_format_label(record.decor_format, record.decor, record.manufacturer)
        _validate_branch_material_numbers(item.price_tiyin, item.min_stock, label=label)
        if item.decor_format_id in seen:
            raise APIError(
                "branch_material_duplicate",
                f"«{label}» ikki marta kiritilgan",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        seen.add(item.decor_format_id)
        validated.append((record, item.price_tiyin, item.min_stock))

    carried = set(
        (
            await db.scalars(
                select(BranchMaterial.decor_format_id).where(
                    BranchMaterial.branch_id == scope.branch_id,
                    BranchMaterial.decor_format_id.in_(seen),
                )
            )
        ).all()
    )

    from app.modules.inventory.api import ensure_stock_item_for_branch_material

    created: list[BranchMaterialRecord] = []
    skipped: list[uuid.UUID] = []
    for record, price_tiyin, min_stock in validated:
        if record.decor_format.id in carried:
            skipped.append(record.decor_format.id)
            continue
        row = BranchMaterial(
            branch_id=scope.branch_id,
            decor_format_id=record.decor_format.id,
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
        )
        created.append(
            BranchMaterialRecord(
                branch_material=row,
                decor_format=record.decor_format,
                decor=record.decor,
                manufacturer=record.manufacturer,
            )
        )
    if created:
        decor_ids = sorted({str(row.decor.id) for row in created})
        await record_action(
            db,
            actor=actor_from_principal(principal),
            action="catalog.branch_material.attach",
            entity_type="branch",
            entity_id=scope.branch_id,
            workshop_id=scope.workshop_id,
            branch_id=scope.branch_id,
            summary=(f"Added {len(created)} formats across {len(decor_ids)} decors to branch"),
            details={
                "decor_ids": decor_ids,
                "decor_format_ids": [str(row.decor_format.id) for row in created],
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
    """Price and threshold only.

    The format is not editable: it *is* this row's identity, and "change the
    format" means attaching the other format and retiring this one — otherwise
    stock, panels and order items silently change what they refer to.
    """

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
        # No mirror to update: `branch_materials.min_stock` is the only home of
        # the low-stock threshold, and every reader joins to it.
        _validate_nonnegative(payload.min_stock, "invalid_min_stock")
        row.min_stock = payload.min_stock
    updated_label = branch_material_label(
        record.decor_format, record.decor, record.manufacturer, row.id
    )
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
    label = branch_material_label(record.decor_format, record.decor, record.manufacturer, row.id)
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


async def set_branch_material_min_stock(
    db: AsyncSession,
    *,
    branch_material_id: uuid.UUID,
    branch_id: uuid.UUID,
    min_stock: int,
) -> BranchMaterial:
    """Write one branch material's low-stock threshold and nothing else.

    The narrow door the inventory module needs: the threshold is warehouse
    policy, set at the shelf by `manage_inventory`, while the catalog edit form
    keeps the same field for `manage_catalog`. The value lives once, here on
    `branch_materials` — no mirror anywhere.

    Deliberately takes no principal: the *caller* owns the permission check (it
    is a different grant on each surface), and this function only guarantees the
    row belongs to the branch it is being written through.
    """

    if min_stock < 0:
        raise APIError(
            "min_stock_invalid",
            "Threshold cannot be negative",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    row = await db.scalar(
        select(BranchMaterial).where(
            BranchMaterial.id == branch_material_id,
            BranchMaterial.branch_id == branch_id,
        )
    )
    if row is None:
        raise APIError(
            "branch_material_not_found",
            "Material is not selected in this branch",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    row.min_stock = min_stock
    await db.flush()
    # `updated_at` carries an `onupdate`, so the flush expires it. The caller
    # renders this row straight into its response — a lazy load there would be
    # IO outside the greenlet and 500 the request.
    await db.refresh(row)
    return row


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
        branch_material_join().where(
            BranchMaterial.id == branch_material_id,
            BranchMaterial.branch_id == scope.branch_id,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise APIError(
            "branch_material_not_found",
            "Branch material not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    bm, decor_format, decor, manufacturer = row
    return BranchMaterialRecord(bm, decor_format, decor, manufacturer), scope


async def _decor_record(db: AsyncSession, decor_id: uuid.UUID) -> DecorRecord | None:
    # The same two derived counts the list carries — the admin detail page used
    # to read "0 ta filial" for a decor that two branches carried, because the
    # single read never computed usage. Formats are outer-joined through the
    # branch rows so a decor with no format still resolves.
    usage = (
        select(func.count(func.distinct(BranchMaterial.branch_id)))
        .select_from(DecorFormat)
        .join(BranchMaterial, BranchMaterial.decor_format_id == DecorFormat.id)
        .where(DecorFormat.decor_id == Decor.id)
        .correlate(Decor)
        .scalar_subquery()
    )
    row = (
        await db.execute(
            select(Decor, Manufacturer, usage, _active_format_count_subquery())
            .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
            .where(Decor.id == decor_id)
        )
    ).one_or_none()
    if row is None:
        return None
    decor, manufacturer, branch_usage, format_count = row
    return DecorRecord(
        decor=decor,
        manufacturer=manufacturer,
        branch_usage_count=int(branch_usage or 0),
        format_count=int(format_count or 0),
    )


async def _attachable_format_record(
    db: AsyncSession, decor_format_id: uuid.UUID
) -> DecorFormatRecord:
    """One active format of an active decor of an active manufacturer, or 4xx.

    Three separate refusals collapse into two codes on purpose: a branch that
    cannot see the decor at all gets "not found", while a decor it *can* see
    whose format the platform has retired gets a message it can act on.
    """

    row = (
        await db.execute(
            select(DecorFormat, Decor, Manufacturer)
            .join(Decor, Decor.id == DecorFormat.decor_id)
            .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
            .where(DecorFormat.id == decor_format_id)
        )
    ).one_or_none()
    if row is None:
        raise APIError(
            "decor_format_not_found",
            "Decor format not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    decor_format, decor, manufacturer = row
    if (
        decor_format.status is not MaterialStatus.ACTIVE
        or decor.status is not MaterialStatus.ACTIVE
        or manufacturer.status is not MaterialStatus.ACTIVE
    ):
        raise APIError(
            "decor_format_inactive",
            "This format is no longer offered",
            status_code=status.HTTP_409_CONFLICT,
            details={"decor_format_id": str(decor_format.id)},
        )
    return DecorFormatRecord(
        decor_format=decor_format,
        decor=decor,
        manufacturer=manufacturer,
    )


async def _find_decor_format(
    db: AsyncSession,
    *,
    decor_id: uuid.UUID,
    shape: DecorFormatShape,
) -> DecorFormat | None:
    """The natural-key lookup, mirroring `uq_decor_formats_natural_key`.

    Checked in Python as well as in the DB so the client gets a 409 naming the
    existing row rather than an IntegrityError 500 — and so SQLite, where the
    COALESCE expression index is the only enforcement, behaves the same.
    """

    row: DecorFormat | None = await db.scalar(
        select(DecorFormat).where(
            DecorFormat.decor_id == decor_id,
            DecorFormat.type == shape.type,
            DecorFormat.thickness_mm == shape.thickness_mm,
            func.coalesce(DecorFormat.length_mm, 0) == (shape.length_mm or 0),
            func.coalesce(DecorFormat.width_mm, 0) == (shape.width_mm or 0),
            func.coalesce(DecorFormat.tape_width_mm, 0) == (shape.tape_width_mm or 0),
            func.coalesce(DecorFormat.finished_sides, 0) == (shape.finished_sides or 0),
        )
    )
    return row


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


async def _ensure_decor_identity_available(
    db: AsyncSession,
    *,
    manufacturer_id: uuid.UUID,
    code: str | None,
    name: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """Mirror of the two partial unique indexes on `decors`.

    Checked here as well as in the DB because the indexes are `postgresql_where`
    and do not exist on SQLite, and because a 409 with a message beats an
    IntegrityError 500 either way. `type` is deliberately not part of this test
    any more — a board and its matching kromka are one decor now.
    """

    query = select(Decor.id).where(Decor.manufacturer_id == manufacturer_id)
    if code is not None:
        query = query.where(func.lower(Decor.code) == code.lower())
    else:
        query = query.where(Decor.code.is_(None), func.lower(Decor.name) == name.lower())
    if exclude_id is not None:
        query = query.where(Decor.id != exclude_id)
    if await db.scalar(query) is not None:
        raise APIError(
            "decor_exists",
            "This manufacturer already has a decor with that code",
            status_code=status.HTTP_409_CONFLICT,
        )


async def _recompute_search_keys_for_manufacturer(
    db: AsyncSession, manufacturer: Manufacturer
) -> None:
    rows = (await db.scalars(select(Decor).where(Decor.manufacturer_id == manufacturer.id))).all()
    for decor in rows:
        decor.search_key = _search_key(
            name=decor.name, code=decor.code, manufacturer_name=manufacturer.name
        )


# --------------------------------------------------------------------------- #
# Filters, paging, validation
# --------------------------------------------------------------------------- #

# Catalog list endpoints paginate with the house limit/offset convention
# (sales, inventory, audit): the caller opts in by passing a limit, the response
# stays a bare list, and the client infers "has more" from a full page. A None
# limit means unbounded — preserving the pre-pagination behavior for callers (and
# tests) that don't ask for a page. Ordering carries a Decor.id tiebreaker so
# offset paging is deterministic across requests.
DECORS_MAX_LIMIT = 200


def _bounded_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    return max(1, min(limit, DECORS_MAX_LIMIT))


def _paginate(query: Any, *, limit: int | None, offset: int) -> Any:
    bounded = _bounded_limit(limit)
    if bounded is None:
        return query
    return query.limit(bounded).offset(max(0, offset))


def _format_ordering() -> tuple[Any, ...]:
    """Active first, then substrate, thickness, size — how a price list reads."""

    return (
        DecorFormat.status,
        DecorFormat.type,
        DecorFormat.thickness_mm,
        DecorFormat.length_mm,
        DecorFormat.width_mm,
        DecorFormat.tape_width_mm,
        DecorFormat.id,
    )


def _active_format_count_subquery() -> Any:
    """How many active formats this decor has.

    `.correlate(Decor)` is load-bearing: `list_decors` already has
    `decor_formats` in its own FROM (it outer-joins through it to count carrying
    branches), and SQLAlchemy's auto-correlation would then correlate BOTH
    tables away and leave the subquery with no FROM clause at all. Naming the
    one table that may correlate pins it.
    """

    return (
        select(func.count(DecorFormat.id))
        .where(
            DecorFormat.decor_id == Decor.id,
            DecorFormat.status == MaterialStatus.ACTIVE,
        )
        .correlate(Decor)
        .scalar_subquery()
    )


def _has_active_format(types: list[DecorType] | None = None) -> Any:
    """`EXISTS (an active format of this decor[, of one of these types])`.

    What the decor-level `type` filter means now that a decor has no type of its
    own: "sells at least one active product of this substrate".
    """

    predicate = (
        select(DecorFormat.id)
        .where(
            DecorFormat.decor_id == Decor.id,
            DecorFormat.status == MaterialStatus.ACTIVE,
        )
        .correlate(Decor)
    )
    if types:
        predicate = predicate.where(DecorFormat.type.in_(types))
    return exists(predicate)


def _decor_filters(
    query: Any,
    *,
    search: str | None,
    manufacturer_id: uuid.UUID | None,
    status_filter: MaterialStatus | None,
    type_: DecorType | None = None,
    types: list[DecorType] | None = None,
    manufacturer_ids: list[uuid.UUID] | None = None,
) -> Any:
    wanted = [*([type_] if type_ is not None else []), *(types or [])]
    if wanted:
        query = query.where(_has_active_format(wanted))
    if manufacturer_id is not None:
        query = query.where(Decor.manufacturer_id == manufacturer_id)
    if manufacturer_ids:
        query = query.where(Decor.manufacturer_id.in_(manufacturer_ids))
    if status_filter is not None:
        query = query.where(Decor.status == status_filter)
    # ILIKEs over the folded key replace the old four-column OR: `сонома`,
    # `Sonoma` and `sonoma` all fold to the same string, which no per-column
    # ILIKE over the raw text could match.
    #
    # Tokenized and ANDed because `search_key` is a *concatenation* of name, code
    # and manufacturer with the separators folded away — "egger sonoma" as one
    # blob would never match "sonomah1334egger", so each word is matched on its
    # own and all of them must hit.
    for word in (search or "").split():
        folded = fold(word)
        if folded:
            query = query.where(Decor.search_key.ilike(f"%{folded}%"))
    return query


def _search_key(*, name: str, code: str | None, manufacturer_name: str) -> str:
    return fold(f"{name} {code or ''} {manufacturer_name}")


def validate_decor_format_shape(
    *,
    type_: DecorType,
    thickness_mm: Decimal | None,
    length_mm: int | None,
    width_mm: int | None,
    tape_width_mm: int | None,
    finished_sides: int | None,
) -> DecorFormatShape:
    """The panel/tape/finished-sides shape rule, with a named error per branch.

    The DB carries the same rule as `ck_decor_formats_shape`; this exists so the
    client gets a message it can put next to a field instead of a 500 out of an
    IntegrityError. It also normalizes orientation so a format is stored one way
    only.
    """

    if thickness_mm is None or thickness_mm <= 0:
        raise APIError(
            "decor_format_shape_mismatch",
            "Qalinlik noto'g'ri",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"field": "thickness_mm"},
        )
    thickness = normalize_mm(thickness_mm)
    if is_tape(type_):
        if length_mm is not None or width_mm is not None:
            raise APIError(
                "decor_format_shape_mismatch",
                "Kromka uchun uzunlik va eni kiritilmaydi",
                status_code=status.HTTP_400_BAD_REQUEST,
                details={"field": "length_mm"},
            )
        if finished_sides is not None:
            raise APIError(
                "decor_format_shape_mismatch",
                "Kromka uchun tomonlar soni kiritilmaydi",
                status_code=status.HTTP_400_BAD_REQUEST,
                details={"field": "finished_sides"},
            )
        if tape_width_mm is None or tape_width_mm <= 0:
            raise APIError(
                "decor_format_shape_mismatch",
                "Kromka eni kerak",
                status_code=status.HTTP_400_BAD_REQUEST,
                details={"field": "tape_width_mm"},
            )
        return DecorFormatShape(type_, thickness, None, None, tape_width_mm, None)
    if tape_width_mm is not None:
        raise APIError(
            "decor_format_shape_mismatch",
            "List uchun kromka eni kiritilmaydi",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"field": "tape_width_mm"},
        )
    if length_mm is None or width_mm is None or length_mm <= 0 or width_mm <= 0:
        raise APIError(
            "decor_format_shape_mismatch",
            "Uzunlik va eni kerak",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"field": "length_mm"},
        )
    if requires_finished_sides(type_):
        if finished_sides not in (1, 2):
            raise APIError(
                "decor_format_shape_mismatch",
                "Nechta tomoni qoplangan? 1 yoki 2",
                status_code=status.HTTP_400_BAD_REQUEST,
                details={"field": "finished_sides"},
            )
    elif finished_sides is not None:
        raise APIError(
            "decor_format_shape_mismatch",
            "Bu tur uchun tomonlar soni kiritilmaydi",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"field": "finished_sides"},
        )
    # Normalize rather than reject: 1830x2750 and 2750x1830 are the same sheet,
    # and the unique index compares the columns literally.
    length, width = max(length_mm, width_mm), min(length_mm, width_mm)
    return DecorFormatShape(type_, thickness, length, width, None, finished_sides)


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
