"""Detailed cutting PDF document.

The document is a Bazis-style production report: summary first, then grouped
sheet pages. The map panel itself is delegated to rendering.draw_sheet_map so
its geometry stays in parity with the web sheet visualiser.
"""

# ruff: noqa: RUF001 -- report copy uses Uzbek punctuation and circled numbers.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any, NamedTuple

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.modules.cutting.rendering import (
    _FONT_BOLD,
    _FONT_REGULAR,
    _format_mm,
    _int_snapshot,
    _material_label,
    _material_snapshot,
    _panel_length,
    _panel_width,
    _parts_by_ref,
    _placement_label_mode,
    _register_fonts,
    draw_sheet_map,
)
from app.modules.cutting.schemas import CuttingPanelResponse, CuttingResultResponse

_PAGE_W = float(A4[0])
_PAGE_H = float(A4[1])
_MARGIN = 14 * mm
_CONTENT_W = _PAGE_W - 2 * _MARGIN
_INK = 0.08
_MUTED = 0.42
_HAIRLINE = 0.78
_ROW_H = 15
_SMALL_ROW_H = 13
_MAP_H = 285
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_EDGE_FIELDS = ("edge_top", "edge_bottom", "edge_left", "edge_right")
_MIN_PRINT_TEXT_PT = 7.0
_MIN_EDGE_STROKE_PT = 0.8
_PORTRAIT_SLOT_GAP = 10.0
_REGISTER_ROW_H = 11.0
_REGISTER_HEADER_H = 13.0
_PORTRAIT_REGISTER_W = 165.0
_LANDSCAPE_REGISTER_W = 242.0
_LANDSCAPE = (float(landscape(A4)[0]), float(landscape(A4)[1]))


@dataclass(frozen=True)
class PdfContext:
    order_number: str | None = None
    client_name: str | None = None
    branch_name: str | None = None
    generated_at: datetime | None = None


class EdgeRegistryEntry(NamedTuple):
    key: str
    material_id: str
    source: str
    number: int


class SheetGroup(NamedTuple):
    start: int
    end: int
    panels: list[CuttingPanelResponse]


class MaterialStats(NamedTuple):
    material_id: str
    sheet_count: int
    piece_count: int
    sheet_area: int
    parts_area: int
    usable_area: int
    waste_area: int


@dataclass(frozen=True)
class LayoutUnit:
    """One indivisible printable layout: a consecutive identical sheet group."""

    group: SheetGroup
    rows: list[list[str]]


@dataclass(frozen=True)
class PdfPagePlan:
    orientation: str
    units: tuple[LayoutUnit, ...]
    row_start: int = 0
    row_end: int | None = None


@dataclass(frozen=True)
class SummarySection:
    title: str
    headers: list[str]
    widths: Sequence[float]
    rows: list[list[str]]


def render_cutting_pdf(result: CuttingResultResponse, context: PdfContext | None = None) -> bytes:
    _register_fonts()
    ctx = context or PdfContext()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    registry = _derive_edge_registry(result.parts_snapshot)
    groups = _group_identical_sheets(result)

    units = [
        LayoutUnit(group, _panel_part_rows(result, group.panels[0], registry)) for group in groups
    ]
    summary_pages = _plan_summary_pages(result, registry)
    work_pages = _plan_work_pages(result, units)
    page_count = len(summary_pages) + len(work_pages)

<<<<<<< HEAD
    for number, summary_page in enumerate(summary_pages, start=1):
        _draw_adaptive_summary_page(pdf, result, ctx, summary_page, number, page_count)
        pdf.showPage()
    if not work_pages and not summary_pages:
        _setup_page(pdf)
        _draw_title(pdf, "Kesish hujjati")
        _draw_page_number(pdf, 1, 1, _PAGE_W, _PAGE_H)
        pdf.showPage()
    for index, page in enumerate(work_pages, start=len(summary_pages) + 1):
        _draw_work_page(pdf, result, ctx, registry, page, index, page_count)
=======
    if not result.panels:
        _draw_title(pdf, "Kesish hujjati")
        _draw_text(pdf, _MARGIN, _PAGE_H - 36 * mm, "Listlar yo'q", 11)
>>>>>>> 1029575d89811c9955199e32c9f1abe50aee66c6
        pdf.showPage()

    pdf.save()
    return buffer.getvalue()


def _draw_summary_page(
    pdf: canvas.Canvas,
    result: CuttingResultResponse,
    context: PdfContext,
    registry: list[EdgeRegistryEntry],
) -> None:
    _setup_page(pdf)
    y = _PAGE_H - _MARGIN
    y = _draw_summary_title_block(pdf, result, context, y)
    y -= 10
    y = _draw_materials_summary(pdf, result, y)
    y -= 12
    y = _draw_edge_summary(pdf, result, registry, y)
    y -= 12
    _draw_usable_offcuts(pdf, result, y)


def _draw_summary_title_block(
    pdf: canvas.Canvas,
    result: CuttingResultResponse,
    context: PdfContext,
    y: float,
) -> float:
    box_h = 70
    pdf.setStrokeGray(_HAIRLINE)
    pdf.rect(_MARGIN, y - box_h, _CONTENT_W, box_h)
    _draw_text(pdf, _MARGIN + 8, y - 17, "Mebel Pro — kesish hujjati", 14, bold=True)
    order = context.order_number or f"chizma {_draft_short_id(result)}"
    date_text = (context.generated_at or datetime.now()).strftime("%d.%m.%Y")
    pieces = sum(_part_quantity(part) for part in result.parts_snapshot)
    total_sheets = len(result.panels)
    left = [
        f"Buyurtma: {order}",
        f"Mijoz: {_fallback(context.client_name)}",
        f"Filial: {_fallback(context.branch_name)}",
    ]
    right = [
        f"Sana: {date_text}",
        f"Listlar: {total_sheets}",
        f"Detallar: {pieces} dona",
    ]
    for index, text in enumerate(left):
        _draw_text(pdf, _MARGIN + 8, y - 34 - index * 13, text, 9)
    for index, text in enumerate(right):
        _draw_text(pdf, _MARGIN + _CONTENT_W / 2 + 8, y - 34 - index * 13, text, 9)
    return y - box_h


def _draw_materials_summary(pdf: canvas.Canvas, result: CuttingResultResponse, y: float) -> float:
    _draw_text(pdf, _MARGIN, y, "Materiallar", 11, bold=True)
    y -= 14
    headers = [
        "Material",
        "List o'lchami",
        "Listlar",
        "Detallar",
        "Detal m²",
        "Qoldiq m²",
        "Chiqit m²",
        "KIM",
        "KIM+q",
    ]
    widths = [124, 62, 34, 38, 45, 45, 42, 34, 34]
    y = _draw_table_row(pdf, y, headers, widths, bold=True)
    stats = _material_stats(result)
    total = MaterialStats("", 0, 0, 0, 0, 0, 0)
    for row in stats:
        snapshot = _material_snapshot(result, row.material_id)
        values = [
            _material_label(snapshot, row.material_id),
            f"{_panel_length_for_snapshot(snapshot)}×{_panel_width_for_snapshot(snapshot)}",
            str(row.sheet_count),
            str(row.piece_count),
            _m2(row.parts_area),
            _m2(row.usable_area),
            _m2(row.waste_area),
            _percent(row.parts_area, row.sheet_area),
            _percent(row.parts_area + row.usable_area, row.sheet_area),
        ]
        y = _draw_table_row(pdf, y, values, widths)
        total = MaterialStats(
            "",
            total.sheet_count + row.sheet_count,
            total.piece_count + row.piece_count,
            total.sheet_area + row.sheet_area,
            total.parts_area + row.parts_area,
            total.usable_area + row.usable_area,
            total.waste_area + row.waste_area,
        )
    totals = [
        "Jami",
        "",
        str(total.sheet_count),
        str(total.piece_count),
        _m2(total.parts_area),
        _m2(total.usable_area),
        _m2(total.waste_area),
        _percent(total.parts_area, total.sheet_area),
        _percent(total.parts_area + total.usable_area, total.sheet_area),
    ]
    return _draw_table_row(pdf, y, totals, widths, bold=True)


def _draw_edge_summary(
    pdf: canvas.Canvas,
    result: CuttingResultResponse,
    registry: list[EdgeRegistryEntry],
    y: float,
) -> float:
    _draw_text(pdf, _MARGIN, y, "Kromka spetsifikatsiyasi", 11, bold=True)
    y -= 14
    if not registry:
        _draw_text(pdf, _MARGIN, y, "Kromka ishlatilmagan.", 9)
        return y - 12
    widths = [28, 360, 112]
    y = _draw_table_row(pdf, y, ["#", "Kromka", "Metr"], widths, bold=True)
    for entry in registry:
        shop = result.edge_consumed_shop_by_material.get(entry.material_id, 0)
        own = result.edge_consumed_own_by_material.get(entry.material_id, 0)
        total = shop + own
        if total <= 0:
            continue
        suffix = f" (shu jumladan o'zingizniki {_metres(own)} m)" if own > 0 else ""
        snapshot = _material_snapshot(result, entry.material_id)
        y = _draw_table_row(
            pdf,
            y,
            [
                _registry_number(entry.number),
                _edge_label(snapshot, entry.material_id),
                f"{_metres(total)} m{suffix}",
            ],
            widths,
        )
    return y


def _draw_usable_offcuts(pdf: canvas.Canvas, result: CuttingResultResponse, y: float) -> float:
    rows = _usable_offcut_rows(result)
    if not rows:
        return y
    _draw_text(pdf, _MARGIN, y, "Sizda qoladigan qoldiqlar", 11, bold=True)
    y -= 14
    widths = [300, 94, 70]
    y = _draw_table_row(pdf, y, ["Material", "O'lcham", "Dona"], widths, bold=True)
    for material_id, length, width, count in rows:
        snapshot = _material_snapshot(result, material_id)
        y = _draw_table_row(
            pdf,
            y,
            [_material_short(snapshot, material_id), f"{length}×{width} mm", f"{count} dona"],
            widths,
        )
    return y


def _draw_sheet_group(
    pdf: canvas.Canvas,
    result: CuttingResultResponse,
    context: PdfContext,
    group: SheetGroup,
    registry: list[EdgeRegistryEntry],
) -> None:
    panel = group.panels[0]
    parts_by_ref = _parts_by_ref(result)
    rows = _panel_part_rows(result, panel, registry)
    first_page = True
    row_index = 0
    while first_page or row_index < len(rows):
        _setup_page(pdf)
        y = _draw_sheet_title_block(pdf, result, context, group, first_page)
        y = _draw_sheet_stats(pdf, result, panel, y - 8)
        map_bottom = y - _MAP_H
        draw_sheet_map(pdf, (_MARGIN, map_bottom, _CONTENT_W, _MAP_H), result, panel, parts_by_ref)
        y = map_bottom - 14
        if not first_page:
            _draw_text(pdf, _MARGIN, y + 12, "(davomi)", 9, bold=True)
        row_index, y = _draw_parts_table(pdf, y, rows, row_index)
        pdf.showPage()
        first_page = False


def _draw_sheet_title_block(
    pdf: canvas.Canvas,
    result: CuttingResultResponse,
    context: PdfContext,
    group: SheetGroup,
    first_page: bool,
) -> float:
    panel = group.panels[0]
    snapshot = _material_snapshot(result, panel.material_id)
    y = _PAGE_H - _MARGIN
    box_h = 58
    pdf.setStrokeGray(_HAIRLINE)
    pdf.rect(_MARGIN, y - box_h, _CONTENT_W, box_h)
    material = _material_label(snapshot, panel.material_id)
    dims = f"{_panel_length(result, panel)}×{_panel_width(result, panel)} mm"
    list_label = (
        f"List {group.start}" if group.start == group.end else f"List {group.start}–{group.end}"
    )
    count = len(group.panels)
    order = context.order_number or f"chizma {_draft_short_id(result)}"
    date_text = (context.generated_at or datetime.now()).strftime("%d.%m.%Y")
    cont = " (davomi)" if not first_page else ""
    _draw_text(pdf, _MARGIN + 8, y - 16, f"Material: {material} · {dims}", 10, bold=True)
    _draw_text(pdf, _MARGIN + 8, y - 31, f"{list_label} · jami {len(result.panels)}{cont}", 9)
    _draw_text(pdf, _MARGIN + 8, y - 46, f"{count} dona list", 9)
    _draw_text(pdf, _MARGIN + _CONTENT_W / 2, y - 31, f"Buyurtma: {order}", 9)
    _draw_text(pdf, _MARGIN + _CONTENT_W / 2, y - 46, f"Sana: {date_text}", 9)
    return float(y - box_h)


def _draw_sheet_stats(
    pdf: canvas.Canvas, result: CuttingResultResponse, panel: CuttingPanelResponse, y: float
) -> float:
    areas = _panel_areas(result, panel)
    text = (
        f"To'ldirish {_percent(areas.parts_area, areas.sheet_area)} · "
        f"Detallar {_m2(areas.parts_area)} m² · "
        f"Qoldiq {_m2(areas.usable_area)} m² · "
        f"Chiqit {_m2(areas.waste_area)} m²"
    )
    _draw_text(pdf, _MARGIN, y, text, 9, bold=True)
    return y - 10


def _draw_parts_table(
    pdf: canvas.Canvas, y: float, rows: list[list[str]], row_index: int
) -> tuple[int, float]:
    widths = [24, 138, 76, 34, 28, 28, 28, 28, 52]
    headers = ["#", "Nomi", "O'lcham (mm)", "Dona", "Д1", "Д2", "Ш1", "Ш2", "Tekstura"]
    y = _draw_table_row(pdf, y, headers, widths, bold=True)
    min_y = _MARGIN + 16
    while row_index < len(rows) and y - _ROW_H >= min_y:
        y = _draw_table_row(pdf, y, rows[row_index], widths)
        row_index += 1
    return row_index, y


def _draw_table_row(
    pdf: canvas.Canvas,
    y: float,
    values: list[str],
    widths: Sequence[float],
    *,
    bold: bool = False,
    row_h: float = _SMALL_ROW_H,
) -> float:
    x = _MARGIN
    pdf.setStrokeGray(_HAIRLINE)
    pdf.setLineWidth(0.35)
    for value, width in zip(values, widths, strict=True):
        pdf.rect(x, y - row_h, width, row_h)
        _draw_text(pdf, x + 3, y - row_h + 4, _clip(value, width), 7.5, bold=bold)
        x += width
    return y - row_h


def _setup_page(pdf: canvas.Canvas) -> None:
    pdf.setPageSize(A4)
    pdf.setTitle("Mebel Pro — kesish hujjati")
    pdf.setAuthor("Mebel Pro")


def _draw_title(pdf: canvas.Canvas, text: str) -> None:
    _draw_text(pdf, _MARGIN, _PAGE_H - _MARGIN, text, 14, bold=True)


def _draw_text(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    size: float,
    *,
    bold: bool = False,
    gray: float = _INK,
) -> None:
    pdf.setFillGray(gray)
    pdf.setFont(_FONT_BOLD if bold else _FONT_REGULAR, size)
    pdf.drawString(x, y, text)


def _derive_edge_registry(parts: list[dict[str, Any]]) -> list[EdgeRegistryEntry]:
    entries: list[EdgeRegistryEntry] = []
    seen: set[str] = set()
    for part in parts:
        for side in _EDGE_FIELDS:
            edge = part.get(side)
            if not isinstance(edge, dict):
                continue
            material_id = str(edge.get("material_id") or "")
            source = str(edge.get("source") or "shop")
            if not material_id:
                continue
            key = f"{material_id}:{source}"
            if key in seen:
                continue
            seen.add(key)
            entries.append(EdgeRegistryEntry(key, material_id, source, len(entries) + 1))
    return entries


def _registry_number(number: int) -> str:
    if 1 <= number <= len(_CIRCLED):
        return _CIRCLED[number - 1]
    return f"({number})"


def _edge_registry_lookup(registry: list[EdgeRegistryEntry]) -> dict[str, EdgeRegistryEntry]:
    return {entry.key: entry for entry in registry}


def _group_identical_sheets(result: CuttingResultResponse) -> list[SheetGroup]:
    groups: list[SheetGroup] = []
    current: list[CuttingPanelResponse] = []
    current_key: tuple[Any, ...] | None = None
    start = 1
    for index, panel in enumerate(result.panels, start=1):
        key = _panel_group_key(panel)
        if current and key != current_key:
            groups.append(SheetGroup(start, index - 1, current))
            current = []
            start = index
        current.append(panel)
        current_key = key
    if current:
        groups.append(SheetGroup(start, start + len(current) - 1, current))
    return groups


def _panel_group_key(panel: CuttingPanelResponse) -> tuple[Any, ...]:
    placements = tuple(
        sorted(
            (
                item.x_mm,
                item.y_mm,
                item.length_mm,
                item.width_mm,
                item.part_ref,
            )
            for item in panel.placements
        )
    )
    offcuts = tuple(
        sorted(
            (item.x_mm, item.y_mm, item.length_mm, item.width_mm, item.usable)
            for item in panel.offcuts
        )
    )
    return str(panel.material_id), placements, offcuts


def _material_stats(result: CuttingResultResponse) -> list[MaterialStats]:
    stats: dict[str, MaterialStats] = {}
    for panel in result.panels:
        material_id = str(panel.material_id)
        areas = _panel_areas(result, panel)
        piece_count = len(panel.placements)
        current = stats.get(material_id, MaterialStats(material_id, 0, 0, 0, 0, 0, 0))
        stats[material_id] = MaterialStats(
            material_id,
            current.sheet_count + 1,
            current.piece_count + piece_count,
            current.sheet_area + areas.sheet_area,
            current.parts_area + areas.parts_area,
            current.usable_area + areas.usable_area,
            current.waste_area + areas.waste_area,
        )
    return list(stats.values())


def _panel_areas(result: CuttingResultResponse, panel: CuttingPanelResponse) -> MaterialStats:
    length = _panel_length(result, panel)
    width = _panel_width(result, panel)
    sheet_area = length * width
    parts_area = sum(item.length_mm * item.width_mm for item in panel.placements)
    usable_area = sum(item.length_mm * item.width_mm for item in panel.offcuts if item.usable)
    waste_area = max(0, sheet_area - parts_area - usable_area)
    return MaterialStats(
        str(panel.material_id),
        1,
        len(panel.placements),
        sheet_area,
        parts_area,
        usable_area,
        waste_area,
    )


def _panel_part_rows(
    result: CuttingResultResponse,
    panel: CuttingPanelResponse,
    registry: list[EdgeRegistryEntry],
) -> list[list[str]]:
    grouped: dict[str, int] = {}
    for placement in panel.placements:
        grouped[placement.part_ref] = grouped.get(placement.part_ref, 0) + 1
    lookup = _edge_registry_lookup(registry)
    rows: list[list[str]] = []
    for index, part in enumerate(result.parts_snapshot):
        part_ref = str(part.get("part_ref") or "")
        count = grouped.get(part_ref, 0)
        if count <= 0:
            continue
        side_numbers = []
        for side in _EDGE_FIELDS:
            edge = part.get(side)
            number = "·"
            if isinstance(edge, dict):
                key = f"{edge.get('material_id')}:{edge.get('source', 'shop')}"
                entry = lookup.get(key)
                if entry:
                    number = _registry_number(entry.number)
            side_numbers.append(number)
        name = _part_name(part, index)
        rows.append(
            [
                str(index + 1),
                name,
                f"{part.get('length_mm')}×{part.get('width_mm')}",
                str(count),
                *side_numbers,
                "→" if part.get("follow_grain", True) else "·",
            ]
        )
    return rows


def _usable_offcut_rows(result: CuttingResultResponse) -> list[tuple[str, int, int, int]]:
    counts: dict[tuple[str, int, int], int] = {}
    for panel in result.panels:
        material_id = str(panel.material_id)
        for offcut in panel.offcuts:
            if not offcut.usable:
                continue
            key = (material_id, offcut.length_mm, offcut.width_mm)
            counts[key] = counts.get(key, 0) + 1
    return sorted(
        (
            (material_id, length, width, count)
            for (material_id, length, width), count in counts.items()
        ),
        key=lambda row: row[1] * row[2],
        reverse=True,
    )


def _edge_label(snapshot: dict[str, Any], material_id: str) -> str:
    manufacturer = _snapshot_text(snapshot, "manufacturer_name")
    decor = _snapshot_text(snapshot, "decor_code")
    name = _snapshot_text(snapshot, "name")
    color = _snapshot_text(snapshot, "color")
    thickness = _snapshot_text(snapshot, "thickness_mm")
    width = _int_snapshot(snapshot.get("edge_width_mm"), fallback=0)
    base = " ".join(part for part in [manufacturer, decor or name] if part) or material_id[:8]
    size = f"{_format_mm(thickness)}×{width} mm" if thickness and width > 0 else ""
    return " · ".join(part for part in [base, color, size] if part)


def _material_short(snapshot: dict[str, Any], material_id: str) -> str:
    return (
        _snapshot_text(snapshot, "decor_code")
        or _snapshot_text(snapshot, "color")
        or _snapshot_text(snapshot, "name")
        or material_id[:8]
    )


def _snapshot_text(snapshot: dict[str, Any], key: str) -> str:
    value = snapshot.get(key)
    return value.strip() if isinstance(value, str) else ""


def _panel_length_for_snapshot(snapshot: dict[str, Any]) -> int:
    return _int_snapshot(snapshot.get("panel_length_mm"), fallback=0)


def _panel_width_for_snapshot(snapshot: dict[str, Any]) -> int:
    return _int_snapshot(snapshot.get("panel_width_mm"), fallback=0)


def _part_name(part: dict[str, Any], index: int) -> str:
    name = part.get("name")
    stripped = name.strip() if isinstance(name, str) else ""
    return stripped or f"D{index + 1}"


def _part_quantity(part: dict[str, Any]) -> int:
    value = part.get("quantity")
    return int(value) if isinstance(value, int) and value > 0 else 0


def _draft_short_id(result: CuttingResultResponse) -> str:
    return result.draft_id.hex[:8] if result.draft_id else str(result.id)[:8]


def _fallback(value: str | None) -> str:
    return value or "—"


def _percent(value: int, total: int) -> str:
    if total <= 0:
        return "—"
    return f"{value / total * 100:.1f}%"


def _m2(area_mm2: int) -> str:
    return f"{area_mm2 / 1_000_000:.2f}"


def _metres(length_mm: int) -> str:
    return f"{length_mm / 1000:.2f}"


def _clip(text: str, width: float) -> str:
    limit = max(3, int(width / 4.4))
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


# --- Adaptive production cards -------------------------------------------


def _plan_work_pages(result: CuttingResultResponse, units: list[LayoutUnit]) -> list[PdfPagePlan]:
    """Plan pages before drawing so no unit is split to make it fit.

    The planner deliberately has no ReportLab dependency.  Its thresholds are
    print constraints, not aesthetic hints: 7 pt type, 0.8 pt edge ticks, and
    complete register rows.  This makes orientation behaviour cheap to test.
    """
    pages: list[PdfPagePlan] = []
    pending: LayoutUnit | None = None
    for unit in units:
        if _portrait_unit_eligible(result, unit):
            if pending is None:
                pending = unit
            else:
                pages.append(PdfPagePlan("portrait", (pending, unit)))
                pending = None
            continue
        if pending is not None:
            pages.append(PdfPagePlan("portrait", (pending,)))
            pending = None
        pages.extend(_landscape_pages_for_unit(unit))
    if pending is not None:
        pages.append(PdfPagePlan("portrait", (pending,)))
    return pages


def _portrait_unit_eligible(result: CuttingResultResponse, unit: LayoutUnit) -> bool:
    panel = unit.group.panels[0]
    frame_h = (_PAGE_H - 2 * _MARGIN - _PORTRAIT_SLOT_GAP) / 2
    map_h = frame_h - 73
    map_w = _CONTENT_W - _PORTRAIT_REGISTER_W - 16
    return len(unit.rows) <= _register_capacity(map_h) and _map_is_readable(
        result, panel, map_w, map_h
    )


def _landscape_pages_for_unit(unit: LayoutUnit) -> list[PdfPagePlan]:
    _page_w, page_h = _LANDSCAPE
    map_h = page_h - 2 * _MARGIN - 73
    capacity = _register_capacity(map_h)
    pages = [PdfPagePlan("landscape", (unit,), 0, min(len(unit.rows), capacity))]
    row_start = capacity
    continuation_capacity = _register_capacity(page_h - 2 * _MARGIN - 40)
    while row_start < len(unit.rows):
        row_end = min(len(unit.rows), row_start + continuation_capacity)
        pages.append(PdfPagePlan("landscape_continuation", (unit,), row_start, row_end))
        row_start = row_end
    return pages


def _register_capacity(height: float) -> int:
    return max(0, int((height - _REGISTER_HEADER_H) // _REGISTER_ROW_H))


def _map_is_readable(
    result: CuttingResultResponse,
    panel: CuttingPanelResponse,
    frame_w: float,
    frame_h: float,
) -> bool:
    length = _panel_length(result, panel)
    width = _panel_width(result, panel)
    if length <= 0 or width <= 0 or frame_w < 150 or frame_h < 120:
        return False
    scale = min(frame_w / length, frame_h / width)
    parts = _parts_by_ref(result)
    # Work-card labels use the same 7 pt fitting ladder as the map renderer.
    # Banded ticks are clamped to 0.8 pt by draw_sheet_map, so their old
    # normalized web tick length is not a print-orientation gate.
    return all(
        _placement_label_mode(
            placement,
            parts,
            _MIN_PRINT_TEXT_PT,
            placement.length_mm * scale,
            placement.width_mm * scale,
        )
        is not None
        for placement in panel.placements
    )


def _plan_summary_pages(
    result: CuttingResultResponse, registry: list[EdgeRegistryEntry]
) -> list[list[tuple[SummarySection, int, int]]]:
    sections = _summary_sections(result, registry)
    pages: list[list[tuple[SummarySection, int, int]]] = []
    page: list[tuple[SummarySection, int, int]] = []
    remaining = _PAGE_H - 2 * _MARGIN - 82  # identity block on the first page
    for section in sections:
        start = 0
        while start < len(section.rows):
            needed_head = 27
            if remaining < needed_head + _REGISTER_ROW_H:
                pages.append(page)
                page = []
                remaining = _PAGE_H - 2 * _MARGIN
            capacity = max(1, int((remaining - needed_head) // _REGISTER_ROW_H))
            end = min(len(section.rows), start + capacity)
            page.append((section, start, end))
            remaining -= needed_head + (end - start) * _REGISTER_ROW_H + 10
            start = end
    if page or not pages:
        pages.append(page)
    return pages


def _summary_sections(
    result: CuttingResultResponse, registry: list[EdgeRegistryEntry]
) -> list[SummarySection]:
    material_widths = [124, 62, 34, 38, 45, 45, 42, 34, 34]
    material_rows: list[list[str]] = []
    total = MaterialStats("", 0, 0, 0, 0, 0, 0)
    for row in _material_stats(result):
        snapshot = _material_snapshot(result, row.material_id)
        material_rows.append(
            [
                _material_label(snapshot, row.material_id),
                f"{_panel_length_for_snapshot(snapshot)}×{_panel_width_for_snapshot(snapshot)}",
                str(row.sheet_count),
                str(row.piece_count),
                _m2(row.parts_area),
                _m2(row.usable_area),
                _m2(row.waste_area),
                _percent(row.parts_area, row.sheet_area),
                _percent(row.parts_area + row.usable_area, row.sheet_area),
            ]
        )
        total = MaterialStats(
            "",
            total.sheet_count + row.sheet_count,
            total.piece_count + row.piece_count,
            total.sheet_area + row.sheet_area,
            total.parts_area + row.parts_area,
            total.usable_area + row.usable_area,
            total.waste_area + row.waste_area,
        )
    if material_rows:
        material_rows.append(
            [
                "Jami",
                "",
                str(total.sheet_count),
                str(total.piece_count),
                _m2(total.parts_area),
                _m2(total.usable_area),
                _m2(total.waste_area),
                _percent(total.parts_area, total.sheet_area),
                _percent(total.parts_area + total.usable_area, total.sheet_area),
            ]
        )
    edge_rows: list[list[str]] = []
    for entry in registry:
        shop = result.edge_consumed_shop_by_material.get(entry.material_id, 0)
        own = result.edge_consumed_own_by_material.get(entry.material_id, 0)
        total_length = shop + own
        if total_length:
            suffix = f" (o'zingizniki {_metres(own)} m)" if own else ""
            edge_rows.append(
                [
                    _registry_number(entry.number),
                    _edge_label(_material_snapshot(result, entry.material_id), entry.material_id),
                    f"{_metres(total_length)} m{suffix}",
                ]
            )
    if not edge_rows:
        edge_rows.append(["", "Kromka ishlatilmagan.", ""])
    offcut_rows = [
        [
            _material_short(_material_snapshot(result, material_id), material_id),
            f"{length}×{width} mm",
            f"{count} dona",
        ]
        for material_id, length, width, count in _usable_offcut_rows(result)
    ]
    if not offcut_rows:
        offcut_rows.append(["", "Qoldiq yo'q.", ""])
    return [
        SummarySection(
            "Materiallar",
            [
                "Material",
                "List",
                "Listlar",
                "Detallar",
                "Detal m²",
                "Qoldiq m²",
                "Chiqit m²",
                "KIM",
                "KIM+q",
            ],
            material_widths,
            material_rows or [["", "", "0", "0", "0.00", "0.00", "0.00", "—", "—"]],
        ),
        SummarySection(
            "Kromka spetsifikatsiyasi", ["#", "Kromka", "Metr"], [28, 360, 112], edge_rows
        ),
        SummarySection(
            "Sizda qoladigan qoldiqlar", ["Material", "O'lcham", "Dona"], [300, 94, 70], offcut_rows
        ),
    ]


def _draw_adaptive_summary_page(
    pdf: canvas.Canvas,
    result: CuttingResultResponse,
    context: PdfContext,
    page: list[tuple[SummarySection, int, int]],
    number: int,
    count: int,
) -> None:
    _setup_page(pdf)
    y = _PAGE_H - _MARGIN
    if number == 1:
        y = _draw_adaptive_identity(pdf, result, context, y) - 10
    else:
        _draw_text(pdf, _MARGIN, y, "Kesish hujjati — umumiy ma'lumot (davomi)", 11, bold=True)
        y -= 20
    for section, start, end in page:
        _draw_text(pdf, _MARGIN, y, section.title, 10, bold=True)
        y -= 12
        y = _draw_adaptive_table_row(pdf, y, section.headers, section.widths, bold=True)
        for row in section.rows[start:end]:
            y = _draw_adaptive_table_row(pdf, y, row, section.widths)
        y -= 10
    _draw_page_number(pdf, number, count, _PAGE_W, _PAGE_H)


def _draw_adaptive_identity(
    pdf: canvas.Canvas, result: CuttingResultResponse, context: PdfContext, y: float
) -> float:
    box_h = 74
    pdf.setStrokeGray(_HAIRLINE)
    pdf.rect(_MARGIN, y - box_h, _CONTENT_W, box_h)
    _draw_text(pdf, _MARGIN + 8, y - 16, "Mebel Pro — kesish hujjati", 14, bold=True)
    order = context.order_number or f"chizma {_draft_short_id(result)}"
    date_text = (context.generated_at or datetime.now()).strftime("%d.%m.%Y")
    pieces = sum(_part_quantity(part) for part in result.parts_snapshot)
    left = [
        f"Buyurtma/chizma: {order}",
        f"Mijoz: {_fallback(context.client_name)}",
        f"Filial: {_fallback(context.branch_name)}",
    ]
    right = [
        f"Sana: {date_text}",
        f"Listlar: {len(result.panels)} · detallar: {pieces} dona",
        "Kesish: "
        f"{_metres(result.total_cut_length_mm)} m · "
        f"kromka: {_metres(result.total_edge_length_mm)} m",
    ]
    for index, text in enumerate(left):
        _draw_text(pdf, _MARGIN + 8, y - 32 - index * 13, text, 8.5)
    for index, text in enumerate(right):
        _draw_text(pdf, _MARGIN + _CONTENT_W / 2 + 5, y - 32 - index * 13, text, 8.5)
    return y - box_h


def _draw_work_page(
    pdf: canvas.Canvas,
    result: CuttingResultResponse,
    context: PdfContext,
    registry: list[EdgeRegistryEntry],
    page: PdfPagePlan,
    number: int,
    count: int,
) -> None:
    if page.orientation == "portrait":
        _setup_page(pdf)
        available_h = _PAGE_H - 2 * _MARGIN
        slot_h = (available_h - _PORTRAIT_SLOT_GAP) / 2
        for slot, unit in enumerate(page.units):
            y = _PAGE_H - _MARGIN - (slot + 1) * slot_h - slot * _PORTRAIT_SLOT_GAP
            _draw_work_card(pdf, result, context, registry, unit, (_MARGIN, y, _CONTENT_W, slot_h))
        _draw_page_number(pdf, number, count, _PAGE_W, _PAGE_H)
        return
    page_w, page_h = _LANDSCAPE
    pdf.setPageSize(_LANDSCAPE)
    pdf.setTitle("Mebel Pro — kesish hujjati")
    unit = page.units[0]
    if page.orientation == "landscape_continuation":
        _draw_register_continuation(pdf, result, context, registry, unit, page, page_w, page_h)
    else:
        _draw_work_card(
            pdf,
            result,
            context,
            registry,
            unit,
            (_MARGIN, _MARGIN, page_w - 2 * _MARGIN, page_h - 2 * _MARGIN),
            row_start=page.row_start,
            row_end=page.row_end,
        )
    _draw_page_number(pdf, number, count, page_w, page_h)


def _draw_work_card(
    pdf: canvas.Canvas,
    result: CuttingResultResponse,
    context: PdfContext,
    registry: list[EdgeRegistryEntry],
    unit: LayoutUnit,
    frame: tuple[float, float, float, float],
    *,
    row_start: int = 0,
    row_end: int | None = None,
) -> None:
    x, y, width, height = frame
    panel = unit.group.panels[0]
    pdf.setStrokeGray(_HAIRLINE)
    pdf.rect(x, y, width, height)
    snapshot = _material_snapshot(result, panel.material_id)
    list_label = (
        f"List {unit.group.start}"
        if unit.group.start == unit.group.end
        else f"List {unit.group.start}–{unit.group.end}"
    )
    _draw_text(
        pdf, x + 6, y + height - 14, f"{list_label} · {len(unit.group.panels)} dona", 9, bold=True
    )
    _draw_text(
        pdf,
        x + 6,
        y + height - 27,
        _material_label(snapshot, str(panel.material_id)),
        7.0,
    )
    stats = _panel_areas(result, panel)
    cut = _cut_metric_text(panel)
    area_stats_text = (
        f"To'ldirish {_percent(stats.parts_area, stats.sheet_area)} · "
        f"Detallar {_m2(stats.parts_area)} m² · "
        f"Qoldiq {_m2(stats.usable_area)} m² · "
        f"Chiqit {_m2(stats.waste_area)} m²"
    )
    _draw_text(
        pdf,
        x + 6,
        y + height - 40,
        area_stats_text,
        7.0,
        bold=True,
    )
    _draw_text(pdf, x + 6, y + height - 53, cut, 7.0, bold=True)
    map_y = y + 7
    map_h = height - 73
    register_w = _PORTRAIT_REGISTER_W if width < 600 else _LANDSCAPE_REGISTER_W
    map_w = width - register_w - 16
    map_x = x + 5
    register_x = map_x + map_w + 7
    draw_sheet_map(
        pdf,
        (map_x, map_y, map_w, map_h),
        result,
        panel,
        _parts_by_ref(result),
        min_text_pt=_MIN_PRINT_TEXT_PT,
        min_edge_stroke_pt=_MIN_EDGE_STROKE_PT,
    )
    _draw_register(
        pdf, register_x, map_y + map_h, register_w, unit.rows[row_start:row_end], registry
    )


def _draw_register_continuation(
    pdf: canvas.Canvas,
    result: CuttingResultResponse,
    context: PdfContext,
    registry: list[EdgeRegistryEntry],
    unit: LayoutUnit,
    page: PdfPagePlan,
    page_w: float,
    page_h: float,
) -> None:
    panel = unit.group.panels[0]
    snapshot = _material_snapshot(result, panel.material_id)
    list_label = (
        f"List {unit.group.start}"
        if unit.group.start == unit.group.end
        else f"List {unit.group.start}–{unit.group.end}"
    )
    _draw_text(pdf, _MARGIN, page_h - _MARGIN, f"{list_label} · Detallar (davomi)", 11, bold=True)
    _draw_text(
        pdf,
        _MARGIN,
        page_h - _MARGIN - 15,
        _clip(_material_label(snapshot, str(panel.material_id)), page_w - 2 * _MARGIN),
        8,
    )
    _draw_register(
        pdf,
        _MARGIN,
        page_h - _MARGIN - 30,
        page_w - 2 * _MARGIN,
        unit.rows[page.row_start : page.row_end],
        registry,
    )


def _draw_register(
    pdf: canvas.Canvas,
    x: float,
    top: float,
    width: float,
    rows: list[list[str]],
    registry: list[EdgeRegistryEntry],
) -> None:
    # The edge columns are deliberately retained on every card: numbers refer
    # to the summary registry and therefore survive grayscale printing.
    del registry
    widths = _register_widths(width)
    headers = ["#", "Detal", "O'lcham", "Q", "D1", "D2", "Sh1", "Sh2"]
    y = _draw_positioned_table_row(
        pdf, x, top, headers, widths, bold=True, row_h=_REGISTER_HEADER_H
    )
    for row in rows:
        compact = [row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]]
        y = _draw_positioned_table_row(pdf, x, y, compact, widths, row_h=_REGISTER_ROW_H)


def _register_widths(width: float) -> list[float]:
    # Eight columns must also fit in a portrait half-card. Names may clip,
    # while dimensions, quantity and all four edge references keep their cells.
    ratios = (0.09, 0.16, 0.26, 0.12, 0.0925, 0.0925, 0.0925, 0.0925)
    return [width * ratio for ratio in ratios]


def _draw_adaptive_table_row(
    pdf: canvas.Canvas,
    y: float,
    values: list[str],
    widths: Sequence[float],
    *,
    bold: bool = False,
    row_h: float = _REGISTER_ROW_H,
) -> float:
    return _draw_positioned_table_row(pdf, _MARGIN, y, values, widths, bold=bold, row_h=row_h)


def _draw_positioned_table_row(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    values: list[str],
    widths: Sequence[float],
    *,
    bold: bool = False,
    row_h: float = _REGISTER_ROW_H,
) -> float:
    cursor = x
    pdf.setStrokeGray(_HAIRLINE)
    pdf.setLineWidth(0.35)
    for value, width in zip(values, widths, strict=True):
        pdf.rect(cursor, y - row_h, width, row_h)
        _draw_text(
            pdf, cursor + 2, y - row_h + 2.5, _clip(value, width), _MIN_PRINT_TEXT_PT, bold=bold
        )
        cursor += width
    return y - row_h


def _cut_metric_text(panel: CuttingPanelResponse) -> str:
    if panel.cut_count is None or panel.cut_length_mm is None:
        return "Kesish ma'lumoti mavjud emas"
    return f"Kesishlar: {panel.cut_count} · uzunligi {_metres(panel.cut_length_mm)} m"


def _draw_page_number(
    pdf: canvas.Canvas, number: int, count: int, page_w: float, _page_h: float
) -> None:
    pdf.setFillGray(_MUTED)
    pdf.setFont(_FONT_REGULAR, 7)
    pdf.drawRightString(page_w - _MARGIN, _MARGIN - 12, f"Sahifa {number} / {count}")
