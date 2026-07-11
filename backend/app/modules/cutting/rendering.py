"""PDF rendering for immutable cutting results.

The PDF is the print companion of the web panel visualiser
(web/src/shared/components/CuttingPanelSvg.vue): same geometry, same centred
part labels, same banding ticks and offcut overlays, one page per panel. All
helper geometry is expressed in sheet millimetres with the y axis growing up —
the optimizer's own convention, which is also reportlab's page convention. The
visualiser's SVG formulas (y down) are transposed once, inside the helpers.
"""

# ruff: noqa: RUF001 -- labels reuse the visualiser's exact copy (multiplication
# sign in dimensions, U+21BB rotation marker)

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, NamedTuple

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

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

# Page bands (points): side margins plus room for the two header lines above
# the drawing and the algorithm stamp below it.
_MARGIN_X = 18 * mm
_HEADER_H = 30 * mm
_FOOTER_H = 20 * mm

# Print equivalents of the web tokens the visualiser uses. Structure stays
# grayscale for print; colour is reserved for the offcut semantics.
_SUCCESS = HexColor("#15803d")  # --color-success: usable offcut
_DANGER = HexColor("#be3a2b")  # --color-danger: waste offcut
_INK_MUTED = HexColor("#5b6675")  # --color-ink-muted: waste offcut label, footer
_INK_SOFT = HexColor("#475569")  # --color-ink-soft: placement labels

# DejaVu Sans is vendored because the built-in PDF fonts are latin-1 only:
# material and part names can be Cyrillic, and the rotation marker is U+21BB.
_FONTS_DIR = Path(__file__).parent / "fonts"
_FONT_REGULAR = "DejaVuSans"
_FONT_BOLD = "DejaVuSans-Bold"


def render_cutting_pdf(result: CuttingResultResponse) -> bytes:
    _register_fonts()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    parts_by_ref = _parts_by_ref(result)

    for panel in result.panels:
        snapshot = _material_snapshot(result, panel.material_id)
        panel_length = _panel_length(result, panel)
        panel_width = _panel_width(result, panel)
        page_width, page_height = _page_size_for_panel(panel_length, panel_width)
        pdf.setPageSize((page_width, page_height))
        origin_x, origin_y, scale = _sheet_transform(
            panel_length, panel_width, page_width, page_height
        )
        norm_scale = _NORM_WIDTH / panel_length
        label_font_pt = (_LABEL_FONT / norm_scale) * scale

        title = f"{snapshot.get('manufacturer_name', '')} {snapshot.get('name', panel.material_id)}"
        pdf.setFillColorRGB(0, 0, 0)
        pdf.setFont(_FONT_BOLD, 13)
        pdf.drawString(_MARGIN_X, page_height - 18 * mm, title.strip())
        caption = (
            f"List {panel.panel_index} · {_material_label(snapshot, panel.material_id)} · "
            f"{panel_length}×{panel_width} · "
            f"KIM {_panel_fill_percent(panel, panel_length, panel_width)}"
        )
        pdf.setFont(_FONT_REGULAR, 9)
        pdf.drawString(_MARGIN_X, page_height - 24 * mm, caption)

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
            if _label_fits(offcut.length_mm, offcut.width_mm, norm_scale):
                pdf.setFillColor(_SUCCESS if offcut.usable else _INK_MUTED)
                pdf.setFont(_FONT_REGULAR, label_font_pt)
                pdf.drawCentredString(
                    x + w / 2, y + h / 2 - 0.36 * label_font_pt, _offcut_label(offcut)
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

            row = parts_by_ref.get(placement.part_ref)
            sides = _banded_sides(row[0] if row else None, rotated=placement.rotated)
            if sides is not None:
                ticks = _band_tick_lines(placement, sides, norm_scale)
                if ticks:
                    pdf.saveState()
                    pdf.setLineCap(1)
                    pdf.setLineWidth((_BAND_STROKE / norm_scale) * scale)
                    pdf.setStrokeGray(0.15)
                    for x1, y1, x2, y2 in ticks:
                        pdf.line(
                            origin_x + x1 * scale,
                            origin_y + y1 * scale,
                            origin_x + x2 * scale,
                            origin_y + y2 * scale,
                        )
                    pdf.restoreState()

            if _label_fits(placement.length_mm, placement.width_mm, norm_scale):
                pdf.setFillColor(_INK_SOFT)
                pdf.setFont(_FONT_REGULAR, label_font_pt)
                pdf.drawCentredString(
                    x + w / 2,
                    y + h / 2 - 0.36 * label_font_pt,
                    _placement_label(placement, parts_by_ref),
                )

        pdf.setFillColor(_INK_MUTED)
        pdf.setFont(_FONT_REGULAR, 7)
        pdf.drawString(
            _MARGIN_X,
            12 * mm,
            f"{result.algorithm_name} {result.algorithm_version} · "
            f"waste {float(result.waste_percentage) * 100:.2f}%",
        )
        pdf.showPage()

    if not result.panels:
        pdf.setFont(_FONT_REGULAR, 12)
        pdf.drawString(_MARGIN_X, A4[1] - 18 * mm, "No panels")
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _register_fonts() -> None:
    registered = pdfmetrics.getRegisteredFontNames()
    if _FONT_REGULAR not in registered:
        pdfmetrics.registerFont(TTFont(_FONT_REGULAR, str(_FONTS_DIR / "DejaVuSans.ttf")))
    if _FONT_BOLD not in registered:
        pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(_FONTS_DIR / "DejaVuSans-Bold.ttf")))


class _BandedSides(NamedTuple):
    top: bool
    right: bool
    bottom: bool
    left: bool


def _page_size_for_panel(panel_length: int, panel_width: int) -> tuple[float, float]:
    return landscape(A4) if panel_length > panel_width else A4  # type: ignore[no-any-return]


def _sheet_transform(
    panel_length: int, panel_width: int, page_width: float, page_height: float
) -> tuple[float, float, float]:
    """(origin_x, origin_y, scale): sheet mm → page points, sheet centred in the
    band between the header and the footer."""
    max_w = page_width - 2 * _MARGIN_X
    max_h = page_height - _HEADER_H - _FOOTER_H
    scale = min(max_w / panel_length, max_h / panel_width)
    origin_x = _MARGIN_X + (max_w - panel_length * scale) / 2
    origin_y = _FOOTER_H + (max_h - panel_width * scale) / 2
    return origin_x, origin_y, scale


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
    return f"{name} {placement.length_mm}×{placement.width_mm}{rotated}"


def _offcut_label(offcut: CuttingOffcutResponse) -> str:
    if not offcut.usable:
        return "chiqit"
    return f"Qoldiq {offcut.length_mm}×{offcut.width_mm} — sizda qoladi"


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
    decor = snapshot.get("decor_code")
    if isinstance(decor, str) and decor:
        return decor
    name = snapshot.get("name")
    if isinstance(name, str) and name:
        return name
    return str(material_id)[:8]


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
