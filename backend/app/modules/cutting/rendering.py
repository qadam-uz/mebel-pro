"""Map drawing primitives for immutable cutting result PDFs.

The detailed PDF document is a production report, not a bare visualiser mirror.
The parity contract is now scoped to the map panel only: placements, offcut
overlays, label fitting and edge-banding ticks mirror
web/src/shared/components/CuttingPanelSvg.vue. All helper geometry is expressed
in sheet millimetres with the y axis growing up — the optimizer's own convention,
which is also reportlab's page convention.
"""

# ruff: noqa: RUF001 -- labels reuse the visualiser's exact copy (multiplication
# sign in dimensions, U+21BB rotation marker)

from __future__ import annotations

from typing import Any, NamedTuple

from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

from app.core.pdf import FONT_BOLD, FONT_REGULAR, register_pdf_fonts
from app.modules.cutting.schemas import (
    CuttingOffcutResponse,
    CuttingPanelResponse,
    CuttingPlacementResponse,
    CuttingResultResponse,
)

# Label and banding constants mirror CuttingPanelSvg.vue one-for-one: sizes are
# normalized to an 800-unit sheet length so a 2800 mm and a 900 mm panel read
# the same on paper as on screen.
_NORM_WIDTH = 800.0
_LABEL_FONT = 11.0
_LABEL_MIN_W = 80.0
_LABEL_MIN_H = 30.0
_BAND_STROKE = 3.0
_BAND_INSET = 3.0
_BAND_MARK = 30.0

# Print equivalents of the web tokens the visualiser uses. Structure stays
# grayscale for print; colour is reserved for the offcut semantics.
_SUCCESS = HexColor("#15803d")  # --color-success: usable offcut
_DANGER = HexColor("#be3a2b")  # --color-danger: waste offcut
_INK_MUTED = HexColor("#5b6675")  # --color-ink-muted: waste offcut label, footer
_INK_SOFT = HexColor("#475569")  # --color-ink-soft: placement labels
_PANEL_TYPE_LABELS = {
    "dsp": "LDSP",
    "mdf": "MDF",
    "plywood": "Fanera",
    "natural_wood": "Yog'och",
    "other": "Panel",
}

# The vendored Unicode font pair is shared with the other in-process documents
# (app/core/pdf.py); these aliases keep the module-local naming.
_FONT_REGULAR = FONT_REGULAR
_FONT_BOLD = FONT_BOLD
_register_fonts = register_pdf_fonts


class _BandedSides(NamedTuple):
    top: bool
    right: bool
    bottom: bool
    left: bool


class _OffcutLabelMode(NamedTuple):
    text: str
    orientation: str


class _Frame(NamedTuple):
    x: float
    y: float
    width: float
    height: float


def _sheet_transform(
    panel_length: int,
    panel_width: int,
    frame_width: float,
    frame_height: float,
    *,
    origin_x: float = 0,
    origin_y: float = 0,
) -> tuple[float, float, float]:
    """(origin_x, origin_y, scale): sheet mm → page points, centred in frame."""
    scale = min(frame_width / panel_length, frame_height / panel_width)
    sheet_x = origin_x + (frame_width - panel_length * scale) / 2
    sheet_y = origin_y + (frame_height - panel_width * scale) / 2
    return sheet_x, sheet_y, scale


def draw_sheet_map(
    pdf: canvas.Canvas,
    frame: tuple[float, float, float, float],
    result: CuttingResultResponse,
    panel: CuttingPanelResponse,
    parts_by_ref: dict[str, tuple[dict[str, Any], int]] | None = None,
    *,
    min_text_pt: float = 7.0,
    min_edge_stroke_pt: float = 0.8,
) -> None:
    """Draw only the sheet map into `(x, y, width, height)` PDF points."""
    _register_fonts()
    parts = parts_by_ref or _parts_by_ref(result)
    panel_length = _panel_length(result, panel)
    panel_width = _panel_width(result, panel)
    box = _Frame(*frame)
    origin_x, origin_y, scale = _sheet_transform(
        panel_length,
        panel_width,
        box.width,
        box.height,
        origin_x=box.x,
        origin_y=box.y,
    )
    norm_scale = _NORM_WIDTH / panel_length
    label_font_pt = max(min_text_pt, (_LABEL_FONT / norm_scale) * scale)

    pdf.setLineWidth(2 * scale)
    pdf.setStrokeGray(0.2)
    pdf.rect(origin_x, origin_y, panel_length * scale, panel_width * scale)

    for offcut in panel.offcuts:
        x, y, w, h = _rect_points(
            offcut.x_mm,
            offcut.y_mm,
            offcut.length_mm,
            offcut.width_mm,
            origin_x=origin_x,
            origin_y=origin_y,
            scale=scale,
        )
        pdf.saveState()
        pdf.setLineWidth(1.5 * scale)
        pdf.setDash([12 * scale, 8 * scale])
        pdf.setStrokeColor(_SUCCESS if offcut.usable else _DANGER)
        pdf.rect(x, y, w, h)
        pdf.restoreState()
        offcut_label = _offcut_label_mode(offcut, norm_scale)
        if offcut_label is not None:
            pdf.setFillColor(_SUCCESS if offcut.usable else _INK_MUTED)
            pdf.setFont(_FONT_REGULAR, max(min_text_pt, label_font_pt))
            if offcut_label.orientation == "vertical":
                pdf.saveState()
                pdf.translate(x + w / 2, y + h / 2)
                pdf.rotate(90)
                pdf.drawCentredString(0, -0.36 * label_font_pt, offcut_label.text)
                pdf.restoreState()
            else:
                pdf.drawCentredString(
                    x + w / 2,
                    y + h / 2 - 0.36 * label_font_pt,
                    offcut_label.text,
                )

    for placement in panel.placements:
        x, y, w, h = _rect_points(
            placement.x_mm,
            placement.y_mm,
            placement.length_mm,
            placement.width_mm,
            origin_x=origin_x,
            origin_y=origin_y,
            scale=scale,
        )
        pdf.setLineWidth(1.5 * scale)
        pdf.setStrokeGray(0.25)
        pdf.setFillGray(0.93)
        pdf.rect(x, y, w, h, stroke=1, fill=1)

        row = parts.get(placement.part_ref)
        sides = _banded_sides(row[0] if row else None, rotated=placement.rotated)
        if sides is not None:
            ticks = _band_tick_lines(placement, sides, norm_scale)
            if ticks:
                pdf.saveState()
                pdf.setLineCap(1)
                pdf.setLineWidth(max(min_edge_stroke_pt, (_BAND_STROKE / norm_scale) * scale))
                pdf.setStrokeGray(0.15)
                for x1, y1, x2, y2 in ticks:
                    pdf.line(
                        origin_x + x1 * scale,
                        origin_y + y1 * scale,
                        origin_x + x2 * scale,
                        origin_y + y2 * scale,
                    )
                pdf.restoreState()

        label = _placement_label_mode(placement, parts, label_font_pt, w, h)
        if label is not None:
            pdf.setFillColor(_INK_SOFT)
            pdf.setFont(_FONT_REGULAR, label_font_pt)
            if label.orientation == "vertical":
                pdf.saveState()
                pdf.translate(x + w / 2, y + h / 2)
                pdf.rotate(90)
                pdf.drawCentredString(0, -0.36 * label_font_pt, label.text)
                pdf.restoreState()
            else:
                pdf.drawCentredString(x + w / 2, y + h / 2 - 0.36 * label_font_pt, label.text)


def _rect_points(
    x_mm: float,
    y_mm: float,
    length_mm: float,
    width_mm: float,
    *,
    origin_x: float,
    origin_y: float,
    scale: float,
) -> tuple[float, float, float, float]:
    """Placement/offcut rectangle in page points. `y_mm` is bottom-left-origin —
    the optimizer's and reportlab's shared convention — so it maps straight
    through. Re-applying the visualiser's SVG y-flip here would mirror the
    whole layout vertically against the on-screen plan."""
    return (
        origin_x + x_mm * scale,
        origin_y + y_mm * scale,
        length_mm * scale,
        width_mm * scale,
    )


def _label_fits(length_mm: int, width_mm: int, norm_scale: float) -> bool:
    return length_mm * norm_scale > _LABEL_MIN_W and width_mm * norm_scale > _LABEL_MIN_H


def _text_label_fits(text: str, length_mm: int, width_mm: int, norm_scale: float) -> bool:
    return (
        length_mm * norm_scale > max(_LABEL_MIN_W, len(text) * 6)
        and width_mm * norm_scale > _LABEL_MIN_H
    )


def _parts_by_ref(result: CuttingResultResponse) -> dict[str, tuple[dict[str, Any], int]]:
    return {
        str(part.get("part_ref")): (part, index) for index, part in enumerate(result.parts_snapshot)
    }


def _placement_label(
    placement: CuttingPlacementResponse,
    parts_by_ref: dict[str, tuple[dict[str, Any], int]],
) -> str:
    row = parts_by_ref.get(placement.part_ref)
    if row is None:
        name = placement.part_ref
    else:
        part, index = row
        raw_name = part.get("name")
        stripped = raw_name.strip() if isinstance(raw_name, str) else ""
        name = stripped or f"D{index + 1}"
    rotated = " ↻" if placement.rotated else ""
    number = f"#{index + 1} " if row is not None else ""
    return f"{number}{name} {placement.length_mm}×{placement.width_mm}{rotated}"


def _placement_label_mode(
    placement: CuttingPlacementResponse,
    parts_by_ref: dict[str, tuple[dict[str, Any], int]],
    font_pt: float,
    width_pt: float,
    height_pt: float,
) -> _OffcutLabelMode | None:
    """Deterministic print fallback: full label, dimensions, row number, none.

    The right-side register always carries dimensions and quantity, so omitting a
    label here is safe only after all readable alternatives have failed.
    """
    full = _placement_label(placement, parts_by_ref)
    row = parts_by_ref.get(placement.part_ref)
    dims = f"{placement.length_mm}×{placement.width_mm}"
    number = f"#{row[1] + 1}" if row is not None else placement.part_ref
    for text in (full, dims, number):
        if _printed_text_fits(text, font_pt, width_pt, height_pt):
            return _OffcutLabelMode(text, "horizontal")
    for text in (full, dims, number):
        if _printed_text_fits(text, font_pt, height_pt, width_pt):
            return _OffcutLabelMode(text, "vertical")
    return None


def _printed_text_fits(text: str, font_pt: float, width_pt: float, height_pt: float) -> bool:
    return (
        pdfmetrics.stringWidth(text, _FONT_REGULAR, font_pt) + 4 <= width_pt
        and font_pt * 1.35 <= height_pt
    )


def _offcut_label_mode(offcut: CuttingOffcutResponse, norm_scale: float) -> _OffcutLabelMode | None:
    dims = f"{offcut.length_mm}×{offcut.width_mm}"
    labels = [f"Qoldiq {dims}"]
    if not offcut.usable:
        labels = ["chiqit"]
    for text in labels:
        if _text_label_fits(text, offcut.length_mm, offcut.width_mm, norm_scale):
            return _OffcutLabelMode(text=text, orientation="horizontal")
    for text in labels:
        if _text_label_fits(text, offcut.width_mm, offcut.length_mm, norm_scale):
            return _OffcutLabelMode(text=text, orientation="vertical")
    if offcut.usable:
        if _text_label_fits(dims, offcut.length_mm, offcut.width_mm, norm_scale):
            return _OffcutLabelMode(text=dims, orientation="horizontal")
        if _text_label_fits(dims, offcut.width_mm, offcut.length_mm, norm_scale):
            return _OffcutLabelMode(text=dims, orientation="vertical")
    return None


def _banded_sides(part: dict[str, Any] | None, *, rotated: bool) -> _BandedSides | None:
    if part is None:
        return None
    top = bool(part.get("edge_top"))
    bottom = bool(part.get("edge_bottom"))
    left = bool(part.get("edge_left"))
    right = bool(part.get("edge_right"))
    if not rotated:
        return _BandedSides(top=top, right=right, bottom=bottom, left=left)
    # The optimizer's only rotation is 90° and it records no direction, so map
    # the part's sides clockwise (top→right, right→bottom, …) like the visualiser.
    return _BandedSides(top=left, right=top, bottom=right, left=bottom)


def _band_tick_lines(
    placement: CuttingPlacementResponse, sides: _BandedSides, norm_scale: float
) -> list[tuple[float, float, float, float]]:
    """Short centred "tape" ticks just inside each banded side, in sheet mm
    (y up). The inset is capped at 30% of the shorter side so it never inverts
    on a thin sliver; each tick is capped at 60% of its side so it stays a
    mark, not a full edge."""
    length = placement.length_mm
    width = placement.width_mm
    inset = min(_BAND_INSET / norm_scale, min(length, width) * 0.3)
    half_h = min(_BAND_MARK / norm_scale, length * 0.6) / 2
    half_v = min(_BAND_MARK / norm_scale, width * 0.6) / 2
    x0 = float(placement.x_mm)
    y0 = float(placement.y_mm)
    cx = x0 + length / 2
    cy = y0 + width / 2
    lines: list[tuple[float, float, float, float]] = []
    if sides.top:
        lines.append((cx - half_h, y0 + width - inset, cx + half_h, y0 + width - inset))
    if sides.bottom:
        lines.append((cx - half_h, y0 + inset, cx + half_h, y0 + inset))
    if sides.left:
        lines.append((x0 + inset, cy - half_v, x0 + inset, cy + half_v))
    if sides.right:
        lines.append((x0 + length - inset, cy - half_v, x0 + length - inset, cy + half_v))
    return lines


def _material_label(snapshot: dict[str, Any], material_id: object) -> str:
    raw_type = _snapshot_text(snapshot, "type")
    type_label = _PANEL_TYPE_LABELS.get(raw_type, raw_type)
    manufacturer = _snapshot_text(snapshot, "manufacturer_name")
    decor = _snapshot_text(snapshot, "decor_code")
    name = _snapshot_text(snapshot, "name")
    color = _snapshot_text(snapshot, "color")
    thickness = _snapshot_text(snapshot, "thickness_mm")
    length = _int_snapshot(snapshot.get("panel_length_mm"), fallback=0)
    width = _int_snapshot(snapshot.get("panel_width_mm"), fallback=0)

    base = " ".join(part for part in [type_label, manufacturer, decor or name] if part)
    if not base:
        return str(material_id)[:8]

    details: list[str] = []
    if color and color.lower() not in base.lower():
        details.append(color)
    if length > 0 and width > 0:
        dims = f"{length}×{width}"
        if thickness:
            dims = f"{dims}×{_format_mm(thickness)}"
        details.append(f"{dims} mm")
    elif thickness:
        details.append(f"{_format_mm(thickness)} mm")
    return " · ".join([base, *details])


def _snapshot_text(snapshot: dict[str, Any], key: str) -> str:
    value = snapshot.get(key)
    return value.strip() if isinstance(value, str) else ""


def _format_mm(value: object) -> str:
    text = str(value).strip()
    try:
        parsed = float(text)
    except ValueError:
        return text
    if parsed.is_integer():
        return str(int(parsed))
    return text.rstrip("0").rstrip(".")


def _panel_fill_percent(panel: CuttingPanelResponse, panel_length: int, panel_width: int) -> str:
    area = panel_length * panel_width
    if area <= 0:
        return "-"
    return f"{max(0.0, 100.0 - panel.waste_area_mm2 / area * 100.0):.1f}%"


def _material_snapshot(result: CuttingResultResponse, material_id: object) -> dict[str, object]:
    return result.material_snapshots.get(str(material_id), {})


def _panel_length(result: CuttingResultResponse, panel: CuttingPanelResponse) -> int:
    snapshot = _material_snapshot(result, panel.material_id)
    return _int_snapshot(snapshot.get("panel_length_mm"), fallback=1000)


def _panel_width(result: CuttingResultResponse, panel: CuttingPanelResponse) -> int:
    snapshot = _material_snapshot(result, panel.material_id)
    return _int_snapshot(snapshot.get("panel_width_mm"), fallback=700)


def _int_snapshot(value: object, *, fallback: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return fallback
