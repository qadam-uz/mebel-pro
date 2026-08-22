"""Unit tests for the pure PDF-layout helpers in cutting/rendering.py.

The PDF must be a faithful print rendering of the web panel visualiser
(web/src/shared/components/CuttingPanelSvg.vue); these tests pin the
transposition of its formulas into reportlab's bottom-left-origin space.
"""

# ruff: noqa: RUF001, RUF002 -- expected labels/docstrings reuse the visualiser's exact
# copy (multiplication sign in dimensions, U+21BB rotation marker)

import uuid
from io import BytesIO
from types import SimpleNamespace
from typing import Any

import pytest
from app.modules.cutting import rendering
from app.modules.cutting.schemas import CuttingOffcutResponse, CuttingPlacementResponse
from reportlab.pdfgen import canvas


def _placement(**overrides: Any) -> CuttingPlacementResponse:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "part_ref": "part-1",
        "part_quantity_index": 1,
        "x_mm": 100,
        "y_mm": 200,
        "length_mm": 600,
        "width_mm": 400,
        "rotated": False,
    }
    values.update(overrides)
    return CuttingPlacementResponse(**values)


def _offcut(*, usable: bool, length_mm: int = 500, width_mm: int = 300) -> CuttingOffcutResponse:
    return CuttingOffcutResponse(
        x_mm=0, y_mm=0, length_mm=length_mm, width_mm=width_mm, usable=usable
    )


# --- placement geometry ---------------------------------------------------


def test_placement_y_maps_straight_through_without_svg_flip() -> None:
    """Regression: the PDF used to re-apply the visualiser's SVG y-flip on top
    of reportlab's bottom-left origin, vertically mirroring every layout
    against the on-screen plan. Optimizer y_mm is bottom-left-origin already —
    it must map straight through."""
    origin_x, origin_y, scale = rendering._sheet_transform(2800, 2070, 500, 300)

    x, y, _w, _h = rendering._rect_points(
        0, 0, 600, 400, origin_x=origin_x, origin_y=origin_y, scale=scale
    )
    assert x == origin_x
    assert y == origin_y  # y_mm=0 is the sheet's bottom edge, not its top

    top = rendering._rect_points(
        0, 2070 - 400, 600, 400, origin_x=origin_x, origin_y=origin_y, scale=scale
    )
    assert top[1] + top[3] == pytest.approx(origin_y + 2070 * scale)


def test_sheet_transform_fits_and_centres_the_sheet() -> None:
    frame_width, frame_height = 500, 300
    origin_x, origin_y, scale = rendering._sheet_transform(
        2800, 2070, frame_width, frame_height, origin_x=10, origin_y=20
    )

    assert scale == pytest.approx(min(frame_width / 2800, frame_height / 2070))
    assert origin_x == pytest.approx(10 + (frame_width - 2800 * scale) / 2)
    assert origin_y == pytest.approx(20 + (frame_height - 2070 * scale) / 2)
    assert origin_x + 2800 * scale <= 10 + frame_width + 1e-6
    assert origin_y + 2070 * scale <= 20 + frame_height + 1e-6


# --- labels ---------------------------------------------------------------


def test_label_gate_matches_the_visualiser_thresholds() -> None:
    norm_scale = 800 / 2800
    assert rendering._label_fits(400, 200, norm_scale)
    assert not rendering._label_fits(250, 200, norm_scale)  # length gate (>80)
    assert not rendering._label_fits(400, 100, norm_scale)  # width gate (>30)


def test_placement_label_mode_edges_when_both_sides_have_room() -> None:
    """A part is identified by its size alone now (no name/number on the
    map), so each dimension prints against the side it measures whenever both
    fit — matching the web visualiser's Bazis-style layout."""
    rendering._register_fonts()
    placement = _placement(length_mm=600, width_mm=400)

    plan = rendering._placement_label_mode(placement, 10.0, 200.0, 150.0, 10.0)

    assert plan == rendering._DimensionLabelPlan("edges", "600", "400", 10.0)


def test_placement_label_mode_falls_back_to_inline_when_edges_dont_clear_the_inset() -> None:
    """When the inset clearance doesn't leave room for a dimension against its
    own (narrow) side, the whole `L×W` collapses onto one centred line."""
    rendering._register_fonts()
    placement = _placement(length_mm=600, width_mm=400)

    plan = rendering._placement_label_mode(placement, 10.0, 52.0, 150.0, 40.0)

    assert plan == rendering._DimensionLabelPlan("inline", "600×400", "", 10.0)


def test_placement_label_mode_rotates_inline_for_a_tall_narrow_strip() -> None:
    """A strip too narrow for any horizontal text still has to carry its size —
    a part is identified by its dimensions alone, so losing them is not an option."""
    rendering._register_fonts()
    placement = _placement(length_mm=80, width_mm=1800)

    plan = rendering._placement_label_mode(placement, 7.0, 12.0, 240.0, 3.0)

    assert plan == rendering._DimensionLabelPlan("inline_rotated", "80×1800", "", 7.0)


def test_placement_label_mode_shrinks_the_font_for_a_placement_too_small_at_the_sheet_size() -> (
    None
):
    """A part too small to label at the sheet's uniform font used to print with
    no size at all. It now keeps its own dimensions at a smaller font — every
    part on the map stays identifiable, even the tiny ones."""
    rendering._register_fonts()
    placement = _placement(length_mm=20, width_mm=20)

    at_sheet_size = rendering._fit_dimension_label(placement, 7.0, 8.0, 18.0, 3.0)
    plan = rendering._placement_label_mode(placement, 7.0, 8.0, 18.0, 3.0)

    assert at_sheet_size is None  # confirms this frame is a genuine shrink case
    assert plan is not None
    assert plan.font_pt < 7.0
    assert plan.font_pt >= rendering._MIN_LABEL_FONT_FLOOR_PT
    assert plan.length_text == "20×20"


def test_edges_mode_is_rejected_when_the_two_labels_would_collide_in_the_corner() -> None:
    """A near-square box can pass each dimension's own along/across check while
    the top-centred length text and the rotated, inset-anchored width text
    still overlap in the corner — regression for a real rendering defect where
    both numbers printed on top of each other."""
    rendering._register_fonts()
    placement = _placement(length_mm=60, width_mm=45)

    assert rendering._edges_labels_collide("60", "45", 4.0, 12.24, 9.18, 3.06)
    plan = rendering._fit_dimension_label(placement, 4.0, 12.24, 9.18, 3.06)

    assert plan is None or plan.mode != "edges"


def test_placement_label_mode_none_when_even_the_floor_size_does_not_fit() -> None:
    """The shrink loop reaches for a genuinely tiny font before giving up — this
    box has to be small enough that even the floor size overflows it."""
    rendering._register_fonts()
    placement = _placement(length_mm=600, width_mm=400)

    plan = rendering._placement_label_mode(placement, 10.0, 2.0, 2.0, 1.0)

    assert plan is None


def test_dim_fits_requires_room_along_its_axis_and_clearance_across_it() -> None:
    rendering._register_fonts()

    assert rendering._dim_fits("600", 10.0, along_pt=30.0, across_pt=150.0, inset_pt=10.0)
    assert not rendering._dim_fits(
        "600", 10.0, along_pt=20.0, across_pt=150.0, inset_pt=10.0
    )  # text itself doesn't fit along the side it measures
    assert not rendering._dim_fits(
        "600", 10.0, along_pt=30.0, across_pt=20.0, inset_pt=10.0
    )  # inset + font leave no clearance across the other axis


def test_offcut_label_mode_ladder() -> None:
    full = rendering._offcut_label_mode(_offcut(usable=True, length_mm=900, width_mm=160), 0.4)
    assert full == rendering._OffcutLabelMode(text="Qoldiq 900×160", orientation="horizontal")

    rotated = rendering._offcut_label_mode(_offcut(usable=True, length_mm=322, width_mm=1820), 0.27)
    assert rotated is not None
    assert rotated.orientation == "vertical"

    assert (
        rendering._offcut_label_mode(_offcut(usable=True, length_mm=30, width_mm=30), 0.4) is None
    )
    assert rendering._offcut_label_mode(
        _offcut(usable=False, length_mm=500, width_mm=300), 0.4
    ) == (rendering._OffcutLabelMode(text="chiqit", orientation="horizontal"))


# --- edge banding ---------------------------------------------------------


def test_banded_sides_identity_when_not_rotated() -> None:
    part = {"edge_top": {"material_id": "m"}, "edge_left": {"material_id": "m"}}
    sides = rendering._banded_sides(part, rotated=False)
    assert sides == rendering._BandedSides(top=True, right=False, bottom=False, left=True)


def test_banded_sides_map_clockwise_when_rotated() -> None:
    part = {"edge_top": {"material_id": "m"}}
    sides = rendering._banded_sides(part, rotated=True)
    assert sides == rendering._BandedSides(top=False, right=True, bottom=False, left=False)


def test_banded_sides_handle_missing_part_and_missing_keys() -> None:
    assert rendering._banded_sides(None, rotated=False) is None
    sides = rendering._banded_sides({}, rotated=False)
    assert sides == rendering._BandedSides(top=False, right=False, bottom=False, left=False)


def test_band_tick_lines_nominal_geometry() -> None:
    norm_scale = 800 / 2800
    placement = _placement(x_mm=100, y_mm=200, length_mm=600, width_mm=400)
    sides = rendering._BandedSides(top=True, right=True, bottom=True, left=True)
    lines = rendering._band_tick_lines(placement, sides, norm_scale)

    inset = 3 / norm_scale  # 10.5 — below the 30%-of-short-side cap (120)
    half = (30 / norm_scale) / 2  # 52.5 — below the 60%-of-side caps
    assert lines == [
        pytest.approx((400 - half, 600 - inset, 400 + half, 600 - inset)),  # top
        pytest.approx((400 - half, 200 + inset, 400 + half, 200 + inset)),  # bottom
        pytest.approx((100 + inset, 400 - half, 100 + inset, 400 + half)),  # left
        pytest.approx((700 - inset, 400 - half, 700 - inset, 400 + half)),  # right
    ]


def test_band_tick_lines_cap_inset_and_length_on_slivers() -> None:
    norm_scale = 800 / 800
    placement = _placement(x_mm=0, y_mm=0, length_mm=500, width_mm=8)
    sides = rendering._BandedSides(top=True, right=True, bottom=False, left=False)
    top, right = rendering._band_tick_lines(placement, sides, norm_scale)

    assert top[1] == pytest.approx(8 - 8 * 0.3)  # inset capped at 30% of the 8mm side
    assert top[2] - top[0] == pytest.approx(30)  # tick keeps its normalized 30mm length
    assert right[3] - right[1] == pytest.approx(8 * 0.6)  # vertical tick capped at 60% of side


# --- header ---------------------------------------------------------------


def test_panel_fill_percent() -> None:
    panel = SimpleNamespace(waste_area_mm2=2_800 * 2_070 // 4)
    assert rendering._panel_fill_percent(panel, 2800, 2070) == "75.0%"  # type: ignore[arg-type]
    assert rendering._panel_fill_percent(panel, 0, 2070) == "-"  # type: ignore[arg-type]


# --- thickening stamp ----------------------------------------------------


def test_thickened_flag_reads_the_part_snapshot_and_defaults_off() -> None:
    """Drafts predating the flag arrive without the key at all — an absent
    `thickened` must read as "not thickened", never as a stamp."""
    assert rendering._is_thickened({"thickened": True}) is True
    assert rendering._is_thickened({"thickened": False}) is False
    assert rendering._is_thickened({}) is False  # legacy snapshot
    assert rendering._is_thickened(None) is False  # placement with no known part


def test_thickening_stamp_prints_only_for_a_thickened_part() -> None:
    """The stamp is the only place the drawing carries the instruction to glue a
    strip under the part — if it silently stopped printing, the shop would build
    the wrong thing and nothing else on the sheet would say so."""
    rendering._register_fonts()
    plain = _placement(part_ref="plain", length_mm=600, width_mm=400)
    thick = _placement(part_ref="thick", length_mm=600, width_mm=400)
    result = SimpleNamespace(
        parts_snapshot=[
            {"part_ref": "plain", "length_mm": 600, "width_mm": 400},
            {"part_ref": "thick", "length_mm": 600, "width_mm": 400, "thickened": True},
        ],
        material_snapshots={"m": {"panel_length_mm": 2750, "panel_width_mm": 1830}},
    )
    panel = SimpleNamespace(material_id="m", placements=[plain, thick], offcuts=[])

    drawn: list[str] = []
    pdf = canvas.Canvas(BytesIO(), pagesize=(600, 400))
    original = pdf.drawCentredString

    def spy(x: float, y: float, text: str, *args: Any, **kwargs: Any) -> None:
        drawn.append(text)
        original(x, y, text, *args, **kwargs)

    pdf.drawCentredString = spy  # type: ignore[method-assign]
    rendering.draw_sheet_map(pdf, (0.0, 0.0, 560.0, 360.0), result, panel)  # type: ignore[arg-type]

    assert drawn.count(rendering._THICKENING_MARK) == 1


# --- grain hatch ---------------------------------------------------------


def test_follow_grain_flag_reads_the_part_snapshot_and_defaults_on() -> None:
    """The default for a missing key is **on**, the mirror image of `thickened`.

    `CuttingDraftPart.follow_grain` is `bool = True`, so every snapshot the app
    writes carries the key; a raw dict without it is an old or hand-built one
    whose parts followed that same default. Reading it as False would quietly
    un-mark exactly the parts a cutter must not turn.
    """
    assert rendering._follows_grain({"follow_grain": True}) is True
    assert rendering._follows_grain({"follow_grain": False}) is False
    assert rendering._follows_grain({}) is True  # legacy snapshot, default on
    assert rendering._follows_grain(None) is False  # placement with no known part


def test_grain_hatch_lines_nominal_geometry() -> None:
    """Twin of the `<pattern>` case in
    web/src/shared/components/__tests__/CuttingPanelSvg.spec.ts — same pitch
    formula, same phase rule. Nothing mechanical keeps the two in step, so
    change them together."""
    norm_scale = 800 / 2800  # pitch = 8 / norm_scale = 28.0 sheet mm
    placement = _placement(x_mm=100, y_mm=200, length_mm=600, width_mm=400)

    lines = rendering._grain_hatch_lines(placement, norm_scale, horizontal=True)

    # Phased from the sheet origin, not the placement: the first line is the
    # first multiple of 28 above y=200, and the last one stays below y=600.
    assert lines[0] == pytest.approx((100.0, 224.0, 700.0, 224.0))
    assert lines[1] == pytest.approx((100.0, 252.0, 700.0, 252.0))
    assert lines[-1] == pytest.approx((100.0, 588.0, 700.0, 588.0))
    assert len(lines) == 14
    assert all(y1 == y2 for _, y1, _, y2 in lines)


def test_grain_hatch_runs_along_the_sheets_long_side() -> None:
    """A portrait sheet turns the ladder 90°. The one case a hardcoded
    "horizontal" would print across the board instead of along it."""
    norm_scale = 800 / 900
    placement = _placement(x_mm=0, y_mm=0, length_mm=400, width_mm=900)

    lines = rendering._grain_hatch_lines(placement, norm_scale, horizontal=False)

    assert lines
    assert all(x1 == x2 for x1, _, x2, _ in lines)
    assert all(y1 == 0 and y2 == 900 for _, y1, _, y2 in lines)


def test_grain_hatch_skips_a_placement_thinner_than_one_gap() -> None:
    """A sliver narrower than the pitch draws nothing rather than a line on its
    own edge — the edge is already a stroke."""
    norm_scale = 800 / 2800
    placement = _placement(x_mm=0, y_mm=0, length_mm=600, width_mm=20)

    assert rendering._grain_hatch_lines(placement, norm_scale, horizontal=True) == []


def test_grain_hatch_prints_only_for_a_grain_locked_part() -> None:
    """The hatch is the only mark that says "do not turn this part". If it
    stopped printing, a textured board would be cut across the grain and
    nothing else on the sheet would say so."""
    rendering._register_fonts()
    free = _placement(part_ref="free", x_mm=0, y_mm=0, length_mm=600, width_mm=400)
    locked = _placement(part_ref="locked", x_mm=800, y_mm=0, length_mm=600, width_mm=400)
    result = SimpleNamespace(
        parts_snapshot=[
            {"part_ref": "free", "length_mm": 600, "width_mm": 400, "follow_grain": False},
            {"part_ref": "locked", "length_mm": 600, "width_mm": 400, "follow_grain": True},
        ],
        material_snapshots={"m": {"panel_length_mm": 2750, "panel_width_mm": 1830}},
    )
    panel = SimpleNamespace(material_id="m", placements=[free, locked], offcuts=[])

    batches: list[int] = []
    pdf = canvas.Canvas(BytesIO(), pagesize=(600, 400))
    original = pdf.lines

    def spy(lines: Any, *args: Any, **kwargs: Any) -> None:
        batches.append(len(lines))
        original(lines, *args, **kwargs)

    pdf.lines = spy  # type: ignore[method-assign]
    rendering.draw_sheet_map(pdf, (0.0, 0.0, 560.0, 360.0), result, panel)  # type: ignore[arg-type]

    # One batch, for the locked placement only. `pdf.lines` is used nowhere else
    # in draw_sheet_map, so the count is unambiguous.
    assert len(batches) == 1
    assert batches[0] > 0
