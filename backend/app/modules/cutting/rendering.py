"""Map drawing primitives for immutable cutting result PDFs.

The detailed PDF document is a production report, not a bare visualiser mirror.
The parity contract is now scoped to the map panel only: placements, offcut
overlays, label fitting and edge-banding ticks mirror
web/src/shared/components/CuttingPanelSvg.vue. All helper geometry is expressed
in sheet millimetres with the y axis growing up — the optimizer's own convention,
which is also reportlab's page convention.
"""

# ruff: noqa: RUF001, RUF002 -- labels and docstrings reuse the visualiser's exact
# copy (multiplication sign in dimensions, U+21BB rotation marker)

from __future__ import annotations

from typing import Any, NamedTuple

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
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
# Grain marking, mirroring CuttingPanelSvg.vue: a part the optimizer may not
# turn is filled with hairlines running along the sheet's texture (its long
# side). Same normalization as the labels and the band ticks.
_GRAIN_STROKE = 1.0
_GRAIN_GAP = 8.0
# The band ticks floor at 0.8pt because a tape mark that thin stops reading as a
# mark. A hairline is the opposite: it must stay a hairline, and at the sheet-
# group frame the natural width is already ~0.5pt. Clamping it to the tick floor
# would make it as heavy as the tape it must sit under. 0.25pt is the classic
# hairline minimum — thinner than that, a 96dpi preview drops it entirely.
_MIN_GRAIN_STROKE_PT = 0.25
# Dimension texts sit against the side they measure, like the web visualiser
# (CuttingPanelSvg.vue). The inset clears the band tick (_BAND_INSET + stroke)
# with room to spare, so a number never lands on a tape mark.
_DIM_INSET = 12.0
# A placement too small for the sheet's uniform label size shrinks its own
# text rather than going unlabelled — every part keeps its size on paper, at
# whatever font still fits inside it. The floor is a last-resort minimum, not
# a target: almost every part prints at the sheet's uniform size. Two sheets
# now always share a page (never a page of its own for a dense one), so the
# map itself is smaller than it used to be — a 100mm part on an ordinary
# 2750mm sheet is only ~14pt on paper, and the text is vector, not raster: a
# print shop reads this up close or zooms a PDF, so a small-but-correct
# number beats a blank rectangle. The floor only exists to stop the loop
# short of a font with literally no width — a genuinely sub-30mm sliver
# still goes unlabelled rather than printing an invisible dot.
_MIN_LABEL_FONT_FLOOR_PT = 1.5
_LABEL_FONT_SHRINK_STEP_PT = 0.1
# Breathing room between the text and the edge of its own axis. A flat 4pt
# was sized for the sheet's uniform label, where it's a rounding error; at
# the smaller sizes the shrink loop reaches for, that same 4pt can be most of
# the placement's own box, so it alone was blocking a label a genuinely
# fitting font would otherwise print.
_LABEL_TEXT_PADDING_PT = 1.0
# The shop-floor shorthand for a part that gets a strip glued underneath
# (utolshenie / obmanka). Cyrillic on purpose: it is what the operators read.
_THICKENING_MARK = "УТ"
# Rough printed width of the two-glyph stamp as a multiple of its font size,
# used to shrink it into a narrow placement without a metrics round-trip.
_THICKENING_TEXT_W_FACTOR = 1.5

# Print equivalents of the web tokens the visualiser uses. Structure stays
# grayscale for print; colour is reserved for the offcut semantics.
_SUCCESS = HexColor("#067a4b")  # --color-success: usable offcut
_DANGER = HexColor("#c9302a")  # --color-danger: waste offcut
_INK_MUTED = HexColor("#666d79")  # --color-ink-muted: waste offcut label, footer
_INK_SOFT = HexColor("#565c66")  # --color-ink-soft: placement labels
# --color-ink (#0f1115) at 17% over the white placement fill, composited by
# hand. The screen draws the hairline with stroke-opacity; the PDF pre-composites
# instead, because the placement fill here is deliberately pure white (see the
# note on setFillGray below) — so the result is pixel-identical, the document
# stays free of a transparency group, and no shop RIP has to flatten one.
_GRAIN = HexColor("#d6d7d7")

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


class _DimensionLabelPlan(NamedTuple):
    """`edges` carries both numbers separately; `inline` carries `L×W` centred.

    `font_pt` is the size this specific plan was fitted at — the sheet's
    uniform size for almost every part, smaller only for the placements that
    needed it.
    """

    mode: str
    length_text: str
    width_text: str
    font_pt: float


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
        # White, not the old light gray: a black-and-white printer's toner
        # coverage on a filled tint can blur the fine band ticks and text.
        pdf.setFillGray(1.0)
        pdf.rect(x, y, w, h, stroke=1, fill=1)

        row = parts.get(placement.part_ref)
        if _follows_grain(row[0] if row else None):
            hatch = _grain_hatch_lines(
                placement, norm_scale, horizontal=panel_length >= panel_width
            )
            if hatch:
                pdf.saveState()
                # Clip to the placement: the ladder is phased from the sheet
                # origin (so neighbouring grained parts share one set of lines,
                # as on screen), which means its segments are computed against
                # the sheet, not this rectangle.
                clip = pdf.beginPath()
                clip.rect(x, y, w, h)
                pdf.clipPath(clip, stroke=0, fill=0)
                pdf.setStrokeColor(_GRAIN)
                pdf.setLineWidth(max(_MIN_GRAIN_STROKE_PT, (_GRAIN_STROKE / norm_scale) * scale))
                pdf.setLineCap(0)
                pdf.lines(
                    [
                        (
                            origin_x + x1 * scale,
                            origin_y + y1 * scale,
                            origin_x + x2 * scale,
                            origin_y + y2 * scale,
                        )
                        for x1, y1, x2, y2 in hatch
                    ]
                )
                pdf.restoreState()

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

        dim_inset_pt = (_DIM_INSET / norm_scale) * scale
        label = _placement_label_mode(placement, label_font_pt, w, h, dim_inset_pt)
        if label is not None:
            pdf.setFillColor(_INK_SOFT)
            pdf.setFont(_FONT_REGULAR, label.font_pt)
            if label.mode == "edges":
                pdf.drawCentredString(
                    x + w / 2,
                    y + h - dim_inset_pt - 0.36 * label.font_pt,
                    label.length_text,
                )
                pdf.saveState()
                pdf.translate(x + dim_inset_pt, y + h / 2)
                pdf.rotate(90)
                pdf.drawCentredString(0, -0.36 * label.font_pt, label.width_text)
                pdf.restoreState()
            elif label.mode == "inline_rotated":
                pdf.saveState()
                pdf.translate(x + w / 2, y + h / 2)
                pdf.rotate(90)
                pdf.drawCentredString(0, -0.36 * label.font_pt, label.length_text)
                pdf.restoreState()
            else:
                pdf.drawCentredString(
                    x + w / 2, y + h / 2 - 0.36 * label.font_pt, label.length_text
                )

        if _is_thickened(row[0] if row else None):
            _draw_thickening_mark(pdf, x, y, w, h, label, label_font_pt)


def _is_thickened(part: dict[str, Any] | None) -> bool:
    return bool(part.get("thickened")) if part else False


def _follows_grain(part: dict[str, Any] | None) -> bool:
    """Whether the optimizer was forbidden to turn this part.

    The default for a missing key is **True**, the opposite of `_is_thickened`:
    `CuttingDraftPart.follow_grain` is `bool = True` (schemas.py), so a snapshot
    written by the app always carries the key, and a raw dict that does not is
    an old or hand-built one whose parts followed the same default. Reading a
    missing key as False would quietly un-mark them.

    A placement with no part at all (`None`) is a different case: we do not know
    its grain, so it stays flat rather than claiming a lock — the same rule the
    visualiser's `followsGrain` follows for an orphan `part_ref`.
    """
    return bool(part.get("follow_grain", True)) if part is not None else False


def _draw_thickening_mark(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    label: _DimensionLabelPlan | None,
    sheet_font_pt: float,
) -> None:
    """The `УТ` stamp: this part gets a strip glued under it (утолщение).

    It owns the centre of the placement. When the dimensions were small enough
    to collapse into the centre too, the stamp drops just under them rather
    than overprinting; when nothing else fits, the stamp still prints — the
    register carries every size anyway, but the thickening instruction exists
    nowhere else on the drawing.
    """
    font_pt = min(sheet_font_pt, label.font_pt if label else sheet_font_pt)
    if _THICKENING_TEXT_W_FACTOR * font_pt + _LABEL_TEXT_PADDING_PT > w:
        font_pt = max(
            _MIN_LABEL_FONT_FLOOR_PT,
            (w - _LABEL_TEXT_PADDING_PT) / _THICKENING_TEXT_W_FACTOR,
        )
    centre_taken = label is not None and label.mode != "edges"
    baseline = y + h / 2 - 0.36 * font_pt
    if centre_taken:
        baseline -= font_pt * 1.15
        if baseline < y + _LABEL_TEXT_PADDING_PT:
            return
    pdf.setFillColor(_INK_SOFT)
    pdf.setFont(_FONT_BOLD, font_pt)
    pdf.drawCentredString(x + w / 2, baseline, _THICKENING_MARK)
    pdf.setFont(_FONT_REGULAR, font_pt)


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


def _placement_label_mode(
    placement: CuttingPlacementResponse,
    font_pt: float,
    width_pt: float,
    height_pt: float,
    inset_pt: float,
) -> _DimensionLabelPlan | None:
    """Decide how a placement carries its own dimensions, shrinking the font
    for this one placement if the sheet's uniform size doesn't fit it.

    A part is identified by its size, never by a name or row number, so the
    dimensions are the one thing that must survive — a part small enough to
    defeat the ladder at every size down to the floor is the only case that
    prints with no label. Every other placement gets *some* legible number,
    even if it's smaller than its neighbours.
    """
    size = font_pt
    while size >= _MIN_LABEL_FONT_FLOOR_PT:
        plan = _fit_dimension_label(placement, size, width_pt, height_pt, inset_pt)
        if plan is not None:
            return plan
        size -= _LABEL_FONT_SHRINK_STEP_PT
    return None


def _fit_dimension_label(
    placement: CuttingPlacementResponse,
    font_pt: float,
    width_pt: float,
    height_pt: float,
    inset_pt: float,
) -> _DimensionLabelPlan | None:
    """The fitting ladder at one fixed font size: `edges` places each number
    against the side it measures (Bazis-style, matching the web visualiser);
    `inline` puts both on a single `L×W` line when the part is too tight for
    the rotated number; `inline_rotated` turns that line 90° so a tall,
    narrow strip — the shape that defeats every horizontal option — still
    carries its size. `None` means this size doesn't fit at all."""
    length_text = str(placement.length_mm)
    width_text = str(placement.width_mm)
    edges_fit = (
        _dim_fits(length_text, font_pt, width_pt, height_pt, inset_pt)
        and _dim_fits(width_text, font_pt, height_pt, width_pt, inset_pt)
        and not _edges_labels_collide(
            length_text, width_text, font_pt, width_pt, height_pt, inset_pt
        )
    )
    if edges_fit:
        return _DimensionLabelPlan("edges", length_text, width_text, font_pt)
    inline = f"{length_text}×{width_text}"
    if _printed_text_fits(inline, font_pt, width_pt, height_pt):
        return _DimensionLabelPlan("inline", inline, "", font_pt)
    if _printed_text_fits(inline, font_pt, height_pt, width_pt):
        return _DimensionLabelPlan("inline_rotated", inline, "", font_pt)
    return None


def _edges_labels_collide(
    length_text: str,
    width_text: str,
    font_pt: float,
    width_pt: float,
    height_pt: float,
    inset_pt: float,
) -> bool:
    """`_dim_fits` only checks each dimension against its own edge — on a small,
    close-to-square placement both texts can independently "fit" while their
    printed boxes still overlap in the corner (the top-centred length text
    reaches left past the inset column the rotated width text sits in). An
    axis-aligned bounding-box test on both labels' actual footprints catches
    that regardless of which axis the collision happens on."""
    top_w = float(pdfmetrics.stringWidth(length_text, _FONT_REGULAR, font_pt))
    side_w = float(pdfmetrics.stringWidth(width_text, _FONT_REGULAR, font_pt))
    side_thickness = font_pt * 0.9
    top_x0, top_x1 = width_pt / 2 - top_w / 2, width_pt / 2 + top_w / 2
    top_y0, top_y1 = height_pt - inset_pt - font_pt * 1.35, height_pt
    side_x0, side_x1 = inset_pt - side_thickness / 2, inset_pt + side_thickness / 2
    side_y0, side_y1 = height_pt / 2 - side_w / 2, height_pt / 2 + side_w / 2
    return (top_x0 < side_x1 and side_x0 < top_x1) and (top_y0 < side_y1 and side_y0 < top_y1)


def _dim_fits(
    text: str, font_pt: float, along_pt: float, across_pt: float, inset_pt: float
) -> bool:
    """A dimension needs room along its own axis and clearance from the side it
    labels — the inset is what keeps it off the band tick."""
    return (
        pdfmetrics.stringWidth(text, _FONT_REGULAR, font_pt) + _LABEL_TEXT_PADDING_PT <= along_pt
        and inset_pt + font_pt * 1.35 <= across_pt
    )


def _printed_text_fits(text: str, font_pt: float, width_pt: float, height_pt: float) -> bool:
    return (
        pdfmetrics.stringWidth(text, _FONT_REGULAR, font_pt) + _LABEL_TEXT_PADDING_PT <= width_pt
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


def _grain_hatch_lines(
    placement: CuttingPlacementResponse, norm_scale: float, *, horizontal: bool
) -> list[tuple[float, float, float, float]]:
    """Hairlines across a grain-locked placement, in sheet mm (y up).

    Twin of the `<pattern>` in CuttingPanelSvg.vue: the pitch is the same
    `_GRAIN_GAP / norm_scale`, and the ladder is phased from the **sheet
    origin** rather than the placement's own edge, so two grained parts side by
    side share one set of lines and the sheet reads as a single grained board.
    The caller clips to the placement; the segments themselves are already
    trimmed to it, so the clip only guards the stroke's own width.
    """
    gap = _GRAIN_GAP / norm_scale
    if gap <= 0:
        return []
    x0 = float(placement.x_mm)
    y0 = float(placement.y_mm)
    x1 = x0 + placement.length_mm
    y1 = y0 + placement.width_mm
    lines: list[tuple[float, float, float, float]] = []
    if horizontal:
        # First multiple of `gap` at or above the placement's bottom edge.
        y = (int(y0 / gap) + 1) * gap
        while y < y1:
            lines.append((x0, y, x1, y))
            y += gap
    else:
        x = (int(x0 / gap) + 1) * gap
        while x < x1:
            lines.append((x, y0, x, y1))
            x += gap
    return lines


def _panel_fill_percent(panel: CuttingPanelResponse, panel_length: int, panel_width: int) -> str:
    area = panel_length * panel_width
    if area <= 0:
        return "-"
    return f"{max(0.0, 100.0 - panel.waste_area_mm2 / area * 100.0):.1f}%"


def _material_snapshot(result: CuttingResultResponse, material_id: object) -> dict[str, object]:
    return result.material_snapshots.get(str(material_id), {})


def _panel_length(result: CuttingResultResponse, panel: CuttingPanelResponse) -> int:
    snapshot = _material_snapshot(result, panel.material_id)
    return _int_snapshot(_snapshot_size(snapshot, "length_mm", "panel_length_mm"), fallback=1000)


def _panel_width(result: CuttingResultResponse, panel: CuttingPanelResponse) -> int:
    snapshot = _material_snapshot(result, panel.material_id)
    return _int_snapshot(_snapshot_size(snapshot, "width_mm", "panel_width_mm"), fallback=700)


def _snapshot_size(snapshot: dict[str, object], key: str, legacy_key: str) -> object:
    """New snapshot key first, pre-reshape key as the fallback.

    Both vocabularies live in the DB forever — `material_snapshots` is frozen
    history the migration deliberately does not rewrite. Reading only the new
    key would silently draw every pre-reshape sheet map at the 1000×700
    fallback, with every placement scaled wrong and no error raised.
    """
    value = snapshot.get(key)
    return value if value is not None else snapshot.get(legacy_key)


def _int_snapshot(value: object, *, fallback: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return fallback
