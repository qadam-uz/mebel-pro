"""The 2D guillotine cutting-stock solver — pure, no DB, fully unit-testable.

Spec: docs/ref/features/cutting.md.

In: a list of parts, each picking its own material; out: an independent
per-material sheet layout, weighted waste %, and the structural metrics the
order needs for pricing. Guillotine cuts only (recursive edge-to-edge splits).

Two named algorithms run against the same input:

* ``ffd-shelf`` — first-fit-decreasing shelf packing.
* ``guillotine-split`` — recursive free-rectangle (guillotine) packing.

Both honour the same constraints, kerf, edge trim, and grain rule. Global
constants live here: ``KERF_MM`` and ``EDGE_TRIM_MM``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.core.errors import AppError

# --- global constants -------------------------------------------------------

KERF_MM = 4
EDGE_TRIM_MM = 10
PART_MIN_MM = 50
MAX_PARTS = 100
MAX_SHEETS_PER_MATERIAL = 20
RUN_BUDGET_SECONDS = 5.0


# --- errors (spec codes) ----------------------------------------------------


def _err(code: str, detail: str, *, status_code: int = 422) -> AppError:
    return AppError(code, detail, status_code=status_code)


# --- inputs -----------------------------------------------------------------


@dataclass(frozen=True)
class PartInput:
    """One part line as the optimiser sees it (already validated upstream)."""

    part_ref: str
    material_id: str
    length_mm: int
    width_mm: int
    quantity: int
    edge_top_mm: float | None = None
    edge_bottom_mm: float | None = None
    edge_left_mm: float | None = None
    edge_right_mm: float | None = None


@dataclass(frozen=True)
class SheetSpec:
    """The standard sheet for one material."""

    material_id: str
    sheet_length_mm: int
    sheet_width_mm: int
    grain_direction: bool

    @property
    def usable_length_mm(self) -> int:
        return self.sheet_length_mm - 2 * EDGE_TRIM_MM

    @property
    def usable_width_mm(self) -> int:
        return self.sheet_width_mm - 2 * EDGE_TRIM_MM


# --- outputs ----------------------------------------------------------------


@dataclass
class Placement:
    """One placed part-instance on one sheet. Origin = bottom-left of usable area."""

    part_ref: str
    part_quantity_index: int
    x_mm: int
    y_mm: int
    length_mm: int
    width_mm: int
    rotated: bool


@dataclass
class Sheet:
    """One physical sheet within a material's layout."""

    material_id: str
    sheet_index: int  # 1..N within the material
    placements: list[Placement] = field(default_factory=list)
    waste_area_mm2: int = 0


@dataclass
class AlgorithmResult:
    """The full output of one algorithm across all materials."""

    algorithm_name: str
    algorithm_version: str
    kerf_mm: int
    edge_trim_mm: int
    sheets: list[Sheet]
    sheets_used_by_material: dict[str, int]
    waste_percentage: float  # 0..1, weighted across materials
    total_cut_length_mm: int
    total_edge_length_mm: int
    edge_length_by_thickness: dict[str, int]
    parts_placed: int


# --- internal helpers -------------------------------------------------------


@dataclass(frozen=True)
class _Instance:
    """A single concrete piece to place (one quantity index of a part)."""

    part_ref: str
    quantity_index: int
    length_mm: int
    width_mm: int


def _deadline_guard(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise _err("optimization_timeout", "Optimisation exceeded the 5 s budget.")


def _oriented(inst: _Instance, spec: SheetSpec) -> list[tuple[int, int, bool]]:
    """Allowed (length, width, rotated) orientations for an instance on its sheet.

    Grained material: forced orientation, no rotation. The part's longer side
    aligns with the sheet's long side. Non-grained: both orientations allowed.
    """
    long_side = max(inst.length_mm, inst.width_mm)
    short_side = min(inst.length_mm, inst.width_mm)
    if spec.grain_direction:
        # length aligned to the sheet long side; no rotation
        return [(long_side, short_side, long_side != inst.length_mm)]
    # rotation allowed: try both, longer-along-length first (better packing)
    return [
        (long_side, short_side, long_side != inst.length_mm),
        (short_side, long_side, short_side != inst.length_mm),
    ]


def _fits_some_orientation(inst: _Instance, spec: SheetSpec) -> bool:
    ul, uw = spec.usable_length_mm, spec.usable_width_mm
    return any(length <= ul and width <= uw for length, width, _ in _oriented(inst, spec))


def _expand(part: PartInput) -> list[_Instance]:
    return [
        _Instance(part.part_ref, i + 1, part.length_mm, part.width_mm) for i in range(part.quantity)
    ]


# --- algorithm 1: first-fit-decreasing shelf --------------------------------


def _pack_ffd_shelf(instances: list[_Instance], spec: SheetSpec, deadline: float) -> list[Sheet]:
    """Shelf packing: lay parts left-to-right on horizontal shelves, opening a
    new shelf (then a new sheet) when the current one cannot host the part.

    Each shelf is a guillotine band: a horizontal cut separates shelves, a
    vertical cut between parts within a shelf — guillotine-compatible.
    """
    ul, uw = spec.usable_length_mm, spec.usable_width_mm
    # decreasing by the larger oriented dimension (height of the shelf it needs)
    order = sorted(
        instances,
        key=lambda inst: (max(inst.length_mm, inst.width_mm), inst.length_mm * inst.width_mm),
        reverse=True,
    )

    sheets: list[Sheet] = []

    # a shelf: y origin, used width along x, shelf height
    def new_sheet() -> tuple[Sheet, list[dict[str, int]]]:
        return Sheet(material_id=spec.material_id, sheet_index=len(sheets) + 1), []

    sheet, shelves = new_sheet()
    sheet_top = 0  # consumed height (y) on the current sheet

    for inst in order:
        _deadline_guard(deadline)
        placed = False
        length, width, rotated = _oriented(inst, spec)[0]
        # choose orientation that fits the sheet at all (non-grained may need swap)
        for ori_l, ori_w, ori_r in _oriented(inst, spec):
            if ori_l <= ul and ori_w <= uw:
                length, width, rotated = ori_l, ori_w, ori_r
                break

        # try existing shelves on the current sheet (place along x; width = part length)
        for shelf in shelves:
            used_x = shelf["used_x"]
            shelf_h = shelf["height"]
            x_cursor = used_x + (KERF_MM if used_x > 0 else 0)
            if x_cursor + length <= ul and width <= shelf_h:
                sheet.placements.append(
                    Placement(
                        inst.part_ref,
                        inst.quantity_index,
                        x_cursor,
                        shelf["y"],
                        length,
                        width,
                        rotated,
                    )
                )
                shelf["used_x"] = x_cursor + length
                placed = True
                break
        if placed:
            continue

        # open a new shelf on the current sheet
        shelf_y = sheet_top + (KERF_MM if sheet_top > 0 else 0)
        if shelf_y + width <= uw and length <= ul:
            sheet.placements.append(
                Placement(inst.part_ref, inst.quantity_index, 0, shelf_y, length, width, rotated)
            )
            shelves.append({"y": shelf_y, "used_x": length, "height": width})
            sheet_top = shelf_y + width
            continue

        # new sheet
        if sheet.placements:
            sheets.append(sheet)
        sheet, shelves = new_sheet()
        sheet_top = 0
        sheet.placements.append(
            Placement(inst.part_ref, inst.quantity_index, 0, 0, length, width, rotated)
        )
        shelves.append({"y": 0, "used_x": length, "height": width})
        sheet_top = width

    if sheet.placements:
        sheets.append(sheet)
    return sheets


# --- algorithm 2: recursive guillotine free-rectangle ----------------------


@dataclass
class _FreeRect:
    x: int
    y: int
    length: int  # extent along x
    width: int  # extent along y


def _pack_guillotine_split(
    instances: list[_Instance], spec: SheetSpec, deadline: float
) -> list[Sheet]:
    """Recursive free-rectangle guillotine packing.

    Each sheet starts as one free rectangle. Placing a part splits the hosting
    rectangle into two children with a single edge-to-edge (guillotine) cut,
    accounting for kerf on each split. Best-area-fit choice of free rectangle.
    """
    ul, uw = spec.usable_length_mm, spec.usable_width_mm
    order = sorted(
        instances,
        key=lambda inst: (inst.length_mm * inst.width_mm, max(inst.length_mm, inst.width_mm)),
        reverse=True,
    )

    sheets: list[Sheet] = []
    free_by_sheet: list[list[_FreeRect]] = []

    def open_sheet() -> None:
        sheets.append(Sheet(material_id=spec.material_id, sheet_index=len(sheets) + 1))
        free_by_sheet.append([_FreeRect(0, 0, ul, uw)])

    for inst in order:
        _deadline_guard(deadline)
        # (sheet_idx, free_idx, rect, length, width, rotated) with smallest leftover
        best: tuple[int, int, _FreeRect, int, int, bool] | None = None
        best_leftover = 0
        for s_idx, frees in enumerate(free_by_sheet):
            for f_idx, rect in enumerate(frees):
                for length, width, rotated in _oriented(inst, spec):
                    if length <= rect.length and width <= rect.width:
                        leftover = rect.length * rect.width - length * width
                        if best is None or leftover < best_leftover:
                            best = (s_idx, f_idx, rect, length, width, rotated)
                            best_leftover = leftover
        if best is None:
            open_sheet()
            s_idx = len(sheets) - 1
            rect = free_by_sheet[s_idx][0]
            chosen: tuple[int, int, int, bool] | None = None
            for length, width, rotated in _oriented(inst, spec):
                if length <= rect.length and width <= rect.width:
                    chosen = (0, length, width, rotated)
                    break
            assert chosen is not None  # validated to fit upstream
            f_idx, length, width, rotated = chosen
            best = (s_idx, f_idx, rect, length, width, rotated)

        s_idx, f_idx, rect, length, width, rotated = best
        sheets[s_idx].placements.append(
            Placement(inst.part_ref, inst.quantity_index, rect.x, rect.y, length, width, rotated)
        )
        # guillotine split of the hosting rectangle (split along the longer leftover)
        frees = free_by_sheet[s_idx]
        frees.pop(f_idx)
        right_w = rect.length - length - KERF_MM
        top_h = rect.width - width - KERF_MM
        # prefer the split that leaves the larger usable child (shorter-axis split)
        if rect.length * top_h >= rect.width * right_w:
            # horizontal cut first: top spans full width, right spans part height
            if top_h > 0:
                frees.append(_FreeRect(rect.x, rect.y + width + KERF_MM, rect.length, top_h))
            if right_w > 0:
                frees.append(_FreeRect(rect.x + length + KERF_MM, rect.y, right_w, width))
        else:
            if right_w > 0:
                frees.append(_FreeRect(rect.x + length + KERF_MM, rect.y, right_w, rect.width))
            if top_h > 0:
                frees.append(_FreeRect(rect.x, rect.y + width + KERF_MM, length, top_h))

    return sheets


# --- metrics ----------------------------------------------------------------


def _edge_lengths_by_thickness(parts: list[PartInput]) -> dict[str, int]:
    """Sum banded-side lengths by thickness across all parts.

    Top/bottom sides use the part length; left/right use the part width. Each
    multiplied by quantity. Keys are the thickness as a string (``"0.4"`` /
    ``"2.0"``); values are total mm.
    """
    totals: dict[str, int] = {}
    for part in parts:
        sides = (
            (part.edge_top_mm, part.length_mm),
            (part.edge_bottom_mm, part.length_mm),
            (part.edge_left_mm, part.width_mm),
            (part.edge_right_mm, part.width_mm),
        )
        for thickness, side_len in sides:
            if thickness:
                key = _thickness_key(thickness)
                totals[key] = totals.get(key, 0) + side_len * part.quantity
    return totals


def _thickness_key(thickness: float) -> str:
    """Stable thickness key: ``0.4`` / ``2.0`` (drop trailing zeros sensibly)."""
    if thickness == int(thickness):
        return f"{thickness:.1f}"
    return f"{thickness:g}"


def _sheet_cut_length(sheet: Sheet, spec: SheetSpec) -> int:
    """Approximate guillotine cut length on a sheet: the perimeter of each
    placement contributes its trimming cuts. We sum the two cut edges introduced
    per part (its length + width), a stable proxy used for pricing comparison."""
    return sum(p.length_mm + p.width_mm for p in sheet.placements)


def _finalise(
    algorithm_name: str,
    algorithm_version: str,
    parts: list[PartInput],
    sheets_by_material: dict[str, list[Sheet]],
    specs: dict[str, SheetSpec],
) -> AlgorithmResult:
    all_sheets: list[Sheet] = []
    sheets_used: dict[str, int] = {}
    total_used_area = 0
    total_sheet_area = 0
    total_cut = 0
    parts_placed = 0

    for material_id, sheets in sheets_by_material.items():
        spec = specs[material_id]
        sheet_area = spec.usable_length_mm * spec.usable_width_mm
        sheets_used[material_id] = len(sheets)
        for sheet in sheets:
            used = sum(p.length_mm * p.width_mm for p in sheet.placements)
            sheet.waste_area_mm2 = max(sheet_area - used, 0)
            total_used_area += used
            total_sheet_area += sheet_area
            total_cut += _sheet_cut_length(sheet, spec)
            parts_placed += len(sheet.placements)
        all_sheets.extend(sheets)

    waste = 0.0
    if total_sheet_area > 0:
        waste = round(1.0 - total_used_area / total_sheet_area, 4)
        waste = min(max(waste, 0.0), 1.0)

    edge_by_thickness = _edge_lengths_by_thickness(parts)
    total_edge = sum(edge_by_thickness.values())

    return AlgorithmResult(
        algorithm_name=algorithm_name,
        algorithm_version=algorithm_version,
        kerf_mm=KERF_MM,
        edge_trim_mm=EDGE_TRIM_MM,
        sheets=all_sheets,
        sheets_used_by_material=sheets_used,
        waste_percentage=waste,
        total_cut_length_mm=total_cut,
        total_edge_length_mm=total_edge,
        edge_length_by_thickness=edge_by_thickness,
        parts_placed=parts_placed,
    )


# --- validation -------------------------------------------------------------


def validate_parts(parts: list[PartInput], specs: dict[str, SheetSpec]) -> None:
    """Run the structural checks the spec mandates, raising the SPEC error codes.

    (material existence/active is validated in the persistence service; here we
    have the resolved specs already.)
    """
    total_qty = sum(p.quantity for p in parts)
    if total_qty > MAX_PARTS:
        raise _err(
            "too_many_parts",
            f"At most {MAX_PARTS} parts per optimisation; this run has {total_qty}.",
        )
    for part in parts:
        spec = specs[part.material_id]
        if part.length_mm < PART_MIN_MM or part.width_mm < PART_MIN_MM:
            raise _err(
                "part_too_small",
                f"Part {part.part_ref} is below the {PART_MIN_MM}x{PART_MIN_MM} mm minimum.",
            )
        inst = _Instance(part.part_ref, 1, part.length_mm, part.width_mm)
        long_side = max(part.length_mm, part.width_mm)
        short_side = min(part.length_mm, part.width_mm)
        ul, uw = spec.usable_length_mm, spec.usable_width_mm
        # Unconstrained (rotation allowed) feasibility — the best either side can do.
        fits_unconstrained = (long_side <= ul and short_side <= uw) or (
            short_side <= ul and long_side <= uw
        )
        if not fits_unconstrained:
            raise _err(
                "part_too_large",
                f"Part {part.part_ref} exceeds the usable area ({ul}x{uw} mm) of its material.",
            )
        # Fits unconstrained but not in the forced grain orientation -> impossible.
        if not _fits_some_orientation(inst, spec):
            raise _err(
                "impossible_grain",
                f"Part {part.part_ref} cannot fit on a grained sheet without rotation.",
            )


# --- orchestration ----------------------------------------------------------

_ALGORITHMS: list[tuple[str, str, object]] = [
    ("ffd-shelf", "1.0", _pack_ffd_shelf),
    ("guillotine-split", "1.0", _pack_guillotine_split),
]


def _run_one(
    algorithm_name: str,
    algorithm_version: str,
    packer: object,
    parts: list[PartInput],
    specs: dict[str, SheetSpec],
    deadline: float,
) -> AlgorithmResult:
    by_material: dict[str, list[_Instance]] = {}
    for part in parts:
        by_material.setdefault(part.material_id, []).extend(_expand(part))

    sheets_by_material: dict[str, list[Sheet]] = {}
    for material_id, instances in by_material.items():
        spec = specs[material_id]
        sheets = packer(instances, spec, deadline)  # type: ignore[operator]
        if len(sheets) > MAX_SHEETS_PER_MATERIAL:
            raise _err(
                "too_many_sheets_needed",
                f"Material {material_id} needs {len(sheets)} sheets "
                f"(> {MAX_SHEETS_PER_MATERIAL}); split into separate orders.",
            )
        sheets_by_material[material_id] = sheets

    return _finalise(algorithm_name, algorithm_version, parts, sheets_by_material, specs)


def optimise(
    parts: list[PartInput],
    specs: dict[str, SheetSpec],
    *,
    budget_seconds: float = RUN_BUDGET_SECONDS,
) -> list[AlgorithmResult]:
    """Run every algorithm against the same input; return one result each.

    Pure CPU work — call via ``anyio.to_thread.run_sync`` from async code.
    Enforces the structural limits and a wall-clock budget across the whole run.
    """
    validate_parts(parts, specs)
    deadline = time.monotonic() + budget_seconds
    results: list[AlgorithmResult] = []
    for name, version, packer in _ALGORITHMS:
        results.append(_run_one(name, version, packer, parts, specs, deadline))
    return results


def winner(results: list[AlgorithmResult]) -> AlgorithmResult:
    """Lowest weighted waste % wins; ties broken by fewest total sheets."""
    return min(
        results,
        key=lambda r: (r.waste_percentage, sum(r.sheets_used_by_material.values())),
    )
