"""Cutting optimizer adapter backed by the standalone ``cutting-engine`` package."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from importlib.metadata import version

from cutting_engine import (
    CuttingEngineError,
    CuttingRequest,
    CuttingSettings,
    GrainDirection,
    OptimizationLevel,
    Part,
    Sheet,
    optimize,
)
from cutting_engine import (
    CuttingResult as EngineCuttingResult,
)

from app.models.enums import MaterialSource

KERF_MM = 4
EDGE_TRIM_MM = 10
EDGE_OVERHANG_MM = 30
MAX_PARTS_PER_RUN = 100
MAX_PANELS_PER_MATERIAL = 20
OPTIMIZATION_TIMEOUT_SECONDS = 5.0
ALGORITHM_VERSION = f"cutting-engine-{version('cutting-engine')}"
ALGORITHM_NAME = "cutting-engine-best"

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
    follow_grain: bool = True
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
class OffcutResult:
    x_mm: int
    y_mm: int
    length_mm: int
    width_mm: int
    usable: bool


@dataclass(frozen=True)
class PanelResult:
    material_id: uuid.UUID
    panel_index: int
    waste_area_mm2: int
    offcuts: list[OffcutResult]
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


def run_all_algorithms(
    parts: list[PartInput],
    materials: dict[uuid.UUID, PanelSpec],
    *,
    timeout_seconds: float = OPTIMIZATION_TIMEOUT_SECONDS,
) -> list[OptimizationResult]:
    """Return the single best deterministic result from ``cutting-engine``.

    The service layer still expects a list because older UI/API flows supported
    comparing algorithms. The product now keeps only the best result, so this
    adapter returns a one-item list while preserving the existing persistence
    contract.
    """

    return [_run_best_engine_result(parts, materials, timeout_seconds=timeout_seconds)]


def _run_best_engine_result(
    parts: list[PartInput],
    materials: dict[uuid.UUID, PanelSpec],
    *,
    timeout_seconds: float,
) -> OptimizationResult:
    if timeout_seconds <= 0:
        raise OptimizerError("optimization_timeout", "Optimization timed out")
    if sum(part.quantity for part in parts) > MAX_PARTS_PER_RUN:
        raise OptimizerError("too_many_parts", "Too many parts for one optimization")
    if not parts:
        raise OptimizerError("empty_parts", "At least one part is required")

    _ensure_inputs(parts, materials)

    deadline = time.monotonic() + timeout_seconds
    panels: list[PanelResult] = []
    total_cut_length = 0

    parts_by_material: dict[uuid.UUID, list[PartInput]] = {}
    for part in parts:
        parts_by_material.setdefault(part.material_id, []).append(part)

    for material_id in sorted(parts_by_material, key=str):
        if time.monotonic() > deadline:
            raise OptimizerError("optimization_timeout", "Optimization timed out")

        material = materials[material_id]
        material_parts = parts_by_material[material_id]
        engine_result = _optimize_material(material, material_parts)

        if engine_result.unplaced_parts:
            unplaced = engine_result.unplaced_parts[0]
            original = next((part for part in material_parts if part.part_ref == unplaced.id), None)
            raise OptimizerError(
                "part_too_large",
                "Part is larger than the usable panel area",
                part_ref=unplaced.id,
                row_index=original.row_index if original is not None else None,
                material_id=material_id,
            )

        if len(engine_result.sheets) > MAX_PANELS_PER_MATERIAL:
            first = material_parts[0]
            raise OptimizerError(
                "too_many_panels_needed",
                "Too many panels needed for one material",
                part_ref=first.part_ref,
                row_index=first.row_index,
                material_id=material_id,
            )

        quantity_indexes: dict[str, int] = {}
        for sheet_result in engine_result.sheets:
            placements: list[PlacementResult] = []
            used_area = 0
            for placement in sheet_result.placements:
                quantity_index = quantity_indexes.get(placement.part_id, 0) + 1
                quantity_indexes[placement.part_id] = quantity_index
                used_area += placement.width * placement.height
                placements.append(
                    PlacementResult(
                        material_id=material_id,
                        part_ref=placement.part_id,
                        part_quantity_index=quantity_index,
                        x_mm=placement.x,
                        y_mm=placement.y,
                        length_mm=placement.width,
                        width_mm=placement.height,
                        rotated=placement.rotated,
                    )
                )
            panels.append(
                PanelResult(
                    material_id=material_id,
                    panel_index=sheet_result.index,
                    waste_area_mm2=material.usable_area_mm2 - used_area,
                    offcuts=[
                        OffcutResult(
                            x_mm=offcut.x,
                            y_mm=offcut.y,
                            length_mm=offcut.width,
                            width_mm=offcut.height,
                            usable=offcut.usable,
                        )
                        for offcut in sheet_result.offcuts
                    ],
                    placements=placements,
                )
            )
            total_cut_length += sum(
                abs(cut.x2 - cut.x1) + abs(cut.y2 - cut.y1) for cut in sheet_result.cuts
            )

        if time.monotonic() > deadline:
            raise OptimizerError("optimization_timeout", "Optimization timed out")

    return _build_result(parts, panels, materials, total_cut_length_mm=total_cut_length)


def _optimize_material(material: PanelSpec, parts: list[PartInput]) -> EngineCuttingResult:
    request = CuttingRequest(
        sheet=Sheet(width=material.length_mm, height=material.width_mm),
        parts=tuple(_engine_part(material, part) for part in parts),
        settings=CuttingSettings(
            kerf=KERF_MM,
            trim=EDGE_TRIM_MM,
            optimization_level=OptimizationLevel.NORMAL,
        ),
    )
    try:
        return optimize(request)
    except CuttingEngineError as exc:
        first = parts[0] if parts else None
        raise OptimizerError(
            "engine_error",
            str(exc) or "Cutting engine failed",
            part_ref=first.part_ref if first is not None else None,
            row_index=first.row_index if first is not None else None,
            material_id=material.material_id,
        ) from exc


def _engine_part(material: PanelSpec, part: PartInput) -> Part:
    locked = _rotation_locked(material, part)
    return Part(
        id=part.part_ref,
        width=part.length_mm,
        height=part.width_mm,
        quantity=part.quantity,
        can_rotate=not locked,
        grain=GrainDirection.VERTICAL if locked else GrainDirection.NONE,
    )


def _ensure_inputs(parts: list[PartInput], materials: dict[uuid.UUID, PanelSpec]) -> None:
    seen_part_refs: set[str] = set()
    for part in parts:
        if part.part_ref in seen_part_refs:
            raise OptimizerError(
                "duplicate_part_ref",
                "Part reference must be unique",
                part_ref=part.part_ref,
                row_index=part.row_index,
                material_id=part.material_id,
            )
        seen_part_refs.add(part.part_ref)
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
    locked = _rotation_locked(material, part)
    if locked and not fits_normal:
        raise OptimizerError(
            "impossible_grain",
            "Part cannot fit a grained panel without rotation",
            part_ref=part.part_ref,
            row_index=part.row_index,
            material_id=part.material_id,
        )
    if not locked and not (fits_normal or fits_rotated):
        raise OptimizerError(
            "part_too_large",
            "Part is larger than the usable panel area",
            part_ref=part.part_ref,
            row_index=part.row_index,
            material_id=part.material_id,
        )


def _rotation_locked(material: PanelSpec, part: PartInput) -> bool:
    return material.grain_direction and part.follow_grain


def _build_result(
    parts: list[PartInput],
    panels: list[PanelResult],
    materials: dict[uuid.UUID, PanelSpec],
    *,
    total_cut_length_mm: int,
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
        algorithm_name=ALGORITHM_NAME,
        algorithm_version=ALGORITHM_VERSION,
        kerf_mm=KERF_MM,
        edge_trim_mm=EDGE_TRIM_MM,
        panels=panels,
        panels_used_by_material=panels_used,
        waste_percentage=waste_percentage,
        total_cut_length_mm=total_cut_length_mm,
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


def _add(target: dict[str, int], key: str, value: int) -> None:
    target[key] = target.get(key, 0) + value
