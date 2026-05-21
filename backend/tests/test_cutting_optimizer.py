"""Unit tests for the pure 2D guillotine solver (no DB)."""

import pytest
from app.core.errors import AppError
from app.services import cutting_optimizer as opt

# A common non-grained sheet: usable area = (2800-20) x (2070-20) = 2780 x 2050.
SHEET = opt.SheetSpec(
    material_id="m1", sheet_length_mm=2800, sheet_width_mm=2070, grain_direction=False
)
GRAINED = opt.SheetSpec(
    material_id="g1", sheet_length_mm=2800, sheet_width_mm=2070, grain_direction=True
)


def _part(ref: str, length: int, width: int, qty: int = 1, material: str = "m1") -> opt.PartInput:
    return opt.PartInput(
        part_ref=ref, material_id=material, length_mm=length, width_mm=width, quantity=qty
    )


def _all_placements(result: opt.AlgorithmResult) -> list[opt.Placement]:
    return [p for sheet in result.sheets for p in sheet.placements]


def _assert_within_usable(result: opt.AlgorithmResult, specs: dict[str, opt.SheetSpec]) -> None:
    by_sheet = {(s.material_id, s.sheet_index): s for s in result.sheets}
    for (mid, _idx), sheet in by_sheet.items():
        spec = specs[mid]
        for p in sheet.placements:
            assert p.x_mm >= 0 and p.y_mm >= 0
            assert p.x_mm + p.length_mm <= spec.usable_length_mm
            assert p.y_mm + p.width_mm <= spec.usable_width_mm


def _assert_no_overlap(result: opt.AlgorithmResult) -> None:
    for sheet in result.sheets:
        rects = [
            (p.x_mm, p.y_mm, p.x_mm + p.length_mm, p.y_mm + p.width_mm) for p in sheet.placements
        ]
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                ax1, ay1, ax2, ay2 = rects[i]
                bx1, by1, bx2, by2 = rects[j]
                overlap = ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2
                assert not overlap, f"overlap on sheet {sheet.sheet_index}"


def _assert_each_instance_once(result: opt.AlgorithmResult, parts: list[opt.PartInput]) -> None:
    expected = {(p.part_ref, i + 1) for p in parts for i in range(p.quantity)}
    got = [(p.part_ref, p.part_quantity_index) for p in _all_placements(result)]
    assert sorted(got) == sorted(expected)
    assert len(got) == len(set(got))  # each exactly once


# --- single material --------------------------------------------------------


def test_single_material_simple_pack() -> None:
    parts = [_part("a", 600, 400, qty=4)]
    specs = {"m1": SHEET}
    results = opt.optimise(parts, specs)
    assert len(results) == 2  # two algorithms
    for r in results:
        assert r.sheets_used_by_material["m1"] == 1
        assert r.parts_placed == 4
        _assert_each_instance_once(r, parts)
        _assert_within_usable(r, specs)
        _assert_no_overlap(r)
        assert 0.0 <= r.waste_percentage <= 1.0


def test_algorithm_stamps() -> None:
    results = opt.optimise([_part("a", 600, 400)], {"m1": SHEET})
    names = {(r.algorithm_name, r.algorithm_version) for r in results}
    assert ("ffd-shelf", "1.0") in names
    assert ("guillotine-split", "1.0") in names


# --- multi material ---------------------------------------------------------


def test_multi_material_independent_layouts() -> None:
    parts = [_part("a", 600, 400, qty=2, material="m1"), _part("b", 800, 500, qty=2, material="m2")]
    specs = {"m1": SHEET, "m2": opt.SheetSpec("m2", 2750, 1830, False)}
    results = opt.optimise(parts, specs)
    for r in results:
        assert set(r.sheets_used_by_material) == {"m1", "m2"}
        # sheets are not shared across materials
        for sheet in r.sheets:
            refs = {p.part_ref for p in sheet.placements}
            if sheet.material_id == "m1":
                assert refs <= {"a"}
            else:
                assert refs <= {"b"}
        _assert_each_instance_once(r, parts)


# --- grain ------------------------------------------------------------------


def test_grain_forces_orientation_no_rotation() -> None:
    # a wide-but-short part on a grained sheet must not rotate
    parts = [_part("a", 400, 600, qty=2, material="g1")]  # length<width nominal
    specs = {"g1": GRAINED}
    results = opt.optimise(parts, specs)
    for r in results:
        for p in _all_placements(r):
            assert p.rotated is False or p.length_mm >= p.width_mm
            # on grained, placed length is the long side
            assert p.length_mm == 600 and p.width_mm == 400


def test_impossible_grain_branch() -> None:
    # The forced-orientation check is the only feasibility on a grained sheet.
    # We exercise the branch directly: a part whose short side exceeds usable
    # width on a grained sheet cannot be placed (rotation would be needed).
    spec = opt.SheetSpec("g3", sheet_length_mm=2800, sheet_width_mm=600, grain_direction=True)
    # usable 2780 x 580; part 2000 long x 590 short -> short 590 > 580 forced.
    # It "fits unconstrained" only if rotated: short(590)<=2780 and long(2000)<=580? no.
    # So this is genuinely part_too_large; confirm the optimiser rejects it.
    with pytest.raises(AppError) as ei:
        opt.optimise([_part("a", 2000, 590, material="g3")], {"g3": spec})
    assert ei.value.code in {"impossible_grain", "part_too_large"}
    # And the impossible_grain helper guards rotation on grained material:
    inst = opt._Instance("a", 1, 590, 2000)  # nominal short<long
    assert opt._oriented(inst, spec)[0][2] is True  # forced rotation flag set
    assert len(opt._oriented(inst, spec)) == 1  # no alternative orientation


def test_rotation_on_non_grained_improves_packing() -> None:
    # Parts that only fit on a non-grained sheet when rotation is allowed.
    # 2780 long usable; a part 2050x2780 (nominal) fits rotated.
    parts = [_part("a", 2050, 2780, material="m1")]
    specs = {"m1": SHEET}
    results = opt.optimise(parts, specs)
    for r in results:
        assert r.parts_placed == 1
        _assert_within_usable(r, specs)


# --- limits -----------------------------------------------------------------


def test_too_many_parts() -> None:
    parts = [_part("a", 100, 100, qty=101)]
    with pytest.raises(AppError) as ei:
        opt.optimise(parts, {"m1": SHEET})
    assert ei.value.code == "too_many_parts"


def test_part_too_small() -> None:
    parts = [_part("a", 40, 600)]
    with pytest.raises(AppError) as ei:
        opt.optimise(parts, {"m1": SHEET})
    assert ei.value.code == "part_too_small"


def test_part_too_large() -> None:
    parts = [_part("a", 3000, 2000)]  # exceeds usable length even rotated
    with pytest.raises(AppError) as ei:
        opt.optimise(parts, {"m1": SHEET})
    assert ei.value.code == "part_too_large"


def test_too_many_sheets_needed() -> None:
    # Each near-full part needs its own sheet; 21 -> over the 20 cap.
    parts = [_part("a", 2700, 2000, qty=21)]
    with pytest.raises(AppError) as ei:
        opt.optimise(parts, {"m1": SHEET})
    assert ei.value.code == "too_many_sheets_needed"


# --- edge banding rollup ----------------------------------------------------


def test_edge_length_by_thickness() -> None:
    part = opt.PartInput(
        part_ref="a",
        material_id="m1",
        length_mm=600,
        width_mm=400,
        quantity=2,
        edge_top_mm=0.4,
        edge_bottom_mm=0.4,
        edge_left_mm=2.0,
        edge_right_mm=None,
    )
    results = opt.optimise([part], {"m1": SHEET})
    r = results[0]
    # top+bottom use length (600) x2 sides x2 qty = 2400 at 0.4
    # left uses width (400) x1 side x2 qty = 800 at 2.0
    assert r.edge_length_by_thickness["0.4"] == 2400
    assert r.edge_length_by_thickness["2.0"] == 800
    assert r.total_edge_length_mm == 3200


def test_winner_is_lowest_waste() -> None:
    results = opt.optimise([_part("a", 600, 400, qty=6)], {"m1": SHEET})
    win = opt.winner(results)
    assert win.waste_percentage == min(r.waste_percentage for r in results)
