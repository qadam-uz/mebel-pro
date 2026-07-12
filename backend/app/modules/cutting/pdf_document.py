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

from reportlab.lib.pagesizes import A4
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


def render_cutting_pdf(result: CuttingResultResponse, context: PdfContext | None = None) -> bytes:
    _register_fonts()
    ctx = context or PdfContext()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    registry = _derive_edge_registry(result.parts_snapshot)
    groups = _group_identical_sheets(result)

    _draw_summary_page(pdf, result, ctx, registry)
    pdf.showPage()

    if not result.panels:
        _draw_title(pdf, "Kesish xujjati")
        _draw_text(pdf, _MARGIN, _PAGE_H - 36 * mm, "Listlar yo'q", 11)
        pdf.showPage()
    else:
        for group in groups:
            _draw_sheet_group(pdf, result, ctx, group, registry)

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
    _draw_text(pdf, _MARGIN + 8, y - 17, "Mebel Pro — kesish xujjati", 14, bold=True)
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
        _draw_text(pdf, _MARGIN, y, "Krom ishlatilmagan.", 9)
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
    pdf.setTitle("Mebel Pro — kesish xujjati")
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
