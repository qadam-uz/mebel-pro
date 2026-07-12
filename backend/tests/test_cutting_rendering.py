"""Unit tests for the pure PDF-layout helpers in cutting/rendering.py.

The PDF must be a faithful print rendering of the web panel visualiser
(web/src/shared/components/CuttingPanelSvg.vue); these tests pin the
transposition of its formulas into reportlab's bottom-left-origin space.
"""

# ruff: noqa: RUF001 -- expected labels reuse the visualiser's exact copy (multiplication
# sign in dimensions, U+21BB rotation marker)

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from app.modules.cutting import rendering
from app.modules.cutting.schemas import CuttingOffcutResponse, CuttingPlacementResponse


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


def _parts_by_ref(parts: list[dict[str, Any]]) -> dict[str, tuple[dict[str, Any], int]]:
    return rendering._parts_by_ref(SimpleNamespace(parts_snapshot=parts))  # type: ignore[arg-type]


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


def test_placement_label_uses_part_name() -> None:
    parts = _parts_by_ref([{"part_ref": "a", "name": "Polka"}])
    label = rendering._placement_label(_placement(part_ref="a"), parts)
    assert label == "#1 Polka 600×400"


def test_placement_label_falls_back_to_row_number_for_blank_names() -> None:
    parts = _parts_by_ref(
        [
            {"part_ref": "a", "name": "Polka"},
            {"part_ref": "b", "name": "   "},
            {"part_ref": "c"},
        ]
    )
    assert rendering._placement_label(_placement(part_ref="b"), parts) == "#2 D2 600×400"
    assert rendering._placement_label(_placement(part_ref="c"), parts) == "#3 D3 600×400"


def test_placement_label_marks_rotated_placements() -> None:
    parts = _parts_by_ref([{"part_ref": "a", "name": "Polka"}])
    label = rendering._placement_label(_placement(part_ref="a", rotated=True), parts)
    assert label == "#1 Polka 600×400 ↻"


def test_placement_label_falls_back_to_ref_for_unknown_parts() -> None:
    label = rendering._placement_label(_placement(part_ref="ghost"), {})
    assert label == "ghost 600×400"


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


def test_material_label_uses_catalog_identity_format() -> None:
    assert (
        rendering._material_label(
            {
                "type": "dsp",
                "manufacturer_name": "Egger",
                "decor_code": "H1334 ST9",
                "name": "Dub",
                "color": "Sanoma",
                "thickness_mm": "18.0",
                "panel_length_mm": 2750,
                "panel_width_mm": 1830,
            },
            "id",
        )
        == "LDSP Egger H1334 ST9 · Sanoma · 2750×1830×18 mm"
    )
    assert rendering._material_label({"name": "Dub"}, "id") == "Dub"
    assert rendering._material_label({}, "0123456789abcdef") == "01234567"
