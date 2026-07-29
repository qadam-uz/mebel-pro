"""2D-Place ``.map`` import adapter for the cutting wizard."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.modules.cutting.imports.base import (
    MAX_IMPORT_PIECES,
    ImportEdgeMaterialGroup,
    ImportedPart,
    ImportMapLayout,
    ImportMapMaterialGroup,
    ImportMapPartRow,
    ImportMapPlacement,
    ImportMapSheet,
    ImportPanelMaterialGroup,
    ImportParsedResponse,
    ImportParseError,
)
from app.modules.cutting.imports.common import distinct_key
from app.modules.cutting.imports.map_parser import MapFile, MapParseError, MapRecord, parse_map_file

EdgeFlags = tuple[bool, bool, bool, bool]


@dataclass
class _PartAggregate:
    part_ref: str
    material_key: str
    name: str
    length_mm: int
    width_mm: int
    edges: EdgeFlags
    quantity: int = 0


def parse_map_2dplace(content: bytes, filename: str | None = None) -> ImportParsedResponse:
    try:
        parsed = parse_map_file(content, filename)
    except MapParseError as exc:
        raise ImportParseError("invalid_map_file", "2D-Place MAP faylni o'qib bo'lmadi") from exc
    return _to_import_response(parsed)


def _to_import_response(map_file: MapFile) -> ImportParsedResponse:
    material_key_by_size: dict[tuple[int, int], str] = {}
    material_sheet_counts: dict[str, int] = {}
    aggregates: dict[tuple[str, tuple[int, int], EdgeFlags, str], _PartAggregate] = {}
    placement_indexes: dict[str, int] = {}
    sheets: list[ImportMapSheet] = []
    has_edges = False

    for sheet_index, sheet in enumerate(map_file.sheets, start=1):
        material_key = _material_key(material_key_by_size, sheet.width_mm, sheet.height_mm)
        material_sheet_counts[material_key] = material_sheet_counts.get(material_key, 0) + 1
        placements: list[ImportMapPlacement] = []
        parts_area = 0
        waste_count = 0
        remainder_count = 0

        for record in sheet.records:
            edges = _edges_dict(record.edges)
            if record.is_waste:
                waste_count += 1
                if record.is_remainder:
                    remainder_count += 1
                placements.append(
                    ImportMapPlacement(
                        sheet_index=sheet_index,
                        sheet_name=sheet.name,
                        material_key=material_key,
                        x_mm=record.x,
                        y_mm=record.y,
                        length_mm=record.width,
                        width_mm=record.height,
                        name="",
                        edges=edges,
                        is_waste=True,
                        is_remainder=record.is_remainder,
                    )
                )
                continue

            has_edges = has_edges or any(record.edges)
            aggregate = _aggregate_for(aggregates, record, material_key)
            aggregate.quantity += 1
            placement_indexes[aggregate.part_ref] = placement_indexes.get(aggregate.part_ref, 0) + 1
            quantity_index = placement_indexes[aggregate.part_ref]
            parts_area += record.width * record.height
            placements.append(
                ImportMapPlacement(
                    sheet_index=sheet_index,
                    sheet_name=sheet.name,
                    material_key=material_key,
                    x_mm=record.x,
                    y_mm=record.y,
                    length_mm=record.width,
                    width_mm=record.height,
                    name=record.name,
                    edges=edges,
                    is_waste=False,
                    is_remainder=False,
                    part_ref=aggregate.part_ref,
                    part_quantity_index=quantity_index,
                    rotated=record.width == aggregate.width_mm
                    and record.height == aggregate.length_mm
                    and aggregate.length_mm != aggregate.width_mm,
                )
            )

        sheet_area = sheet.width_mm * sheet.height_mm
        sheets.append(
            ImportMapSheet(
                sheet_index=sheet_index,
                name=sheet.name,
                material_key=material_key,
                width_mm=sheet.width_mm,
                height_mm=sheet.height_mm,
                placements=placements,
                parts_count=sum(1 for placement in placements if not placement.is_waste),
                waste_count=waste_count,
                remainder_count=remainder_count,
                parts_area_mm2=parts_area,
                fill_percentage=round((parts_area / sheet_area) * 100, 2) if sheet_area else 0,
            )
        )

    total_pieces = sum(aggregate.quantity for aggregate in aggregates.values())
    if total_pieces > MAX_IMPORT_PIECES:
        raise ImportParseError(
            "too_many_parts",
            f"Faylda {total_pieces} dona detal — bir optimallashtirishga eng ko'pi 300 dona. "
            "Faylni bo'lib yuklang",
            details={"total_pieces": total_pieces},
        )

    material_groups = [
        ImportMapMaterialGroup(
            key=key,
            label=_material_label(width, height, map_file.order_type),
            width_mm=width,
            height_mm=height,
            sheet_count=material_sheet_counts[key],
            hint=map_file.order_type or None,
        )
        for (width, height), key in material_key_by_size.items()
    ]
    part_rows = [
        ImportMapPartRow(
            row=index,
            part_ref=aggregate.part_ref,
            material_key=aggregate.material_key,
            length_mm=aggregate.length_mm,
            width_mm=aggregate.width_mm,
            quantity=aggregate.quantity,
            follow_grain=True,
            edges=_edges_dict(aggregate.edges),
            name=aggregate.name,
        )
        for index, aggregate in enumerate(aggregates.values(), start=1)
    ]

    edge_materials = (
        [ImportEdgeMaterialGroup(key="e1", label="MAP fayldagi kromkalar", side_count=0)]
        if has_edges
        else []
    )
    if edge_materials:
        edge_materials[0].side_count = sum(
            sum(1 for selected in aggregate.edges if selected) * aggregate.quantity
            for aggregate in aggregates.values()
        )

    return ImportParsedResponse(
        source_format="map_2dplace",
        parts=[
            ImportedPart(
                row=index,
                length_mm=aggregate.length_mm,
                width_mm=aggregate.width_mm,
                quantity=aggregate.quantity,
                material_key=aggregate.material_key,
                follow_grain=True,
                edges={
                    side: "e1" if selected and has_edges else None
                    for side, selected in _edges_dict(aggregate.edges).items()
                },
            )
            for index, aggregate in enumerate(aggregates.values(), start=1)
        ],
        panel_materials=[
            ImportPanelMaterialGroup(
                key=group.key,
                label=group.label,
                part_count=sum(1 for row in part_rows if row.material_key == group.key),
                thickness_hint=None,
            )
            for group in material_groups
        ],
        edge_materials=edge_materials,
        skipped_rows=[],
        warnings=[],
        material_groups=material_groups,
        map_layout=ImportMapLayout(
            description=map_file.description,
            customer_name=map_file.customer_name,
            order_type=map_file.order_type,
            sheets=sheets,
            part_rows=part_rows,
        ),
        total_parts=len(aggregates),
        total_pieces=total_pieces,
    )


def _aggregate_for(
    aggregates: dict[tuple[str, tuple[int, int], EdgeFlags, str], _PartAggregate],
    record: MapRecord,
    material_key: str,
) -> _PartAggregate:
    name = record.name or f"{record.width}x{record.height}"
    unordered_size = (
        min(record.width, record.height),
        max(record.width, record.height),
    )
    key = (distinct_key(name), unordered_size, record.edges, material_key)
    aggregate = aggregates.get(key)
    if aggregate is not None:
        return aggregate
    aggregate = _PartAggregate(
        part_ref=f"map-{len(aggregates) + 1}",
        material_key=material_key,
        name=name,
        length_mm=record.width,
        width_mm=record.height,
        edges=record.edges,
    )
    aggregates[key] = aggregate
    return aggregate


def _material_key(keys: dict[tuple[int, int], str], width: int, height: int) -> str:
    size = (width, height)
    existing = keys.get(size)
    if existing is not None:
        return existing
    key = f"m{len(keys) + 1}"
    keys[size] = key
    return key


def _material_label(width: int, height: int, hint: str) -> str:
    base = f"{width}x{height} mm list"
    return f"{base} · {hint}" if hint else base


def _edges_dict(edges: EdgeFlags) -> dict[str, bool]:
    top, bottom, left, right = edges
    return {"top": top, "bottom": bottom, "left": left, "right": right}


# 2D-Place's MAP format carries no explicit kerf/edge-trim field (map_parser.py
# reads only description, sheet size, record coordinates, waste/remainder
# flags, and edge codes) — but both are implicit in how the layout was already
# spaced when it was placed. These mirror the branch kerf_mm/edge_trim_mm
# bounds (app/modules/workshop/schemas.py BranchCreateRequest/BranchPatchRequest)
# — a derived value outside them is untrustworthy noise, not a real cut parameter.
_KERF_MM_MIN = 1
_KERF_MM_MAX = 20
_EDGE_TRIM_MM_MIN = 0
_EDGE_TRIM_MM_MAX = 50


def derive_map_cut_params(layout: ImportMapLayout) -> tuple[int, int]:
    """Recover (kerf_mm, edge_trim_mm) from an imported MAP layout's geometry.

    Kerf is the small gap 2D-Place left between two adjacent real parts;
    edge trim is the margin it kept from the raw sheet edge before placing
    anything. Both are recovered as the single most common value across the
    *whole* imported layout (every sheet, not one) — a one-off 1 mm/3 mm
    stray gap must not outvote the dominant 4 mm seen elsewhere in the same
    file. Waste/remainder rectangles are excluded from both measurements;
    only real parts define kerf and trim.

    A sheet with a single part, or parts that never sit adjacent, leaves no
    kerf evidence; a layout with no part near an edge leaves no trim
    evidence. Either falls back to 0 — today's hardcoded behaviour — rather
    than guessing. A derived value outside the branch settings' sane range
    is treated the same way: probably noise, not a real cut parameter.

    (An unconfirmed lead: raw uint16-LE reads at MAP byte offsets 683/833
    line up with each fixture's trim, and offset 581 with kerf 4 — but the
    kerf offset doesn't discriminate across fixtures and both offsets sit
    inside record data, not a header field. Not relied on here.)
    """
    kerf = _mode(_adjacent_gaps(layout))
    trim = _mode(_edge_insets(layout))
    kerf_mm = kerf if kerf is not None and _KERF_MM_MIN <= kerf <= _KERF_MM_MAX else 0
    edge_trim_mm = (
        trim if trim is not None and _EDGE_TRIM_MM_MIN <= trim <= _EDGE_TRIM_MM_MAX else 0
    )
    return kerf_mm, edge_trim_mm


def _adjacent_gaps(layout: ImportMapLayout) -> Counter[int]:
    """Gaps between every pair of real parts on the same sheet whose spans
    overlap on the perpendicular axis (i.e. they face each other across a
    would-be saw cut). Only non-negative gaps count — an overlap would mean
    the placements are invalid, already rejected before this runs."""
    gaps: Counter[int] = Counter()
    for sheet in layout.sheets:
        parts = [placement for placement in sheet.placements if not placement.is_waste]
        for index, left in enumerate(parts):
            for right in parts[index + 1 :]:
                y_overlap = min(left.y_mm + left.width_mm, right.y_mm + right.width_mm) - max(
                    left.y_mm, right.y_mm
                )
                if y_overlap > 0:
                    _count_gap(gaps, right.x_mm - (left.x_mm + left.length_mm))
                    _count_gap(gaps, left.x_mm - (right.x_mm + right.length_mm))
                x_overlap = min(left.x_mm + left.length_mm, right.x_mm + right.length_mm) - max(
                    left.x_mm, right.x_mm
                )
                if x_overlap > 0:
                    _count_gap(gaps, right.y_mm - (left.y_mm + left.width_mm))
                    _count_gap(gaps, left.y_mm - (right.y_mm + right.width_mm))
    return gaps


def _edge_insets(layout: ImportMapLayout) -> Counter[int]:
    """Every real part's inset from each of the sheet's four edges."""
    insets: Counter[int] = Counter()
    for sheet in layout.sheets:
        for placement in sheet.placements:
            if placement.is_waste:
                continue
            insets[placement.x_mm] += 1
            insets[placement.y_mm] += 1
            insets[sheet.width_mm - (placement.x_mm + placement.length_mm)] += 1
            insets[sheet.height_mm - (placement.y_mm + placement.width_mm)] += 1
    return insets


def _count_gap(gaps: Counter[int], gap: int) -> None:
    if gap >= 0:
        gaps[gap] += 1


def _mode(counter: Counter[int]) -> int | None:
    """The most frequent value, tie-broken toward the smallest — deterministic
    regardless of dict iteration order, and the smallest candidate is the
    conservative pick for both a saw kerf and a trim margin."""
    if not counter:
        return None
    top_count = max(counter.values())
    return min(value for value, count in counter.items() if count == top_count)
