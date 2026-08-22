"""Detailed cutting PDF document.

The document is a Bazis-style production report: summary first, then grouped
sheet pages. The map panel itself is delegated to rendering.draw_sheet_map so
its geometry stays in parity with the web sheet visualiser.
"""

# ruff: noqa: RUF001, RUF002 -- report copy uses Uzbek punctuation and circled numbers.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from io import BytesIO
from typing import Any, NamedTuple

import anyio.to_thread
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from app.core.material_label import edge_label as _edge_label
from app.core.material_label import material_label as _material_label
from app.core.money import format_som as _som
from app.modules.cutting.rendering import (
    _FONT_BOLD,
    _FONT_REGULAR,
    _int_snapshot,
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
# The sheet map is what the operator actually reads at the saw, so the page
# gives it every point it can spare. 10 mm is the tightest margin office and
# home printers reliably reproduce without clipping — below that the map starts
# losing its own edge on some hardware, which costs more than it gains.
_MARGIN = 10 * mm
_CONTENT_W = _PAGE_W - 2 * _MARGIN
_INK = 0.08
_MUTED = 0.42
_HAIRLINE = 0.78
_ROW_H = 15
_SMALL_ROW_H = 13
# Identity box column split: the left column holds free-text identity and needs
# the wider share; the right holds fixed-shape generated stats.
_IDENTITY_SPLIT = 0.58
_IDENTITY_FONT = 8.5
# Title block above the first identity baseline, then the per-line steps. The
# box is not a fixed height: long names wrap and it grows, so these drive both
# `_draw_adaptive_identity` and the first summary page's remaining-space budget.
_IDENTITY_TOP = 32.0
_IDENTITY_LEFT_STEP = 12.0
_IDENTITY_RIGHT_STEP = 13.0
_IDENTITY_BOTTOM_PAD = 11.0
_IDENTITY_MIN_H = 82.0
# Gap between the identity box and the first table on the summary page.
_IDENTITY_GAP = 10.0
_MAP_H = 285
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_EDGE_FIELDS = ("edge_top", "edge_bottom", "edge_left", "edge_right")
_MIN_PRINT_TEXT_PT = 7.0
_MIN_EDGE_STROKE_PT = 0.8
_PORTRAIT_SLOT_GAP = 10.0
_REGISTER_ROW_H = 14.0
# Summary tables set their own row height: a cell too wide for its column wraps
# onto further lines and the row grows, rather than the value being cut off with
# an ellipsis. A material name or an own-material note is exactly the cell that
# overflows, and half a material name identifies nothing. A single line still
# measures `_REGISTER_ROW_H`, so an ordinary row is unchanged.
_SUMMARY_LINE_STEP = 8.5
_SUMMARY_ROW_PAD = 5.5
_SUMMARY_ROW_TOP_PAD = 3.0
_CELL_PAD = 2.0
# The gap between the section title and its header row, in the planner's budget.
_SECTION_TITLE_H = 12.0
_REGISTER_HEADER_H = 13.0
# Every point here is a point the map does not get, and the map is width-bound
# for a standard 2750x1830 sheet. 104 is the floor: the binding constraint is now
# the bold 7pt header — "Kenglik" is 25.3pt in a 41.6pt column (0.40 x 104) —
# ahead of a 4-digit mm value (17.8pt) over a 22pt band tick, and the narrow
# "Soni" column still clears its own header.
#
# This is also why the thickening stamp has no column here: it would need
# ~18pt, and the map's >70% page-width floor leaves under 2pt of headroom. The
# stamp lives on the map instead, centred in the part it applies to.
_PORTRAIT_REGISTER_W = 104.0
# Vertical space a work card spends above its map: the four header lines plus
# the padding under them. The planner needs it to size a slot's register.
_CARD_HEADER_H = 73.0
# Gap between the slot's bottom edge and the map/register's bottom edge (see
# `map_y` in `_draw_work_card`). The register shares the map's top, so it
# actually gets this much more room than `_CARD_HEADER_H` alone implies —
# `_portrait_slot_capacity` must add it back or it undercounts by a row.
_CARD_MAP_BOTTOM_PAD = 7.0
_CONTINUATION_HEADER_H = 40.0
# The register's own tick geometry (band-count marks under Uzunlik/Kenglik), separate
# from the map's tick constants in rendering.py.
_REGISTER_TICK_W = 22.0
_REGISTER_TICK_GAP = 3.5
_REGISTER_TICK_STROKE = 0.7
_REGISTER_NUMBER_BASELINE = 5.0
_REGISTER_TICK_TOP = 8.5


@dataclass(frozen=True)
class PdfPriceRow:
    """One receipt line, printed the way the client's «Chek» prints it: what it
    is, the arithmetic behind the figure, and the figure itself.

    The row carries the *numbers*; this module owns how they read on paper, so
    the caller never has to know the receipt's copy or its money format.
    `amount_tiyin` is None for a line the workshop does not charge because the
    client supplied the material — the row still prints, since "you bring it"
    is not the same statement as "it costs nothing". `material_id` is carried
    so an edge line can be stamped with the same registry number ①② the map,
    the register and the kromka specification use.
    """

    group: str
    label: str
    # What the charge multiplies: `quantity` of `unit` at `unit_price_tiyin`.
    # A missing quantity or price prints the amount alone rather than a
    # multiplication by nothing (an order placed before rates were stored).
    unit: str = ""
    quantity: str = ""
    unit_price_tiyin: int | None = None
    # The share of the same line the client brings, in the same unit.
    own_quantity: str = ""
    amount_tiyin: int | None = None
    material_id: str | None = None


@dataclass(frozen=True)
class PdfPricing:
    """The order's money, itemised — the same receipt the client reads under
    «Buyurtmangiz», so the document and the screen state one price one way."""

    rows: tuple[PdfPriceRow, ...] = ()
    total_tiyin: int = 0
    # What the client's own sheets and tape took off the bill; 0 hides the line.
    saved_tiyin: int = 0


@dataclass(frozen=True)
class PdfContext:
    order_number: str | None = None
    client_name: str | None = None
    branch_name: str | None = None
    generated_at: datetime | None = None
    # Draft-bound (not yet an order) identity: the draft's own name, used as
    # the "Buyurtma/chizma" fallback ahead of the bare short-id.
    draft_name: str | None = None
    client_phone: str | None = None
    workshop_name: str | None = None
    branch_address: str | None = None
    branch_phone: str | None = None
    # The money side of the document. Absent for a draft that has no price yet
    # (no branch, no order) — the summary then prints its technical tables only.
    pricing: PdfPricing | None = None


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
    # Rows to print bold, by absolute index — the receipt's total is the one
    # figure the reader is looking for, and a table of equal rows hides it.
    # Absolute, not page-relative, so a section split across pages keeps it.
    bold_rows: frozenset[int] = frozenset()


async def render_cutting_pdf_async(
    result: CuttingResultResponse, context: PdfContext | None = None
) -> bytes:
    """`render_cutting_pdf` off the event loop.

    reportlab lays out every part of every panel and rasterises the diagram —
    pure CPU, and it grows with the size of the cut. This process runs one event
    loop for every tenant, so drawing inline stalls every other request for the
    duration, exactly as the cutting optimizer did before it was offloaded.
    """
    return await anyio.to_thread.run_sync(partial(render_cutting_pdf, result, context))


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
    summary_pages = _plan_summary_pages(result, registry, ctx)
    work_pages = _plan_work_pages(result, units)
    page_count = len(summary_pages) + len(work_pages)

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
    box_h = 78
    pdf.setStrokeGray(_HAIRLINE)
    pdf.rect(_MARGIN, y - box_h, _CONTENT_W, box_h)
    _draw_text(pdf, _MARGIN + 8, y - 17, "Mebel Pro — kesish hujjati", 14, bold=True)
    date_text = (context.generated_at or datetime.now()).strftime("%d.%m.%Y")
    pieces = sum(_part_quantity(part) for part in result.parts_snapshot)
    total_sheets = len(result.panels)
    left = _identity_left_lines(result, context)
    right = [
        f"Sana: {date_text}",
        f"Listlar: {total_sheets}",
        f"Detallar: {pieces} dona",
    ]
    for index, text in enumerate(left):
        _draw_text(pdf, _MARGIN + 8, y - 34 - index * 12, text, 9)
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
        "Ishlatildi",
        "Qoldiq bilan",
    ]
    widths = [124, 62, 34, 38, 45, 45, 42, 58, 58]
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
        f"{_percent(areas.parts_area, areas.sheet_area)} ishlatildi · "
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


def _sheet_list_label(group: SheetGroup) -> str:
    return f"List {group.start}" if group.start == group.end else f"List {group.start}-{group.end}"


def _sheet_edge_labels(
    result: CuttingResultResponse,
    panel: CuttingPanelResponse,
    parts_by_ref: dict[str, tuple[dict[str, Any], int]],
) -> list[str]:
    """Distinct edge-band materials actually used by the parts placed on this
    sheet, in first-seen order."""
    seen: set[str] = set()
    labels: list[str] = []
    for placement in panel.placements:
        row = parts_by_ref.get(placement.part_ref)
        if row is None:
            continue
        part = row[0]
        for side in _EDGE_FIELDS:
            edge = part.get(side)
            if not isinstance(edge, dict):
                continue
            material_id = str(edge.get("material_id") or "")
            if not material_id or material_id in seen:
                continue
            seen.add(material_id)
            labels.append(_edge_label(_material_snapshot(result, material_id), material_id))
    return labels


def _panel_part_rows(
    result: CuttingResultResponse,
    panel: CuttingPanelResponse,
    registry: list[EdgeRegistryEntry],
) -> list[list[str]]:
    """Register rows: `[length, width, quantity, length_band_count,
    width_band_count]`. A part is identified by size + band pattern alone —
    no name, no row number — so rows that end up identical on both counts
    merge their quantity. Thickening is deliberately NOT part of the key: it
    has no column here (the map's >70% page-width floor leaves no room, see
    `_PORTRAIT_REGISTER_W`), so keying on it would only split one size into
    two rows that print identically. The map carries the stamp instead.
    `registry` is unused: edge materials no longer print per row, only
    ①②③-numbered in the summary spec; kept so this signature still matches
    the other row-builders callers thread together.
    """
    del registry
    grouped: dict[str, int] = {}
    for placement in panel.placements:
        grouped[placement.part_ref] = grouped.get(placement.part_ref, 0) + 1
    merged: dict[tuple[int, int, int, int], int] = {}
    order: list[tuple[int, int, int, int]] = []
    for part in result.parts_snapshot:
        part_ref = str(part.get("part_ref") or "")
        count = grouped.get(part_ref, 0)
        if count <= 0:
            continue
        length_mm = int(part.get("length_mm") or 0)
        width_mm = int(part.get("width_mm") or 0)
        length_bands = sum(
            1 for side in ("edge_top", "edge_bottom") if isinstance(part.get(side), dict)
        )
        width_bands = sum(
            1 for side in ("edge_left", "edge_right") if isinstance(part.get(side), dict)
        )
        key = (length_mm, width_mm, length_bands, width_bands)
        if key not in merged:
            order.append(key)
        merged[key] = merged.get(key, 0) + count
    rows: list[list[str]] = []
    for key in order:
        length_mm, width_mm, length_bands, width_bands = key
        rows.append(
            [str(length_mm), str(width_mm), str(merged[key]), str(length_bands), str(width_bands)]
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


def _material_short(snapshot: dict[str, Any], material_id: str) -> str:
    """Shortest thing that still names the material, for a narrow column.

    Reads both snapshot vocabularies for the same reason
    `app/core/material_label.py` does: results frozen before the catalog
    reshape carry `decor_code`/`color`/`name`, and a PDF re-rendered from one
    of those must not degrade to an id fragment.
    """
    return (
        _snapshot_text(snapshot, "code")
        or _snapshot_text(snapshot, "name")
        or _snapshot_text(snapshot, "decor_code")
        or _snapshot_text(snapshot, "color")
        or _snapshot_text(snapshot, "name")
        or material_id[:8]
    )


def _snapshot_text(snapshot: dict[str, Any], key: str) -> str:
    value = snapshot.get(key)
    return value.strip() if isinstance(value, str) else ""


def _panel_length_for_snapshot(snapshot: dict[str, Any]) -> int:
    return _int_snapshot(_snapshot_size(snapshot, "length_mm", "panel_length_mm"), fallback=0)


def _panel_width_for_snapshot(snapshot: dict[str, Any]) -> int:
    return _int_snapshot(_snapshot_size(snapshot, "width_mm", "panel_width_mm"), fallback=0)


def _snapshot_size(snapshot: dict[str, Any], key: str, legacy_key: str) -> Any:
    """New snapshot key first, pre-reshape key as the fallback."""
    value = snapshot.get(key)
    return value if value is not None else snapshot.get(legacy_key)


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


def _order_or_draft_label(result: CuttingResultResponse, context: PdfContext) -> str:
    """An order-bound PDF keeps its order number; a still-draft PDF falls back
    to the draft's own name; only a nameless draft prints the bare short id."""
    if context.order_number:
        return context.order_number
    if context.draft_name:
        return context.draft_name
    return f"chizma {_draft_short_id(result)}"


def _client_label(context: PdfContext) -> str:
    if context.client_name and context.client_phone:
        return f"{context.client_name} ({context.client_phone})"
    return _fallback(context.client_name)


def _branch_lines(context: PdfContext) -> list[str]:
    """Workshop + branch identity for the fixed-height identity box, split
    across up to two lines instead of clipping.

    The phone rides with the names rather than with the address: the box has a
    hard four-line budget, and a real address plus a phone is wider than the
    column, so pairing them put the phone — the one line a customer acts on —
    into the truncated tail. Names + phone and the address alone both fit.
    """
    first = " · ".join(
        part for part in [context.workshop_name, context.branch_name, context.branch_phone] if part
    )
    second = context.branch_address or ""
    lines = [line for line in [first, second] if line]
    return lines or ["—"]


def _identity_left_lines(result: CuttingResultResponse, context: PdfContext) -> list[str]:
    branch_lines = _branch_lines(context)
    lines = [
        f"Buyurtma/chizma: {_order_or_draft_label(result, context)}",
        f"Mijoz: {_client_label(context)}",
        f"Filial: {branch_lines[0]}",
    ]
    lines.extend(branch_lines[1:])
    return lines


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


def _wrap(text: str, size: float, width: float, *, bold: bool = False) -> list[str]:
    """Word-wrap to the column width, measured in the real font.

    `_clip` estimates from a character count, which is fine for the generated
    stat lines it guards but wrong for free-text identity (a long workshop name
    or address in a proportional font). Nothing here is dropped: a line too wide
    for its column continues on the next one, and a single unbroken token wider
    than the whole column is split on characters rather than allowed to run over
    the neighbouring column.
    """
    font = _FONT_BOLD if bold else _FONT_REGULAR
    if not text:
        return []
    if width <= 0 or pdfmetrics.stringWidth(text, font, size) <= width:
        return [text]
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}" if current else word
        if pdfmetrics.stringWidth(candidate, font, size) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        while pdfmetrics.stringWidth(word, font, size) > width:
            head = ""
            for char in word:
                if pdfmetrics.stringWidth(head + char, font, size) > width:
                    break
                head += char
            if not head:  # column narrower than one glyph — nothing to split on
                break
            lines.append(head)
            word = word[len(head) :]
        current = word
    if current:
        lines.append(current)
    return lines


# --- Adaptive production cards -------------------------------------------


def _plan_work_pages(result: CuttingResultResponse, units: list[LayoutUnit]) -> list[PdfPagePlan]:
    """Two sheets to an A4 portrait page, always.

    Orientation is no longer a decision: a page holds two layout units (the last
    one alone when the count is odd) regardless of how many parts a sheet
    carries. A register too long for its half-page slot spills onto a
    continuation page instead of promoting its sheet to a page of its own — the
    operator gets a predictable two-up sheet order, and no row is dropped.
    """
    del result
    capacity = _portrait_slot_capacity()
    pages: list[PdfPagePlan] = []
    for index in range(0, len(units), 2):
        pair = tuple(units[index : index + 2])
        pages.append(PdfPagePlan("portrait", pair))
        for unit in pair:
            pages.extend(_register_continuation_pages(unit, capacity))
    return pages


def _portrait_slot_capacity() -> int:
    """Register rows one half-page work card can print.

    Must mirror `_draw_work_card`'s geometry exactly: the register starts at
    the map's top (`map_y + map_h`, i.e. `slot_h - _CARD_HEADER_H +
    _CARD_MAP_BOTTOM_PAD` above the slot's bottom edge), not at
    `slot_h - _CARD_HEADER_H`. Omitting the pad undercounts by a row and
    sends a row to a needless continuation page even though it would have
    fit in the card.
    """
    slot_h = (_PAGE_H - 2 * _MARGIN - _PORTRAIT_SLOT_GAP) / 2
    return _register_capacity(slot_h - _CARD_HEADER_H + _CARD_MAP_BOTTOM_PAD)


def _register_continuation_pages(unit: LayoutUnit, capacity: int) -> list[PdfPagePlan]:
    if capacity <= 0 or len(unit.rows) <= capacity:
        return []
    pages: list[PdfPagePlan] = []
    continuation_capacity = _register_capacity(_PAGE_H - 2 * _MARGIN - _CONTINUATION_HEADER_H)
    row_start = capacity
    while row_start < len(unit.rows):
        row_end = min(len(unit.rows), row_start + continuation_capacity)
        pages.append(PdfPagePlan("portrait_continuation", (unit,), row_start, row_end))
        row_start = row_end
    return pages


def _register_capacity(height: float) -> int:
    return max(0, int((height - _REGISTER_HEADER_H) // _REGISTER_ROW_H))


def _plan_summary_pages(
    result: CuttingResultResponse,
    registry: list[EdgeRegistryEntry],
    context: PdfContext | None = None,
) -> list[list[tuple[SummarySection, int, int]]]:
    sections = _summary_sections(result, registry, context)
    pages: list[list[tuple[SummarySection, int, int]]] = []
    page: list[tuple[SummarySection, int, int]] = []
    # The identity block on the first page is as tall as its wrapped columns
    # need; measure it rather than assume, or a workshop with a long name
    # silently overprints the first table.
    identity_h = _identity_box_h(*_identity_columns(result, context or PdfContext()))
    remaining = _PAGE_H - 2 * _MARGIN - identity_h - _IDENTITY_GAP
    for section in sections:
        # Rows are no longer a fixed height, so the planner measures each one
        # the same way the drawing does — the alternative is a wrapped row
        # printing past the bottom margin of the page it was budgeted onto.
        heights = [_summary_row_h(row, section.widths) for row in section.rows]
        needed_head = _SECTION_TITLE_H + _summary_row_h(section.headers, section.widths, bold=True)
        start = 0
        while start < len(section.rows):
            if remaining < needed_head + heights[start]:
                pages.append(page)
                page = []
                remaining = _PAGE_H - 2 * _MARGIN
            end = start
            used = 0.0
            while end < len(heights) and used + heights[end] <= remaining - needed_head:
                used += heights[end]
                end += 1
            if end == start:  # one row taller than a whole page: place it anyway
                used = heights[start]
                end = start + 1
            page.append((section, start, end))
            remaining -= needed_head + used + 10
            start = end
    if page or not pages:
        pages.append(page)
    return pages


def _summary_sections(
    result: CuttingResultResponse,
    registry: list[EdgeRegistryEntry],
    context: PdfContext | None = None,
) -> list[SummarySection]:
    # Last column widened 38 → 58 with the KIM → Ishlatildi rename: a header
    # wider than its column wraps onto a second line and pushes every table
    # below it down, so each one is sized to hold its own label. _fill_width
    # gives the slack back to the name column, which absorbs it by wrapping.
    material_widths = _fill_width([0, 50, 55, 52, 52, 55, 58])
    material_rows: list[list[str]] = []
    total = MaterialStats("", 0, 0, 0, 0, 0, 0)
    for row in _material_stats(result):
        snapshot = _material_snapshot(result, row.material_id)
        material_rows.append(
            [
                _material_label(snapshot, row.material_id),
                str(row.sheet_count),
                str(row.piece_count),
                _m2(row.parts_area),
                _m2(row.usable_area),
                _m2(row.waste_area),
                _percent(row.parts_area, row.sheet_area),
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
                str(total.sheet_count),
                str(total.piece_count),
                _m2(total.parts_area),
                _m2(total.usable_area),
                _m2(total.waste_area),
                _percent(total.parts_area, total.sheet_area),
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
            _material_label(_material_snapshot(result, material_id), material_id),
            f"{length}×{width} mm",
            f"{count} dona",
        ]
        for material_id, length, width, count in _usable_offcut_rows(result)
    ]
    if not offcut_rows:
        offcut_rows.append(["", "Qoldiq yo'q.", ""])
    pricing = (context or PdfContext()).pricing
    # Money first: the client opens this document to see what the order costs,
    # and the section that answers that must not be one the offcut table can
    # push onto page 2. The production tables the saw reads follow it, and the
    # work cards — the pages that actually go to the machine — are unaffected.
    return [
        *([_pricing_section(pricing, registry)] if pricing else []),
        SummarySection(
            "Materiallar",
            [
                "Material",
                "Listlar",
                "Detallar",
                "Detal m²",
                "Qoldiq m²",
                "Chiqindi m²",
                "Ishlatildi",
            ],
            material_widths,
            material_rows or [["", "0", "0", "0.00", "0.00", "0.00", "—"]],
        ),
        SummarySection(
            "Kromkalar", ["#", "Kromka", "Metr"], _fill_width([28, 0, 112], name_index=1), edge_rows
        ),
        SummarySection(
            "Qoldiqlar", ["Material", "O'lcham", "Dona"], _fill_width([0, 100, 64]), offcut_rows
        ),
    ]


def _pricing_section(pricing: PdfPricing, registry: list[EdgeRegistryEntry]) -> SummarySection:
    """The receipt as a table: every row carries the multiplication behind it,
    so the price can be checked instead of taken on faith — the same reason the
    «Buyurtmangiz» card prints `3 × 300 000 = 900 000` rather than a subtotal.

    Figures are bare numbers: the currency is stated by the two money headers,
    once, which is also what buys the arithmetic column the width it needs.
    """
    numbers = {entry.material_id: entry.number for entry in registry}
    rows = [
        [
            row.group,
            _numbered_label(row, numbers),
            _price_detail(row),
            _som(row.amount_tiyin) if row.amount_tiyin is not None else "o'zingizniki",
        ]
        for row in pricing.rows
    ]
    rows.append(["Jami", "", "", _som(pricing.total_tiyin)])
    total_index = len(rows) - 1
    if pricing.saved_tiyin > 0:
        rows.append(["Tejaldi", "o'z materialingiz hisobiga", "", _som(pricing.saved_tiyin)])
    return SummarySection(
        "Hisob-kitob",
        ["Turi", "Nomi", "Hisob (so'm)", "Summa (so'm)"],
        _fill_width([44, 0, 200, 80], name_index=1),
        rows,
        bold_rows=frozenset({total_index}),
    )


def _price_detail(row: PdfPriceRow) -> str:
    """The arithmetic cell: `3 list × 300 000 · 2 list o'zingizniki`."""
    parts = []
    if row.quantity and row.unit_price_tiyin:
        parts.append(f"{row.quantity} {row.unit} × {_som(row.unit_price_tiyin)}")
    if row.own_quantity:
        parts.append(f"{row.own_quantity} {row.unit} o'zingizniki")
    return " · ".join(part.strip() for part in parts)


def _numbered_label(row: PdfPriceRow, numbers: dict[str, int]) -> str:
    number = numbers.get(row.material_id or "")
    return f"{_registry_number(number)} {row.label}" if number else row.label


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
        y = _draw_adaptive_identity(pdf, result, context, y) - _IDENTITY_GAP
    else:
        _draw_text(pdf, _MARGIN, y, "Kesish hujjati — umumiy ma'lumot (davomi)", 11, bold=True)
        y -= 20
    for section, start, end in page:
        _draw_text(pdf, _MARGIN, y, section.title, 10, bold=True)
        y -= _SECTION_TITLE_H
        y = _draw_adaptive_table_row(pdf, y, section.headers, section.widths, bold=True)
        for index in range(start, end):
            y = _draw_adaptive_table_row(
                pdf, y, section.rows[index], section.widths, bold=index in section.bold_rows
            )
        y -= 10
    _draw_page_number(pdf, number, count, _PAGE_W, _PAGE_H)


def _identity_columns(
    result: CuttingResultResponse, context: PdfContext
) -> tuple[list[str], list[str]]:
    """The identity box's two columns, wrapped to their own widths.

    The left column carries free-text identity (workshop, branch, address,
    client) whose length the report cannot bound; the right is generated stats
    of a known shape. Long text wraps onto further lines rather than being
    truncated — a half-printed workshop name is worse than a taller box — so
    the box height is a function of this result, not a constant.
    """
    date_text = (context.generated_at or datetime.now()).strftime("%d.%m.%Y")
    pieces = sum(_part_quantity(part) for part in result.parts_snapshot)
    left = [
        line
        for text in _identity_left_lines(result, context)
        for line in _wrap(text, _IDENTITY_FONT, _identity_left_w())
    ]
    right = [
        line
        for text in (
            f"Sana: {date_text}",
            f"Listlar: {len(result.panels)} · detallar: {pieces} dona",
            f"Kromka: {_metres(result.total_edge_length_mm)} m",
            # The two cutting parameters the layout was computed with — without
            # them the saw operator cannot reproduce these coordinates.
            f"Arra kesigi: {result.kerf_mm} mm · chetki qirqim: {result.edge_trim_mm} mm",
            # The one figure the client looks for first, stated before the
            # receipt spells out how it was built.
            *(
                [f"Jami: {_som(context.pricing.total_tiyin)} so'm"]
                if context.pricing is not None
                else []
            ),
        )
        for line in _wrap(text, _IDENTITY_FONT, _identity_right_w())
    ]
    return left, right


def _identity_left_w() -> float:
    """Left edge padding to the right column's edge, less a gutter."""
    return float(_CONTENT_W * _IDENTITY_SPLIT - 16)


def _identity_right_w() -> float:
    return float(_CONTENT_W * (1 - _IDENTITY_SPLIT) - 8)


def _identity_box_h(left: list[str], right: list[str]) -> float:
    """Height the identity box needs for its wrapped columns.

    `_plan_summary_pages` has to subtract the same number it draws, or the
    first page's tables start where the box already ended.
    """
    last_baseline = max(
        (len(left) - 1) * _IDENTITY_LEFT_STEP, (len(right) - 1) * _IDENTITY_RIGHT_STEP
    )
    return max(_IDENTITY_MIN_H, _IDENTITY_TOP + last_baseline + _IDENTITY_BOTTOM_PAD)


def _draw_adaptive_identity(
    pdf: canvas.Canvas, result: CuttingResultResponse, context: PdfContext, y: float
) -> float:
    left, right = _identity_columns(result, context)
    box_h = _identity_box_h(left, right)
    pdf.setStrokeGray(_HAIRLINE)
    pdf.rect(_MARGIN, y - box_h, _CONTENT_W, box_h)
    _draw_text(pdf, _MARGIN + 8, y - 16, "Mebel Pro — kesish hujjati", 14, bold=True)
    right_x = _MARGIN + _CONTENT_W * _IDENTITY_SPLIT
    for index, text in enumerate(left):
        _draw_text(pdf, _MARGIN + 8, y - _IDENTITY_TOP - index * _IDENTITY_LEFT_STEP, text, 8.5)
    for index, text in enumerate(right):
        _draw_text(pdf, right_x, y - _IDENTITY_TOP - index * _IDENTITY_RIGHT_STEP, text, 8.5)
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
    _setup_page(pdf)
    if page.orientation == "portrait_continuation":
        _draw_register_continuation(pdf, result, context, registry, page.units[0], page)
        _draw_page_number(pdf, number, count, _PAGE_W, _PAGE_H)
        return
    slot_h = (_PAGE_H - 2 * _MARGIN - _PORTRAIT_SLOT_GAP) / 2
    capacity = _portrait_slot_capacity()
    for slot, unit in enumerate(page.units):
        y = _PAGE_H - _MARGIN - (slot + 1) * slot_h - slot * _PORTRAIT_SLOT_GAP
        _draw_work_card(
            pdf,
            result,
            context,
            registry,
            unit,
            (_MARGIN, y, _CONTENT_W, slot_h),
            row_end=capacity,
        )
    _draw_page_number(pdf, number, count, _PAGE_W, _PAGE_H)


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
    parts_by_ref = _parts_by_ref(result)
    # Card header: exactly 4 lines — list range, material, kromka materials
    # used on this sheet, then the area/ishlatildi/qoldiq metrics.
    _draw_text(pdf, x + 6, y + height - 14, _sheet_list_label(unit.group), 9, bold=True)
    _draw_text(
        pdf,
        x + 6,
        y + height - 27,
        _material_label(snapshot, str(panel.material_id)),
        7.5,
    )
    edge_labels = _sheet_edge_labels(result, panel, parts_by_ref)
    kromka_line = f"Kromkalar: {', '.join(edge_labels)}" if edge_labels else "Kromkalar: —"
    _draw_text(pdf, x + 6, y + height - 40, _clip(kromka_line, width - 12), 7.0)
    areas = _panel_areas(result, panel)
    metrics_line = (
        f"Detallar maydoni: {_m2(areas.parts_area)} m² · "
        f"{_percent(areas.parts_area, areas.sheet_area)} ishlatildi · "
        f"Foydali qoldiq: {_m2(areas.usable_area)} m² · "
        f"Chiqindi: {_m2(areas.waste_area)} m²"
    )
    _draw_text(pdf, x + 6, y + height - 53, metrics_line, 7.0)
    map_y = y + _CARD_MAP_BOTTOM_PAD
    map_h = height - _CARD_HEADER_H
    register_w = _PORTRAIT_REGISTER_W
    map_w = width - register_w - 16
    map_x = x + 5
    register_x = map_x + map_w + 7
    draw_sheet_map(
        pdf,
        (map_x, map_y, map_w, map_h),
        result,
        panel,
        parts_by_ref,
        min_text_pt=_MIN_PRINT_TEXT_PT,
        min_edge_stroke_pt=_MIN_EDGE_STROKE_PT,
    )
    del registry  # edge materials print in the "Kromkalar" header line, not per row
    _draw_register(pdf, register_x, map_y + map_h, register_w, unit.rows[row_start:row_end])


def _draw_register_continuation(
    pdf: canvas.Canvas,
    result: CuttingResultResponse,
    context: PdfContext,
    registry: list[EdgeRegistryEntry],
    unit: LayoutUnit,
    page: PdfPagePlan,
) -> None:
    panel = unit.group.panels[0]
    snapshot = _material_snapshot(result, panel.material_id)
    list_label = _sheet_list_label(unit.group)
    _draw_text(pdf, _MARGIN, _PAGE_H - _MARGIN, f"{list_label} · Detallar (davomi)", 11, bold=True)
    _draw_text(
        pdf,
        _MARGIN,
        _PAGE_H - _MARGIN - 15,
        _clip(_material_label(snapshot, str(panel.material_id)), _CONTENT_W),
        8,
    )
    del registry  # edge materials print in the work card's "Kromkalar" line, not per row
    # Full content width, not the work card's narrow _PORTRAIT_REGISTER_W: this
    # page has no map beside it, so a 120pt column would sit as a lone strip on
    # an otherwise empty A4. _register_widths splits it into the same three
    # proportional columns, just spread across the page.
    _draw_register(
        pdf,
        _MARGIN,
        _PAGE_H - _MARGIN - _CONTINUATION_HEADER_H,
        _CONTENT_W,
        unit.rows[page.row_start : page.row_end],
    )


def _draw_register(
    pdf: canvas.Canvas,
    x: float,
    top: float,
    width: float,
    rows: list[list[str]],
) -> None:
    """Uzunlik / Kenglik / Soni register. A part carries no name or row number on
    the sheet — only size and band pattern — so this draws rules only: a rule
    under the header, a light hairline between rows, a closing rule under the
    last row. No per-cell boxes (those made empty cells read as stray boxes).
    """
    widths = _register_widths(width)
    y = top - _REGISTER_HEADER_H
    cursor = x
    for text, col_width in zip(["Uzunlik", "Kenglik", "Soni"], widths, strict=True):
        _draw_centred_text(pdf, cursor + col_width / 2, y + 3, text, _MIN_PRINT_TEXT_PT, bold=True)
        cursor += col_width
    pdf.setStrokeGray(_HAIRLINE)
    pdf.setLineWidth(0.6)
    pdf.line(x, y, x + width, y)
    for index, row in enumerate(rows):
        y = _draw_register_row(pdf, x, y, row, widths)
        if index < len(rows) - 1:
            pdf.setStrokeGray(_HAIRLINE)
            pdf.setLineWidth(0.35)
            pdf.line(x, y, x + width, y)
    pdf.setStrokeGray(_HAIRLINE)
    pdf.setLineWidth(0.6)
    pdf.line(x, y, x + width, y)


def _draw_register_row(
    pdf: canvas.Canvas,
    x: float,
    top: float,
    row: list[str],
    widths: Sequence[float],
) -> float:
    length_text, width_text, qty_text, length_bands, width_bands = row
    y = top - _REGISTER_ROW_H
    baseline = top - _REGISTER_NUMBER_BASELINE
    tick_top = top - _REGISTER_TICK_TOP
    cursor = x
    _draw_centred_text(pdf, cursor + widths[0] / 2, baseline, length_text, _MIN_PRINT_TEXT_PT)
    _draw_band_ticks(pdf, cursor + widths[0] / 2, tick_top, int(length_bands))
    cursor += widths[0]
    _draw_centred_text(pdf, cursor + widths[1] / 2, baseline, width_text, _MIN_PRINT_TEXT_PT)
    _draw_band_ticks(pdf, cursor + widths[1] / 2, tick_top, int(width_bands))
    cursor += widths[1]
    _draw_centred_text(pdf, cursor + widths[2] / 2, baseline, qty_text, _MIN_PRINT_TEXT_PT)
    return y


def _draw_band_ticks(pdf: canvas.Canvas, cx: float, top_y: float, count: int) -> None:
    """N short horizontal rules stacked under a register number — N banded
    edges on that side (0, 1 or 2). Uniform solid stroke, never dashed."""
    if count <= 0:
        return
    pdf.saveState()
    pdf.setStrokeGray(_INK)
    pdf.setLineWidth(_REGISTER_TICK_STROKE)
    pdf.setLineCap(1)
    half = _REGISTER_TICK_W / 2
    for tick in range(count):
        ty = top_y - tick * _REGISTER_TICK_GAP
        pdf.line(cx - half, ty, cx + half, ty)
    pdf.restoreState()


def _draw_centred_text(
    pdf: canvas.Canvas, cx: float, y: float, text: str, size: float, *, bold: bool = False
) -> None:
    pdf.setFillGray(_INK)
    pdf.setFont(_FONT_BOLD if bold else _FONT_REGULAR, size)
    pdf.drawCentredString(cx, y, text)


def _fill_width(widths: list[float], *, name_index: int = 0) -> list[float]:
    """Spend the whole content width, giving the slack to the name column.

    The numeric columns are sized to their content; the name column (material,
    kromka) holds text that is always longer than its box, so it absorbs
    whatever the page width leaves over instead of the table stopping short.
    """
    fixed = sum(width for index, width in enumerate(widths) if index != name_index)
    return [
        float(_CONTENT_W - fixed) if index == name_index else width
        for index, width in enumerate(widths)
    ]


def _register_widths(width: float) -> list[float]:
    # Uzunlik / Kenglik carry a 4-digit mm value over a 22pt band tick; Soni carries at
    # most three digits but still has to clear its own bold "Soni" header, which
    # is wider than any value it holds. At the register's narrowed width the old
    # 0.16 share stopped covering that header.
    ratios = (0.40, 0.40, 0.20)
    return [width * ratio for ratio in ratios]


def _draw_adaptive_table_row(
    pdf: canvas.Canvas,
    y: float,
    values: list[str],
    widths: Sequence[float],
    *,
    bold: bool = False,
) -> float:
    return _draw_positioned_table_row(pdf, _MARGIN, y, values, widths, bold=bold)


def _draw_positioned_table_row(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    values: list[str],
    widths: Sequence[float],
    *,
    bold: bool = False,
) -> float:
    """One table row, as tall as its widest-wrapping cell needs.

    Cells wrap inside their own column and the row grows to the tallest of
    them; every line stays inside its cell, so a long material name costs a
    second line rather than its own second half.
    """
    row_h = _summary_row_h(values, widths, bold=bold)
    cursor = x
    pdf.setStrokeGray(_HAIRLINE)
    pdf.setLineWidth(0.35)
    for value, width in zip(values, widths, strict=True):
        pdf.rect(cursor, y - row_h, width, row_h)
        # Top-aligned: a short cell reads against the tall cell's FIRST line,
        # which is the one that names the row. A one-line row lands on exactly
        # the baseline it had before rows could grow.
        for index, line in enumerate(_cell_lines(value, width, bold=bold)):
            baseline = y - _SUMMARY_ROW_TOP_PAD - (index + 1) * _SUMMARY_LINE_STEP
            _draw_text(pdf, cursor + _CELL_PAD, baseline, line, _MIN_PRINT_TEXT_PT, bold=bold)
        cursor += width
    return y - row_h


def _cell_lines(value: str, width: float, *, bold: bool = False) -> list[str]:
    """The cell's text, wrapped to its own column and never empty."""
    return _wrap(value, _MIN_PRINT_TEXT_PT, width - 2 * _CELL_PAD, bold=bold) or [""]


def _summary_row_h(values: Sequence[str], widths: Sequence[float], *, bold: bool = False) -> float:
    """The height a row needs — one line is `_REGISTER_ROW_H`, as before."""
    lines = max(
        len(_cell_lines(value, width, bold=bold))
        for value, width in zip(values, widths, strict=True)
    )
    return max(_REGISTER_ROW_H, lines * _SUMMARY_LINE_STEP + _SUMMARY_ROW_PAD)


def _draw_page_number(
    pdf: canvas.Canvas, number: int, count: int, page_w: float, _page_h: float
) -> None:
    pdf.setFillGray(_MUTED)
    pdf.setFont(_FONT_REGULAR, 7)
    pdf.drawRightString(page_w - _MARGIN, _MARGIN - 12, f"Sahifa {number} / {count}")
