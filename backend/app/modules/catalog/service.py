"""Decor catalog, decor format and branch material use cases.

The split this module enforces: the *product* — the decor's identity (`decors`)
and every concrete format it is made in (`decor_formats`) — is one fact, while a
branch owns only the *commercial decision* (`branch_materials`: we carry this
format, at this price). Nothing on the platform surface may name a price.

Since 2026-09-07 the product half has two writers. The platform maintains a
**library** (`workshop_id IS NULL`) transcribed from manufacturer catalogs; a
workshop may add the manufacturer, decor or format the library lacks, and what it
adds is stamped with its `workshop_id` and visible only to itself. Every
workshop-facing read therefore carries the predicate
`workshop_id IS NULL OR workshop_id = :ws` on all three tables — see
`_owner_predicate`, which is the single spelling of it — and every platform read
carries `workshop_id IS NULL`. A row of another workshop does not exist for this
one: not listed, not attachable, and 404 rather than 403 by id, because the id
must not leak that something is there.
"""

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from fastapi import status
from sqlalchemy import ColumnElement, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.errors import APIError
from app.core.material_label import edge_label, material_label
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.core.search_fold import build_search_key, fold
from app.core.search_query import (
    SearchPlan,
    capped,
    rank_expression,
    run_search_tiers,
    search_predicate,
    trigram_predicate,
    trigram_rank_expression,
)
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
    WorkshopDecorCreateRequest,
    WorkshopDecorPatchRequest,
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


# --------------------------------------------------------------------------- #
# Ownership and visibility
# --------------------------------------------------------------------------- #


# Throughout this section a `workshop_id` of `None` means the platform reader:
# the library and nothing else.
def _owner_predicate(
    column: InstrumentedAttribute[uuid.UUID | None], workshop_id: uuid.UUID | None
) -> ColumnElement[bool]:
    """`visible_to(ws)` as SQL, over one table's `workshop_id`.

    The single spelling of the rule. A workshop reader sees the library plus its
    own rows; a platform reader (`workshop_id=None`) sees the library only, which
    is why the admin app never renders a workshop's private decor.
    """

    if workshop_id is None:
        return column.is_(None)
    return or_(column.is_(None), column == workshop_id)


def _decor_visibility(workshop_id: uuid.UUID | None) -> tuple[ColumnElement[bool], ...]:
    """The predicate for a query that has both `Decor` and `Manufacturer` in scope.

    Both halves are needed: a workshop's own decor of a library manufacturer is
    visible, a library decor of a foreign workshop's manufacturer cannot exist,
    and neither may leak the other way round.
    """

    return (
        _owner_predicate(Decor.workshop_id, workshop_id),
        _owner_predicate(Manufacturer.workshop_id, workshop_id),
    )


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
class WorkshopDecorCreateResult:
    """What one «Yangi dekor» save produced — the pattern and its first sizes.

    Returned together because the sheet moves straight to the price step with
    every one of these formats ticked; a second round trip to list them would
    show an empty step two for as long as it took.
    """

    decor: DecorRecord
    formats: list[DecorFormatRecord]


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


class BranchCatalogFacetScope(StrEnum):
    """Which set a facet enumerates — see `list_branch_catalog_facets`."""

    ATTACHABLE = "attachable"
    CARRIED = "carried"


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
    # The library only: a workshop's own manufacturer is that workshop's private
    # row, and the admin app has no screen — and no mandate — for it.
    query = (
        select(Manufacturer).where(Manufacturer.workshop_id.is_(None)).order_by(Manufacturer.name)
    )
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
    await _ensure_manufacturer_name_available(db, name=name, workshop_id=None)
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
        await _ensure_manufacturer_name_available(
            db, name=name, workshop_id=None, exclude_id=row.id
        )
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
            _active_format_count_subquery(None),
        )
        .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
        .outerjoin(DecorFormat, DecorFormat.decor_id == Decor.id)
        .outerjoin(
            BranchMaterial,
            and_(BranchMaterial.decor_format_id == DecorFormat.id),
        )
        .where(*_decor_visibility(None))
    )
    query = _decor_filters(
        query,
        workshop_id=None,
        type_=type_,
        types=types,
        manufacturer_id=manufacturer_id,
        manufacturer_ids=manufacturer_ids,
        status_filter=status_filter,
    ).group_by(Decor.id, Manufacturer.id)

    async def run(plan: SearchPlan) -> list[DecorRecord]:
        # A number reaches the formats through an EXISTS here: the platform list
        # is one table up from the dimensions, and `18` should still find the
        # decors sold in 18 mm.
        searched = apply_decor_search(
            query,
            plan,
            ordering=(Manufacturer.name, Decor.name, Decor.id),
            dimension_arms=decor_dimension_arms,
        )
        rows = (
            await db.execute(_paginate(searched, limit=capped(limit, plan.limit), offset=offset))
        ).all()
        return [
            DecorRecord(
                decor=decor,
                manufacturer=manufacturer,
                branch_usage_count=int(usage or 0),
                format_count=int(formats or 0),
            )
            for decor, manufacturer, usage, formats in rows
        ]

    return await run_search_tiers(db, search, run)


async def create_decor(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: DecorCreateRequest,
) -> DecorRecord:
    require_platform_operator(principal)
    manufacturer = await _active_manufacturer(db, payload.manufacturer_id, workshop_id=None)
    name = _required_text(payload.name, "decor_name_required")
    code = _optional_text(payload.code)
    await _ensure_decor_identity_available(
        db,
        manufacturer_id=manufacturer.id,
        code=code,
        name=name,
        workshop_id=None,
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
    # Library-scoped, so every platform write that resolves through here — patch,
    # activate, add a format — refuses a workshop's own decor with a 404 without
    # each of them repeating the check.
    record = await _decor_record(db, decor_id, workshop_id=None)
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
        manufacturer = await _active_manufacturer(db, payload.manufacturer_id, workshop_id=None)
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
        workshop_id=None,
        exclude_id=row.id,
    )
    # Recomputed unconditionally: every input to the key (name, code, maker) is
    # patchable, and an unchanged write costs one fold() call.
    await _recompute_decor_search_key(db, row, manufacturer.name)
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
    """Every library format of one decor, active first — the platform's own view.

    Library only: a workshop's own 16 mm hanging off this library decor is that
    workshop's private row, and the admin screen would otherwise offer to
    deactivate a format the platform never wrote.
    """

    record = await get_decor(db, principal=principal, decor_id=decor_id)
    rows = (
        await db.scalars(
            select(DecorFormat)
            .where(
                DecorFormat.decor_id == record.decor.id,
                DecorFormat.workshop_id.is_(None),
            )
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
    existing = await _find_decor_formats(
        db, decor_id=record.decor.id, shape=shape, workshop_id=None
    )
    if existing:
        raise APIError(
            "decor_format_exists",
            "This decor already has that format",
            status_code=status.HTTP_409_CONFLICT,
            details={"decor_format_id": str(existing[0].id)},
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
    await _recompute_search_key_after_format_write(db, record)
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
    if row is None or row.decor_id != record.decor.id or row.workshop_id is not None:
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
    await _recompute_search_key_after_format_write(db, record)
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
    filtered = _decor_filters(
        _attachable_decors_query(scope.workshop_id),
        workshop_id=scope.workshop_id,
        type_=type_,
        manufacturer_id=manufacturer_id,
        status_filter=None,
    )
    available = _active_format_count_subquery(scope.workshop_id)
    carried = (
        select(func.count(BranchMaterial.id))
        .join(DecorFormat, DecorFormat.id == BranchMaterial.decor_format_id)
        .where(
            BranchMaterial.branch_id == scope.branch_id,
            DecorFormat.decor_id == Decor.id,
            DecorFormat.status == MaterialStatus.ACTIVE,
            _owner_predicate(DecorFormat.workshop_id, scope.workshop_id),
        )
        .correlate(Decor)
        .scalar_subquery()
    )

    async def run(plan: SearchPlan) -> BranchCatalogOptionsPage:
        # The picker is a branch surface too: the operator is looking for a
        # product they can see on a price list, so `18` has to find the decors
        # sold in 18 mm — through an EXISTS, since the row here is a decor.
        searched = apply_decor_search(
            filtered,
            plan,
            ordering=(Manufacturer.name, Decor.name, Decor.id),
            dimension_arms=decor_dimension_arms,
        )
        # The total counts what this tier found, so the picker's "N of M" never
        # describes a tier the reader is not looking at.
        total = await db.scalar(searched.order_by(None).with_only_columns(func.count(Decor.id)))
        page = _paginate(
            searched.with_only_columns(Decor, Manufacturer, carried, available),
            limit=capped(limit, plan.limit),
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
                    await db.execute(page)
                ).all()
            ],
            total=int(total or 0),
        )

    return await run_search_tiers(db, search, run, empty=lambda page: not page.items)


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
    record = await _decor_record(db, decor_id, workshop_id=scope.workshop_id)
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
                _owner_predicate(DecorFormat.workshop_id, scope.workshop_id),
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
    scope: BranchCatalogFacetScope = BranchCatalogFacetScope.ATTACHABLE,
) -> BranchCatalogFacets:
    """Manufacturer values present in one of two sets, and they are not the same set.

    `ATTACHABLE` is the platform's offer — what the attach sheet may add — and is
    the default because that sheet asked first. `CARRIED` is what this branch
    already holds, which is the only honest set for a filter over the branch's
    own table: offering the platform's list there means dropdown options that
    return nothing.

    Either way the values are deliberately unfiltered by the surface's *other*
    filters: dropdown options that reshuffle as you pick from them are worse than
    a couple of empty results.
    """

    _require_workshop_user(principal)
    resolved = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    if scope is BranchCatalogFacetScope.CARRIED:
        query = (
            select(Manufacturer)
            .join(Decor, Decor.manufacturer_id == Manufacturer.id)
            .join(DecorFormat, DecorFormat.decor_id == Decor.id)
            .join(BranchMaterial, BranchMaterial.decor_format_id == DecorFormat.id)
            .where(BranchMaterial.branch_id == resolved.branch_id)
        )
    else:
        query = _attachable_decors_query(resolved.workshop_id).with_only_columns(Manufacturer)
    manufacturers = list(
        (await db.scalars(query.distinct().order_by(Manufacturer.name, Manufacturer.id))).all()
    )
    return BranchCatalogFacets(manufacturers=manufacturers)


def _attachable_decors_query(workshop_id: uuid.UUID | None) -> Any:
    """Visible active decors from active manufacturers with at least one format.

    A decor with no active *visible* format is a name nobody can attach anything
    of, so it is not an option — showing it would mean a two-step picker whose
    step two is empty.
    """

    return (
        select(Decor.id)
        .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
        .where(
            Decor.status == MaterialStatus.ACTIVE,
            Manufacturer.status == MaterialStatus.ACTIVE,
            *_decor_visibility(workshop_id),
            _has_active_format(workshop_id),
        )
    )


# --------------------------------------------------------------------------- #
# Workshop-owned catalog rows
# --------------------------------------------------------------------------- #
#
# What the library lacks, the workshop writes for itself. Every function here
# needs `MANAGE_CATALOG` on the branch, and the owning workshop is *the branch's*
# — never a request field, because a request field is an id one workshop could
# type to plant a row in another's catalog.


async def list_workshop_manufacturers(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
) -> list[Manufacturer]:
    """Visible active manufacturers, library first, then the workshop's own.

    Feeds the create form's combobox. The two groups are ordered rather than
    labelled here — the response carries `own` per row, and the reader wants the
    names it has seen on a price list before the names it typed itself.
    """

    _require_workshop_user(principal)
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    rows = await db.scalars(
        select(Manufacturer)
        .where(
            Manufacturer.status == MaterialStatus.ACTIVE,
            _owner_predicate(Manufacturer.workshop_id, scope.workshop_id),
        )
        .order_by(Manufacturer.workshop_id.is_not(None), Manufacturer.name, Manufacturer.id)
    )
    return list(rows.all())


async def create_workshop_decor(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    payload: WorkshopDecorCreateRequest,
) -> WorkshopDecorCreateResult:
    """A decor and its first formats, written by the workshop, in ONE transaction.

    The whole point of the form is that the operator does not wait: they name the
    maker (picking one, or typing a new one), the decor and at least one size,
    and the next screen is the price step. So it is one call — a decor with no
    format is a name nobody can attach anything of, and a half-written pair is
    exactly the state a two-call flow leaves behind when the second call fails.

    Nothing is written until every format has passed `validate_decor_format_shape`
    and the in-request duplicate check, so a bad third size leaves no decor, no
    manufacturer and no audit rows.
    """

    _require_workshop_user(principal)
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    name = _required_text(payload.name, "decor_name_required")
    code = _optional_text(payload.code)
    shapes = _validate_new_format_shapes(payload.formats)

    manufacturer, manufacturer_created = await _resolve_workshop_manufacturer(
        db,
        workshop_id=scope.workshop_id,
        manufacturer_id=payload.manufacturer_id,
        manufacturer_name=payload.manufacturer_name,
    )
    await _ensure_decor_identity_available(
        db,
        manufacturer_id=manufacturer.id,
        code=code,
        name=name,
        workshop_id=scope.workshop_id,
    )

    actor = actor_from_principal(principal)
    if manufacturer_created:
        await record_action(
            db,
            actor=actor,
            action="catalog.manufacturer.create",
            entity_type="manufacturer",
            entity_id=manufacturer.id,
            workshop_id=scope.workshop_id,
            branch_id=scope.branch_id,
            summary=f"Created manufacturer {manufacturer.name}",
            details={"workshop_owned": True},
        )

    decor = Decor(
        manufacturer_id=manufacturer.id,
        workshop_id=scope.workshop_id,
        code=code,
        name=name,
        has_grain=payload.has_grain,
        status=MaterialStatus.ACTIVE,
        search_key=_search_key(name=name, code=code, manufacturer_name=manufacturer.name),
    )
    db.add(decor)
    await db.flush()
    decor.image_file_id = await attach_file(
        db,
        principal=principal,
        file_id=payload.image_file_id,
        entity_type=_IMAGE_ENTITY_TYPE,
        entity_id=decor.id,
        allowed_content_types=IMAGE_CONTENT_TYPES,
    )
    await record_action(
        db,
        actor=actor,
        action="catalog.dekor.create",
        entity_type=_DECOR_ENTITY_TYPE,
        entity_id=decor.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Created decor {decor_label(decor, manufacturer)}",
        details={"manufacturer_id": str(manufacturer.id), "workshop_owned": True},
    )

    record = DecorRecord(decor=decor, manufacturer=manufacturer, format_count=len(shapes))
    formats = [
        await _write_workshop_format(db, actor=actor, record=record, scope=scope, shape=shape)
        for shape in shapes
    ]
    # After the formats, so the substrate words of the rows just written are in
    # the key: «ldsp oq yog'och» has to find the decor the operator just created.
    await _recompute_search_key_after_format_write(db, record)
    # Flush before the refresh: `refresh` re-reads the row and would otherwise
    # throw away the key that was just assigned in memory, silently — the decor
    # would be findable by name and never by substrate.
    await db.flush()
    await db.refresh(decor)
    return WorkshopDecorCreateResult(decor=record, formats=formats)


async def create_workshop_decor_format(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    decor_id: uuid.UUID,
    payload: DecorFormatCreateRequest,
) -> DecorFormatRecord:
    """One more size on any decor the branch can see — library or its own.

    The twin rule: if the shape already exists as an **active** visible format,
    the answer is a 409 naming that row, and the sheet ticks it instead of
    creating a second id for one physical product. An **inactive library** twin
    does not block — the platform discontinued it, the workshop still buys it —
    and the workshop gets its own row.
    """

    _require_workshop_user(principal)
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    record = await _decor_record(db, decor_id, workshop_id=scope.workshop_id)
    if record is None:
        raise APIError(
            "decor_not_found",
            "Decor not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
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
    twins = await _find_decor_formats(
        db, decor_id=record.decor.id, shape=shape, workshop_id=scope.workshop_id
    )
    blocking = next(
        (
            twin
            for twin in twins
            # An active twin of either owner is attachable, so it is the answer.
            # A retired *own* twin blocks too: there is nothing to attach and
            # nothing to create — the workshop already wrote this shape once, and
            # a format's status is not editable in this release.
            if twin.status is MaterialStatus.ACTIVE or twin.workshop_id is not None
        ),
        None,
    )
    if blocking is not None:
        raise APIError(
            "decor_format_exists",
            "This decor already has that format",
            status_code=status.HTTP_409_CONFLICT,
            details={"decor_format_id": str(blocking.id)},
        )
    row = await _write_workshop_format(
        db,
        actor=actor_from_principal(principal),
        record=record,
        scope=scope,
        shape=shape,
    )
    await _recompute_search_key_after_format_write(db, record)
    return row


async def update_workshop_decor(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    branch_id: uuid.UUID,
    decor_id: uuid.UUID,
    payload: WorkshopDecorPatchRequest,
) -> DecorRecord:
    """Fix a decor this workshop wrote. Its formats stay immutable.

    Two refusals, deliberately different: a **library** decor is 403
    `decor_not_owned` — the operator can see the row, so the honest answer is
    "not yours" — while another workshop's decor is 404, because admitting the id
    resolves would leak that it exists.
    """

    _require_workshop_user(principal)
    scope = await resolve_branch_scope(
        db,
        principal,
        branch_id=branch_id,
        permission=Permission.MANAGE_CATALOG,
    )
    record = await _decor_record(db, decor_id, workshop_id=scope.workshop_id)
    if record is None:
        raise APIError(
            "decor_not_found",
            "Decor not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if record.decor.workshop_id is None:
        raise APIError(
            "decor_not_owned",
            "This decor belongs to the platform library",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    row = record.decor
    manufacturer = record.manufacturer
    fields = payload.model_fields_set
    if "manufacturer_id" in fields or "manufacturer_name" in fields:
        manufacturer, created = await _resolve_workshop_manufacturer(
            db,
            workshop_id=scope.workshop_id,
            manufacturer_id=payload.manufacturer_id,
            manufacturer_name=payload.manufacturer_name,
        )
        row.manufacturer_id = manufacturer.id
        if created:
            await record_action(
                db,
                actor=actor_from_principal(principal),
                action="catalog.manufacturer.create",
                entity_type="manufacturer",
                entity_id=manufacturer.id,
                workshop_id=scope.workshop_id,
                branch_id=scope.branch_id,
                summary=f"Created manufacturer {manufacturer.name}",
                details={"workshop_owned": True},
            )
    if "name" in fields and payload.name is not None:
        row.name = _required_text(payload.name, "decor_name_required")
    if "code" in fields:
        row.code = _optional_text(payload.code)
    if "has_grain" in fields and payload.has_grain is not None:
        row.has_grain = payload.has_grain
    if "image_file_id" in fields:
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
        workshop_id=scope.workshop_id,
        exclude_id=row.id,
    )
    await _recompute_decor_search_key(db, row, manufacturer.name)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="catalog.dekor.update",
        entity_type=_DECOR_ENTITY_TYPE,
        entity_id=row.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Updated decor {decor_label(row, manufacturer)}",
        details={"workshop_owned": True},
    )
    await db.refresh(row)
    return DecorRecord(
        decor=row,
        manufacturer=manufacturer,
        branch_usage_count=record.branch_usage_count,
        format_count=record.format_count,
    )


async def _resolve_workshop_manufacturer(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    manufacturer_id: uuid.UUID | None,
    manufacturer_name: str | None,
) -> tuple[Manufacturer, bool]:
    """Pick a visible manufacturer, or mint the workshop's own. Returns (row, created).

    Exactly one of the two inputs, because "both" has no honest reading: it would
    silently ignore one of the two things the operator said.

    A typed name is matched on the **folded** key, not on `lower()`: «Kastamonu»,
    «kastamonu» and «Қастамону» are one maker, and letting them become three
    would split the workshop's own catalog by keyboard layout. The library is
    searched before the workshop's own rows, so the first typist to name a maker
    the platform already lists reuses it instead of forking it.
    """

    typed = _optional_text(manufacturer_name)
    if (manufacturer_id is None) == (typed is None):
        raise APIError(
            "manufacturer_required",
            "Ishlab chiqaruvchini tanlang yoki nomini kiriting",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if manufacturer_id is not None:
        return await _active_manufacturer(db, manufacturer_id, workshop_id=workshop_id), False

    assert typed is not None
    wanted = fold(typed)
    candidates = await db.scalars(
        select(Manufacturer)
        .where(
            Manufacturer.status == MaterialStatus.ACTIVE,
            _owner_predicate(Manufacturer.workshop_id, workshop_id),
        )
        .order_by(Manufacturer.workshop_id.is_not(None), Manufacturer.name, Manufacturer.id)
    )
    for candidate in candidates.all():
        if fold(candidate.name) == wanted:
            return candidate, False
    await _ensure_manufacturer_name_available(db, name=typed, workshop_id=workshop_id)
    row = Manufacturer(name=typed, workshop_id=workshop_id, status=MaterialStatus.ACTIVE)
    db.add(row)
    await db.flush()
    return row, True


def _validate_new_format_shapes(
    payloads: Sequence[DecorFormatCreateRequest],
) -> list[DecorFormatShape]:
    """Every requested format, validated and normalized, before anything is written.

    Duplicates are refused rather than collapsed: two identical rows in the list
    mean the operator lost track of what they had added, and silently keeping one
    would leave the price step showing fewer sizes than they typed.
    """

    if not payloads:
        raise APIError(
            "decor_formats_required",
            "Kamida bitta o'lcham qo'shing",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    shapes: list[DecorFormatShape] = []
    for payload in payloads:
        shape = validate_decor_format_shape(
            type_=payload.type,
            thickness_mm=payload.thickness_mm,
            length_mm=payload.length_mm,
            width_mm=payload.width_mm,
            tape_width_mm=payload.tape_width_mm,
            finished_sides=payload.finished_sides,
        )
        if shape in shapes:
            raise APIError(
                "decor_format_duplicate_in_request",
                "Bu o'lcham allaqachon ro'yxatda",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        shapes.append(shape)
    return shapes


async def _write_workshop_format(
    db: AsyncSession,
    *,
    actor: Any,
    record: DecorRecord,
    scope: BranchScope,
    shape: DecorFormatShape,
) -> DecorFormatRecord:
    """One workshop-owned `decor_formats` row plus its audit line."""

    row = DecorFormat(
        decor_id=record.decor.id,
        workshop_id=scope.workshop_id,
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
        actor=actor,
        action="catalog.decor_format.create",
        entity_type=_DECOR_FORMAT_ENTITY_TYPE,
        entity_id=row.id,
        workshop_id=scope.workshop_id,
        branch_id=scope.branch_id,
        summary=f"Created format {decor_format_label(row, record.decor, record.manufacturer)}",
        details={
            "decor_id": str(record.decor.id),
            "type": row.type.value,
            "workshop_owned": True,
        },
    )
    return DecorFormatRecord(
        decor_format=row,
        decor=record.decor,
        manufacturer=record.manufacturer,
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
    query = branch_material_join().where(BranchMaterial.branch_id == scope.branch_id)
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
        # The branch's own rows, so nothing here needs the visibility predicate:
        # a `branch_materials` row can only exist for a format this workshop was
        # allowed to attach, and filtering one out would hide a row its stock,
        # panels and order items still point at.
        workshop_id=scope.workshop_id,
        manufacturer_id=manufacturer_id,
        status_filter=None,
    )

    async def run(plan: SearchPlan) -> list[BranchMaterialRecord]:
        # The join already carries the format, so a token may be an o'lcham
        # number matched on the row itself rather than through an EXISTS.
        searched = apply_decor_search(
            query,
            plan,
            ordering=(
                Manufacturer.name,
                Decor.name,
                DecorFormat.thickness_mm,
                BranchMaterial.id,
            ),
            dimension_arms=format_dimension_arms,
        )
        rows = (
            await db.execute(_paginate(searched, limit=capped(limit, plan.limit), offset=offset))
        ).all()
        return [
            BranchMaterialRecord(
                branch_material=bm,
                decor_format=decor_format,
                decor=decor,
                manufacturer=manufacturer,
            )
            for bm, decor_format, decor, manufacturer in rows
        ]

    return await run_search_tiers(db, search, run)


def apply_decor_search(
    query: Any,
    plan: SearchPlan,
    *,
    ordering: Sequence[Any] = (),
    dimension_arms: Callable[[str], Sequence[Any]] | None = None,
) -> Any:
    """Filter and order one tier of a search over a query that has `Decor` in scope.

    The one place a catalog surface meets `app/core/search_query.py`. Every
    consumer — the platform decor list, the branch table, the attach picker,
    inventory, both client pickers — hands its base query, the plan the tier
    ladder handed it, and its own ordering; relevance is prepended to that
    ordering so a search re-sorts the list and an empty search leaves it exactly
    as the surface wrote it.

    `dimension_arms` is what the surface lets a *number* mean, and it differs by
    how far the row is from `decor_formats`: on a branch row the format is
    joined and matched directly, on a decor list it is an EXISTS. Surfaces pass
    the matching helper below.
    """

    if not plan.active:
        return query.order_by(*ordering) if ordering else query
    typed = plan.query or ""
    if plan.fuzzy:
        # Numbers do not have typos: the fuzzy tier is text-only, and a query
        # that folds to nothing has nothing to be close to.
        predicate = trigram_predicate(typed, Decor.search_key)
        if predicate is None:
            return query.order_by(*ordering) if ordering else query
        return query.where(predicate).order_by(
            trigram_rank_expression(typed, Decor.search_key).desc(), *ordering
        )
    predicate = search_predicate(typed, Decor.search_key, dimension_arms=dimension_arms)
    if predicate is not None:
        query = query.where(predicate)
    return query.order_by(rank_expression(typed, Decor.search_key, Decor.code), *ordering)


def format_dimension_arms(word: str) -> list[Any]:
    """The `DecorFormat` columns a search token can equal, read as millimetres.

    For the surfaces whose row **is** a format — the branch table, inventory,
    both client pickers: the o'lcham line is most of what the reader sees, so
    the number they can see is the number they can type.

    Matched by **value**, not as a substring: `18` is a thickness or a tape
    width, never part of `1830`, which a `LIKE '%18%'` could not tell apart. The
    three length columns are integer millimetres, so a fractional token can only
    ever have been a thickness (`0.4` kromka). A `2800x2070` pair matches a sheet
    of that size in either orientation.
    """

    pair = _as_dimension_pair(word)
    if pair is not None:
        first, second = pair
        return [
            or_(
                and_(DecorFormat.length_mm == first, DecorFormat.width_mm == second),
                and_(DecorFormat.length_mm == second, DecorFormat.width_mm == first),
            )
        ]
    number = _as_dimension(word)
    if number is None:
        return []
    arms: list[Any] = [DecorFormat.thickness_mm == number]
    if number == number.to_integral_value():
        whole = int(number)
        arms.append(DecorFormat.length_mm == whole)
        arms.append(DecorFormat.width_mm == whole)
        arms.append(DecorFormat.tape_width_mm == whole)
    return arms


def decor_dimension_arms(word: str) -> list[Any]:
    """`format_dimension_arms` as *"has an active format like that"*.

    For the surfaces that list decors — the platform list and the attach picker
    — where the numbers live one table down and cannot be matched on the row
    itself. «sonoma 18» finds the decors that are both Sonoma and sold in 18 mm,
    and the picker's step two then lists every format so the 18 mm one can be
    ticked.
    """

    arms = format_dimension_arms(word)
    if not arms:
        return []
    return [
        exists(
            select(DecorFormat.id)
            .where(
                DecorFormat.decor_id == Decor.id,
                DecorFormat.status == MaterialStatus.ACTIVE,
                or_(*arms),
            )
            .correlate(Decor)
        )
    ]


def _as_dimension(word: str) -> Decimal | None:
    """A search token read as a millimetre value, or None if it is not one.

    A comma is accepted for the decimal mark — the operator's keyboard and the
    Russian locale both produce `0,4`.
    """

    try:
        value = Decimal(word.replace(",", "."))
    except InvalidOperation:
        return None
    return value if value > 0 and value.is_finite() else None


# The four ways a sheet size gets typed: the Latin `x`, the multiplication sign
# a price list prints, the asterisk a spreadsheet does, and Cyrillic HA -- the
# same physical key, on the layout half the workshop types in.
_DIMENSION_PAIR_SEPARATORS = "x\u00d7*\u0445"


def _as_dimension_pair(word: str) -> tuple[int, int] | None:
    """`2800x2070` read as a sheet size, or None if it is not one."""

    lowered = word.casefold()
    for separator in _DIMENSION_PAIR_SEPARATORS:
        if lowered.count(separator) != 1:
            continue
        left, right = lowered.split(separator)
        first, second = _as_dimension(left), _as_dimension(right)
        if first is None or second is None:
            continue
        if first != first.to_integral_value() or second != second.to_integral_value():
            continue
        return int(first), int(second)
    return None


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
    validated: list[tuple[DecorFormatRecord, int]] = []
    seen: set[uuid.UUID] = set()
    for item in payload.items:
        record = await _attachable_format_record(
            db, item.decor_format_id, workshop_id=scope.workshop_id
        )
        label = decor_format_label(record.decor_format, record.decor, record.manufacturer)
        _validate_price(item.price_tiyin, label=label)
        if item.decor_format_id in seen:
            raise APIError(
                "branch_material_duplicate",
                f"«{label}» ikki marta kiritilgan",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        seen.add(item.decor_format_id)
        validated.append((record, item.price_tiyin))

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
    for record, price_tiyin in validated:
        if record.decor_format.id in carried:
            skipped.append(record.decor_format.id)
            continue
        row = BranchMaterial(
            branch_id=scope.branch_id,
            decor_format_id=record.decor_format.id,
            price_tiyin=price_tiyin,
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
    """Price only.

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


async def _decor_record(
    db: AsyncSession, decor_id: uuid.UUID, *, workshop_id: uuid.UUID | None
) -> DecorRecord | None:
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
            select(Decor, Manufacturer, usage, _active_format_count_subquery(workshop_id))
            .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
            .where(Decor.id == decor_id, *_decor_visibility(workshop_id))
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
    db: AsyncSession, decor_format_id: uuid.UUID, *, workshop_id: uuid.UUID
) -> DecorFormatRecord:
    """One visible active format of an active decor of an active manufacturer, or 4xx.

    Three separate refusals collapse into two codes on purpose: a branch that
    cannot see the decor at all gets "not found", while a decor it *can* see
    whose format has been retired gets a message it can act on. Another
    workshop's format takes the first door — `decor_format_not_found`, never a
    403, so the id does not confirm that a row is there.
    """

    row = (
        await db.execute(
            select(DecorFormat, Decor, Manufacturer)
            .join(Decor, Decor.id == DecorFormat.decor_id)
            .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
            .where(
                DecorFormat.id == decor_format_id,
                _owner_predicate(DecorFormat.workshop_id, workshop_id),
                *_decor_visibility(workshop_id),
            )
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


async def _find_decor_formats(
    db: AsyncSession,
    *,
    decor_id: uuid.UUID,
    shape: DecorFormatShape,
    workshop_id: uuid.UUID | None,
) -> list[DecorFormat]:
    """Every *visible* row with this natural key, mirroring the two unique indexes.

    Checked in Python as well as in the DB so the client gets a 409 naming the
    existing row rather than an IntegrityError 500 — and so SQLite, where the
    COALESCE expression index is the only enforcement, behaves the same.

    A list rather than one row because a workshop reader can legitimately see two
    of them: a retired library format and its own live replacement. Scoped by
    visibility, so a foreign workshop's identically-shaped format neither blocks
    nor gets named in the 409. Active first, so a caller taking the head takes
    the live twin.
    """

    rows = await db.scalars(
        select(DecorFormat)
        .where(
            DecorFormat.decor_id == decor_id,
            DecorFormat.type == shape.type,
            DecorFormat.thickness_mm == shape.thickness_mm,
            func.coalesce(DecorFormat.length_mm, 0) == (shape.length_mm or 0),
            func.coalesce(DecorFormat.width_mm, 0) == (shape.width_mm or 0),
            func.coalesce(DecorFormat.tape_width_mm, 0) == (shape.tape_width_mm or 0),
            func.coalesce(DecorFormat.finished_sides, 0) == (shape.finished_sides or 0),
            _owner_predicate(DecorFormat.workshop_id, workshop_id),
        )
        .order_by((DecorFormat.status != MaterialStatus.ACTIVE), DecorFormat.id)
    )
    return list(rows.all())


async def _active_manufacturer(
    db: AsyncSession, manufacturer_id: uuid.UUID, *, workshop_id: uuid.UUID | None
) -> Manufacturer:
    """One visible, active manufacturer by id, or 404.

    Another workshop's maker is 404 rather than 403 for the same reason a foreign
    decor is: the id must not confirm that a row exists.
    """

    row = await db.scalar(
        select(Manufacturer).where(
            Manufacturer.id == manufacturer_id,
            _owner_predicate(Manufacturer.workshop_id, workshop_id),
        )
    )
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
    workshop_id: uuid.UUID | None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """Mirror of the two ownership arms of the manufacturer name index.

    Scoped, not global: a workshop that entered «Kastamonu» of its own must not
    stop the platform adding Kastamonu to the library later, and vice versa.
    """

    query = select(Manufacturer.id).where(
        func.lower(Manufacturer.name) == name.lower(),
        Manufacturer.workshop_id.is_(None)
        if workshop_id is None
        else Manufacturer.workshop_id == workshop_id,
    )
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
    workshop_id: uuid.UUID | None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """Mirror of the four partial unique indexes on `decors`.

    Checked here as well as in the DB because the predicates do not survive on
    every dialect, and because a 409 with a message beats an IntegrityError 500
    either way. `type` is deliberately not part of this test — a board and its
    matching kromka are one decor now.

    Scoped to one ownership arm: a workshop's own «Egger · H1145» and the
    library's are two rows by design, and neither may refuse the other.
    """

    query = (
        select(Decor, Manufacturer)
        .join(Manufacturer, Manufacturer.id == Decor.manufacturer_id)
        .where(
            Decor.manufacturer_id == manufacturer_id,
            Decor.workshop_id.is_(None)
            if workshop_id is None
            else Decor.workshop_id == workshop_id,
        )
    )
    if code is not None:
        query = query.where(func.lower(Decor.code) == code.lower())
    else:
        query = query.where(Decor.code.is_(None), func.lower(Decor.name) == name.lower())
    if exclude_id is not None:
        query = query.where(Decor.id != exclude_id)
    existing = (await db.execute(query)).first()
    if existing is not None:
        # The label rides along so the form can say WHICH decor is in the way —
        # «Bunday dekor bor: Egger H1145 · Sonoma» — instead of a bare refusal
        # the operator has to go hunting through the picker to explain.
        clash, clash_manufacturer = existing
        raise APIError(
            "decor_exists",
            "This manufacturer already has a decor with that code",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "decor_id": str(clash.id),
                "decor_label": decor_label(clash, clash_manufacturer),
            },
        )


async def _decor_type_words(db: AsyncSession, decor_id: uuid.UUID) -> list[str]:
    """The substrate words one decor's active formats put into its search key."""

    types = (
        await db.scalars(
            select(DecorFormat.type)
            .where(
                DecorFormat.decor_id == decor_id,
                DecorFormat.status == MaterialStatus.ACTIVE,
            )
            .distinct()
        )
    ).all()
    return sorted(row.value for row in types)


async def _recompute_decor_search_key(
    db: AsyncSession, decor: Decor, manufacturer_name: str
) -> None:
    decor.search_key = _search_key(
        name=decor.name,
        code=decor.code,
        manufacturer_name=manufacturer_name,
        type_words=await _decor_type_words(db, decor.id),
    )


async def _recompute_search_key_after_format_write(db: AsyncSession, record: DecorRecord) -> None:
    """A format write can change the decor's substrate set — so it rebuilds the key.

    Creating the decor's first LDSP format is what makes «ldsp sonoma» find it,
    and deactivating the last one is what should stop it. Flushed first so the
    format row the key is computed from is the one the caller just wrote.
    """

    await db.flush()
    await _recompute_decor_search_key(db, record.decor, record.manufacturer.name)


async def _recompute_search_keys_for_manufacturer(
    db: AsyncSession, manufacturer: Manufacturer
) -> None:
    rows = (await db.scalars(select(Decor).where(Decor.manufacturer_id == manufacturer.id))).all()
    for decor in rows:
        await _recompute_decor_search_key(db, decor, manufacturer.name)


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


def _active_format_count_subquery(workshop_id: uuid.UUID | None) -> Any:
    """How many *visible* active formats this decor has.

    Visibility is load-bearing here rather than cosmetic: without it a library
    decor would report a foreign workshop's private 16 mm as "available", and the
    picker would offer a step two that lists nothing.

    `.correlate(Decor)` is load-bearing too: `list_decors` already has
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
            _owner_predicate(DecorFormat.workshop_id, workshop_id),
        )
        .correlate(Decor)
        .scalar_subquery()
    )


def _has_active_format(workshop_id: uuid.UUID | None, types: list[DecorType] | None = None) -> Any:
    """`EXISTS (a visible active format of this decor[, of one of these types])`.

    What the decor-level `type` filter means now that a decor has no type of its
    own: "sells at least one active product of this substrate".
    """

    predicate = (
        select(DecorFormat.id)
        .where(
            DecorFormat.decor_id == Decor.id,
            DecorFormat.status == MaterialStatus.ACTIVE,
            _owner_predicate(DecorFormat.workshop_id, workshop_id),
        )
        .correlate(Decor)
    )
    if types:
        predicate = predicate.where(DecorFormat.type.in_(types))
    return exists(predicate)


def _decor_filters(
    query: Any,
    *,
    workshop_id: uuid.UUID | None,
    manufacturer_id: uuid.UUID | None,
    status_filter: MaterialStatus | None,
    type_: DecorType | None = None,
    types: list[DecorType] | None = None,
    manufacturer_ids: list[uuid.UUID] | None = None,
) -> Any:
    """The non-search decor filters. Search is `apply_decor_search`'s job — it
    runs per tier, and the tier ladder is above these filters, not inside them.

    `workshop_id` scopes only the format EXISTS the `type` filter reaches
    through; the decor and manufacturer halves of the visibility predicate belong
    to the caller's base query, which is where the two tables are joined."""

    wanted = [*([type_] if type_ is not None else []), *(types or [])]
    if wanted:
        query = query.where(_has_active_format(workshop_id, wanted))
    if manufacturer_id is not None:
        query = query.where(Decor.manufacturer_id == manufacturer_id)
    if manufacturer_ids:
        query = query.where(Decor.manufacturer_id.in_(manufacturer_ids))
    if status_filter is not None:
        query = query.where(Decor.status == status_filter)
    return query


def _search_key(
    *,
    name: str,
    code: str | None,
    manufacturer_name: str,
    type_words: Sequence[str] = (),
) -> str:
    """`decors.search_key` — the decor's identity plus the substrates it sells in.

    The type words are the `DecorType` values of the decor's **active** formats,
    which is what makes «лдсп» and «ldsp sonoma» work on a table whose rows carry
    no substrate of their own any more. They are a fact about the formats, not
    about the decor, so the key is rebuilt whenever a format is created or its
    status changes as well as on every decor write and manufacturer rename.
    """

    return build_search_key(name, code, manufacturer_name, *type_words)


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


def _validate_price(price_tiyin: int, *, label: str) -> None:
    """The attach row's one number.

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
