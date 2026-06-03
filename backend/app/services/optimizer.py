"""Pure guillotine cutting optimizers and metric calculation."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from app.models.enums import MaterialSource

KERF_MM = 4
EDGE_TRIM_MM = 10
EDGE_OVERHANG_MM = 30
MAX_PARTS_PER_RUN = 100
MAX_PANELS_PER_MATERIAL = 20
OPTIMIZATION_TIMEOUT_SECONDS = 5.0
ALGORITHM_VERSION = "1.0"

EDGE_SIDES = ("top", "bottom", "left", "right")


@dataclass(frozen=True)
class OptimizerError(Exception):
    code: str
    message: str
    part_ref: str | None = None
    row_index: int | None = None
    material_id: uuid.UUID | None = None


@dataclass(frozen=True)
class PanelSpec:
    material_id: uuid.UUID
    length_mm: int
    width_mm: int
    grain_direction: bool

    @property
    def usable_length_mm(self) -> int:
        return self.length_mm - 2 * EDGE_TRIM_MM

    @property
    def usable_width_mm(self) -> int:
        return self.width_mm - 2 * EDGE_TRIM_MM

    @property
    def usable_area_mm2(self) -> int:
        return self.usable_length_mm * self.usable_width_mm


@dataclass(frozen=True)
class EdgeBandInput:
    material_id: uuid.UUID
    source: MaterialSource


@dataclass(frozen=True)
class PartInput:
    part_ref: str
    row_index: int
    material_id: uuid.UUID
    material_source: MaterialSource
    length_mm: int
    width_mm: int
    quantity: int
    edge_top: EdgeBandInput | None = None
    edge_bottom: EdgeBandInput | None = None
    edge_left: EdgeBandInput | None = None
    edge_right: EdgeBandInput | None = None

    @property
    def area_mm2(self) -> int:
        return self.length_mm * self.width_mm

    def edge_for_side(self, side: str) -> EdgeBandInput | None:
        if side == "top":
            return self.edge_top
        if side == "bottom":
            return self.edge_bottom
        if side == "left":
            return self.edge_left
        if side == "right":
            return self.edge_right
        raise ValueError(f"Unknown edge side: {side}")


@dataclass(frozen=True)
class PlacementResult:
    material_id: uuid.UUID
    part_ref: str
    part_quantity_index: int
    x_mm: int
    y_mm: int
    length_mm: int
    width_mm: int
    rotated: bool


@dataclass(frozen=True)
class PanelResult:
    material_id: uuid.UUID
    panel_index: int
    waste_area_mm2: int
    placements: list[PlacementResult]


@dataclass(frozen=True)
class OptimizationResult:
    algorithm_name: str
    algorithm_version: str
    kerf_mm: int
    edge_trim_mm: int
    panels: list[PanelResult]
    panels_used_by_material: dict[str, int]
    waste_percentage: Decimal
    total_cut_length_mm: int
    total_edge_length_mm: int
    edge_length_by_material: dict[str, int]
    edge_length_shop_by_material: dict[str, int]
    edge_length_own_by_material: dict[str, int]
    edge_consumed_shop_by_material: dict[str, int]
    edge_consumed_own_by_material: dict[str, int]
    edge_banded_sides_by_material: dict[str, dict[str, int]]


@dataclass(frozen=True)
class _PartInstance:
    part: PartInput
    quantity_index: int


@dataclass(frozen=True)
class _FreeRect:
    x_mm: int
    y_mm: int
    length_mm: int
    width_mm: int

    @property
    def area_mm2(self) -> int:
        return self.length_mm * self.width_mm


@dataclass
class _PanelState:
    material: PanelSpec
    panel_index: int
    free_rects: list[_FreeRect] = field(default_factory=list)
    placements: list[PlacementResult] = field(default_factory=list)
    used_area_mm2: int = 0

    @classmethod
    def create(cls, material: PanelSpec, panel_index: int) -> _PanelState:
        return cls(
            material=material,
            panel_index=panel_index,
            free_rects=[
                _FreeRect(
                    x_mm=EDGE_TRIM_MM,
                    y_mm=EDGE_TRIM_MM,
                    length_mm=material.usable_length_mm,
                    width_mm=material.usable_width_mm,
                )
            ],
        )

    @property
    def waste_area_mm2(self) -> int:
        return self.material.usable_area_mm2 - self.used_area_mm2


@dataclass(frozen=True)
class _PlacementChoice:
    panel_index: int
    rect_index: int
    length_mm: int
    width_mm: int
    rotated: bool


def run_all_algorithms(
    parts: list[PartInput],
    materials: dict[uuid.UUID, PanelSpec],
    *,
    timeout_seconds: float = OPTIMIZATION_TIMEOUT_SECONDS,
) -> list[OptimizationResult]:
    """Run every available deterministic algorithm against the same input."""

    if timeout_seconds <= 0:
        raise OptimizerError("optimization_timeout", "Optimization timed out")
    if sum(part.quantity for part in parts) > MAX_PARTS_PER_RUN:
        raise OptimizerError("too_many_parts", "Too many parts for one optimization")
    if not parts:
        raise OptimizerError("empty_parts", "At least one part is required")

    deadline = time.monotonic() + timeout_seconds
    return [
        _run_algorithm("ffd-guillotine", parts, materials, deadline=deadline),
        _run_algorithm("bfd-guillotine", parts, materials, deadline=deadline),
    ]


def _run_algorithm(
    algorithm_name: str,
    parts: list[PartInput],
    materials: dict[uuid.UUID, PanelSpec],
    *,
    deadline: float,
) -> OptimizationResult:
    grouped: dict[uuid.UUID, list[_PartInstance]] = {}
    for part in parts:
        if part.quantity < 1:
            raise OptimizerError(
                "invalid_quantity",
                "Part quantity must be at least 1",
                part_ref=part.part_ref,
                row_index=part.row_index,
                material_id=part.material_id,
            )
        if part.material_id not in materials:
            raise OptimizerError(
                "material_not_found",
                "Panel material not found",
                part_ref=part.part_ref,
                row_index=part.row_index,
                material_id=part.material_id,
            )
        _ensure_part_can_fit(part, materials[part.material_id])
        for quantity_index in range(1, part.quantity + 1):
            grouped.setdefault(part.material_id, []).append(
                _PartInstance(part=part, quantity_index=quantity_index)
            )

    panels: list[PanelResult] = []
    for material_id in sorted(grouped, key=str):
        material = materials[material_id]
        instances = sorted(
            grouped[material_id],
            key=lambda item: (
                -item.part.area_mm2,
                item.part.part_ref,
                item.quantity_index,
            ),
        )
        panels.extend(_place_material(algorithm_name, material, instances, deadline=deadline))

    return _build_result(algorithm_name, parts, panels, materials)


def _ensure_part_can_fit(part: PartInput, material: PanelSpec) -> None:
    if part.length_mm < 50 or part.width_mm < 50:
        raise OptimizerError(
            "part_too_small",
            "Part is smaller than the minimum allowed size",
            part_ref=part.part_ref,
            row_index=part.row_index,
            material_id=part.material_id,
        )
    fits_normal = (
        part.length_mm <= material.usable_length_mm and part.width_mm <= material.usable_width_mm
    )
    fits_rotated = (
        part.width_mm <= material.usable_length_mm and part.length_mm <= material.usable_width_mm
    )
    if material.grain_direction and not fits_normal:
        raise OptimizerError(
            "impossible_grain",
            "Part cannot fit a grained panel without rotation",
            part_ref=part.part_ref,
            row_index=part.row_index,
            material_id=part.material_id,
        )
    if not material.grain_direction and not (fits_normal or fits_rotated):
        raise OptimizerError(
            "part_too_large",
            "Part is larger than the usable panel area",
            part_ref=part.part_ref,
            row_index=part.row_index,
            material_id=part.material_id,
        )


def _place_material(
    algorithm_name: str,
    material: PanelSpec,
    instances: list[_PartInstance],
    *,
    deadline: float,
) -> list[PanelResult]:
    panel_states: list[_PanelState] = []
    for instance in instances:
        if time.monotonic() > deadline:
            raise OptimizerError("optimization_timeout", "Optimization timed out")
        choice = (
            _choose_first_fit(panel_states, instance)
            if algorithm_name == "ffd-guillotine"
            else _choose_best_fit(panel_states, instance)
        )
        if choice is None:
            if len(panel_states) >= MAX_PANELS_PER_MATERIAL:
                raise OptimizerError(
                    "too_many_panels_needed",
                    "Too many panels needed for one material",
                    part_ref=instance.part.part_ref,
                    row_index=instance.part.row_index,
                    material_id=material.material_id,
                )
            panel_states.append(_PanelState.create(material, len(panel_states) + 1))
            choice = (
                _choose_first_fit(panel_states[-1:], instance)
                if algorithm_name == "ffd-guillotine"
                else _choose_best_fit(panel_states[-1:], instance)
            )
            if choice is not None:
                choice = _PlacementChoice(
                    panel_index=len(panel_states) - 1,
                    rect_index=choice.rect_index,
                    length_mm=choice.length_mm,
                    width_mm=choice.width_mm,
                    rotated=choice.rotated,
                )
        if choice is None:
            raise OptimizerError(
                "part_too_large",
                "Part is larger than the usable panel area",
                part_ref=instance.part.part_ref,
                row_index=instance.part.row_index,
                material_id=material.material_id,
            )
        _apply_choice(panel_states[choice.panel_index], choice, instance)

    return [
        PanelResult(
            material_id=state.material.material_id,
            panel_index=state.panel_index,
            waste_area_mm2=state.waste_area_mm2,
            placements=state.placements,
        )
        for state in panel_states
    ]


def _choose_first_fit(
    panels: list[_PanelState],
    instance: _PartInstance,
) -> _PlacementChoice | None:
    for panel_index, panel in enumerate(panels):
        for rect_index, rect in enumerate(panel.free_rects):
            for length_mm, width_mm, rotated in _orientations(instance.part, panel.material):
                if _fits(rect, length_mm, width_mm):
                    return _PlacementChoice(
                        panel_index=panel_index,
                        rect_index=rect_index,
                        length_mm=length_mm,
                        width_mm=width_mm,
                        rotated=rotated,
                    )
    return None


def _choose_best_fit(
    panels: list[_PanelState],
    instance: _PartInstance,
) -> _PlacementChoice | None:
    best: tuple[int, int, int, int, _PlacementChoice] | None = None
    for panel_index, panel in enumerate(panels):
        for rect_index, rect in enumerate(panel.free_rects):
            for length_mm, width_mm, rotated in _orientations(instance.part, panel.material):
                if not _fits(rect, length_mm, width_mm):
                    continue
                leftover_area = rect.area_mm2 - length_mm * width_mm
                rotated_rank = 1 if rotated else 0
                choice = _PlacementChoice(
                    panel_index=panel_index,
                    rect_index=rect_index,
                    length_mm=length_mm,
                    width_mm=width_mm,
                    rotated=rotated,
                )
                rank = (leftover_area, panel_index, rect_index, rotated_rank, choice)
                if best is None or rank[:4] < best[:4]:
                    best = rank
    return best[4] if best is not None else None


def _orientations(part: PartInput, material: PanelSpec) -> tuple[tuple[int, int, bool], ...]:
    normal = (part.length_mm, part.width_mm, False)
    if material.grain_direction or part.length_mm == part.width_mm:
        return (normal,)
    return (normal, (part.width_mm, part.length_mm, True))


def _fits(rect: _FreeRect, length_mm: int, width_mm: int) -> bool:
    return length_mm <= rect.length_mm and width_mm <= rect.width_mm


def _apply_choice(
    panel: _PanelState,
    choice: _PlacementChoice,
    instance: _PartInstance,
) -> None:
    rect = panel.free_rects.pop(choice.rect_index)
    panel.placements.append(
        PlacementResult(
            material_id=panel.material.material_id,
            part_ref=instance.part.part_ref,
            part_quantity_index=instance.quantity_index,
            x_mm=rect.x_mm,
            y_mm=rect.y_mm,
            length_mm=choice.length_mm,
            width_mm=choice.width_mm,
            rotated=choice.rotated,
        )
    )
    panel.used_area_mm2 += choice.length_mm * choice.width_mm

    right_length = rect.length_mm - choice.length_mm - KERF_MM
    if right_length > 0:
        panel.free_rects.append(
            _FreeRect(
                x_mm=rect.x_mm + choice.length_mm + KERF_MM,
                y_mm=rect.y_mm,
                length_mm=right_length,
                width_mm=choice.width_mm,
            )
        )

    top_width = rect.width_mm - choice.width_mm - KERF_MM
    if top_width > 0:
        panel.free_rects.append(
            _FreeRect(
                x_mm=rect.x_mm,
                y_mm=rect.y_mm + choice.width_mm + KERF_MM,
                length_mm=rect.length_mm,
                width_mm=top_width,
            )
        )
    panel.free_rects.sort(key=lambda item: (item.y_mm, item.x_mm, item.width_mm, item.length_mm))


def _build_result(
    algorithm_name: str,
    parts: list[PartInput],
    panels: list[PanelResult],
    materials: dict[uuid.UUID, PanelSpec],
) -> OptimizationResult:
    panels_used: dict[str, int] = {}
    total_waste = 0
    total_usable_area = 0
    for panel in panels:
        material = materials[panel.material_id]
        material_key = str(panel.material_id)
        panels_used[material_key] = panels_used.get(material_key, 0) + 1
        total_waste += panel.waste_area_mm2
        total_usable_area += material.usable_area_mm2

    edge_metrics = _edge_metrics(parts)
    waste_percentage = (
        Decimal(total_waste) / Decimal(total_usable_area) if total_usable_area else Decimal("0")
    )
    return OptimizationResult(
        algorithm_name=algorithm_name,
        algorithm_version=ALGORITHM_VERSION,
        kerf_mm=KERF_MM,
        edge_trim_mm=EDGE_TRIM_MM,
        panels=panels,
        panels_used_by_material=panels_used,
        waste_percentage=waste_percentage,
        total_cut_length_mm=_total_cut_length(parts),
        total_edge_length_mm=sum(edge_metrics.edge_length_by_material.values()),
        edge_length_by_material=edge_metrics.edge_length_by_material,
        edge_length_shop_by_material=edge_metrics.edge_length_shop_by_material,
        edge_length_own_by_material=edge_metrics.edge_length_own_by_material,
        edge_consumed_shop_by_material=edge_metrics.edge_consumed_shop_by_material,
        edge_consumed_own_by_material=edge_metrics.edge_consumed_own_by_material,
        edge_banded_sides_by_material=edge_metrics.edge_banded_sides_by_material,
    )


@dataclass(frozen=True)
class _EdgeMetrics:
    edge_length_by_material: dict[str, int]
    edge_length_shop_by_material: dict[str, int]
    edge_length_own_by_material: dict[str, int]
    edge_consumed_shop_by_material: dict[str, int]
    edge_consumed_own_by_material: dict[str, int]
    edge_banded_sides_by_material: dict[str, dict[str, int]]


def _edge_metrics(parts: list[PartInput]) -> _EdgeMetrics:
    geometric: dict[str, int] = {}
    shop_geometric: dict[str, int] = {}
    own_geometric: dict[str, int] = {}
    shop_consumed: dict[str, int] = {}
    own_consumed: dict[str, int] = {}
    side_counts: dict[str, dict[str, int]] = {}

    for part in parts:
        for side in EDGE_SIDES:
            edge = part.edge_for_side(side)
            if edge is None:
                continue
            edge_length = part.length_mm if side in {"top", "bottom"} else part.width_mm
            edge_key = str(edge.material_id)
            length = edge_length * part.quantity
            consumed = (edge_length + EDGE_OVERHANG_MM) * part.quantity
            sides = part.quantity
            _add(geometric, edge_key, length)
            source_key = edge.source.value
            side_counts.setdefault(edge_key, {"shop": 0, "own": 0})
            side_counts[edge_key][source_key] += sides
            if edge.source is MaterialSource.SHOP:
                _add(shop_geometric, edge_key, length)
                _add(shop_consumed, edge_key, consumed)
            else:
                _add(own_geometric, edge_key, length)
                _add(own_consumed, edge_key, consumed)

    return _EdgeMetrics(
        edge_length_by_material=geometric,
        edge_length_shop_by_material=shop_geometric,
        edge_length_own_by_material=own_geometric,
        edge_consumed_shop_by_material=shop_consumed,
        edge_consumed_own_by_material=own_consumed,
        edge_banded_sides_by_material=side_counts,
    )


def _total_cut_length(parts: list[PartInput]) -> int:
    return sum(2 * (part.length_mm + part.width_mm) * part.quantity for part in parts)


def _add(target: dict[str, int], key: str, value: int) -> None:
    target[key] = target.get(key, 0) + value
