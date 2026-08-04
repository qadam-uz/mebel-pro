import dataclasses
import uuid

import pytest
from app.models.enums import MaterialSource
from app.modules.cutting import optimizer as optimizer_module
from app.modules.cutting.api import (
    DEFAULT_CUT_PARAMS,
    EDGE_OVERHANG_MM,
    OPTIMIZATION_TIMEOUT_SECONDS,
    CutParams,
    EdgeBandInput,
    OptimizerError,
    PanelSpec,
    PartInput,
    PlacementResult,
    run_optimizer,
)
from cutting_engine import CuttingResult as EngineCuttingResult
from cutting_engine import (
    GrainDirection,
    NoValidSolverResultError,
    SolverMetadata,
    SolverProvider,
)


def _panel(*, length: int = 1000, width: int = 800, grain: bool = False) -> PanelSpec:
    return PanelSpec(
        material_id=uuid.uuid4(),
        length_mm=length,
        width_mm=width,
        grain_direction=grain,
    )


def _part(
    *,
    material_id: uuid.UUID,
    part_ref: str = "part-1",
    length: int = 300,
    width: int = 200,
    quantity: int = 1,
    follow_grain: bool = True,
    edge_top: EdgeBandInput | None = None,
    edge_left: EdgeBandInput | None = None,
) -> PartInput:
    return PartInput(
        part_ref=part_ref,
        row_index=1,
        material_id=material_id,
        material_source=MaterialSource.SHOP,
        length_mm=length,
        width_mm=width,
        quantity=quantity,
        follow_grain=follow_grain,
        edge_top=edge_top,
        edge_left=edge_left,
    )


@pytest.mark.parametrize(
    "params",
    [DEFAULT_CUT_PARAMS, CutParams(kerf_mm=3, edge_trim_mm=12)],
    ids=["default-params", "alt-branch-params"],
)
def test_cutting_engine_places_every_instance_without_overlap(params: CutParams) -> None:
    panel = _panel()
    parts = [
        _part(material_id=panel.material_id, part_ref="a", length=320, width=180, quantity=2),
        _part(material_id=panel.material_id, part_ref="b", length=250, width=200),
    ]

    result = run_optimizer(parts, {panel.material_id: panel}, params=params)

    assert result.algorithm_name == "cutting-engine/native"
    assert result.kerf_mm == params.kerf_mm
    assert result.edge_trim_mm == params.edge_trim_mm
    placements = [
        placement for panel_result in result.panels for placement in panel_result.placements
    ]
    assert sorted((p.part_ref, p.part_quantity_index) for p in placements) == [
        ("a", 1),
        ("a", 2),
        ("b", 1),
    ]
    for panel_result in result.panels:
        assert panel_result.offcuts
        assert all(offcut.length_mm > 0 and offcut.width_mm > 0 for offcut in panel_result.offcuts)
        for placement in panel_result.placements:
            assert placement.x_mm >= params.edge_trim_mm
            assert placement.y_mm >= params.edge_trim_mm
            assert placement.x_mm + placement.length_mm <= panel.length_mm - params.edge_trim_mm
            assert placement.y_mm + placement.width_mm <= panel.width_mm - params.edge_trim_mm
        _assert_no_overlap(panel_result.placements)


def test_optimizer_records_exact_per_sheet_cut_count_and_manhattan_length() -> None:
    panel = _panel()

    result = run_optimizer(
        [_part(material_id=panel.material_id)],
        {panel.material_id: panel},
        params=DEFAULT_CUT_PARAMS,
    )

    assert all(row.cut_count is not None and row.cut_count >= 0 for row in result.panels)
    assert all(row.cut_length_mm is not None and row.cut_length_mm >= 0 for row in result.panels)
    assert sum(row.cut_length_mm or 0 for row in result.panels) == result.total_cut_length_mm


def test_rejects_more_than_300_parts_before_optimizing() -> None:
    panel = _panel()
    part = _part(material_id=panel.material_id, quantity=301)

    with pytest.raises(OptimizerError) as exc:
        run_optimizer([part], {panel.material_id: panel}, params=DEFAULT_CUT_PARAMS)

    assert exc.value.code == "too_many_parts"


def test_follow_grain_rejects_rotation_even_on_non_grained_material() -> None:
    panel = _panel(length=300, width=200, grain=False)
    part = _part(material_id=panel.material_id, length=170, width=260)

    with pytest.raises(OptimizerError) as exc:
        run_optimizer([part], {panel.material_id: panel}, params=DEFAULT_CUT_PARAMS)

    assert exc.value.code == "impossible_grain"
    assert exc.value.part_ref == "part-1"


def test_rotation_allowed_when_part_does_not_follow_grain() -> None:
    panel = _panel(length=300, width=200, grain=False)
    part = _part(material_id=panel.material_id, length=170, width=260, follow_grain=False)

    result = run_optimizer([part], {panel.material_id: panel}, params=DEFAULT_CUT_PARAMS)

    placement = result.panels[0].placements[0]
    assert placement.rotated is True
    assert placement.length_mm == 260
    assert placement.width_mm == 170


def test_grained_material_rejects_rotation_locked_impossible_part() -> None:
    panel = _panel(length=300, width=200, grain=True)
    part = _part(material_id=panel.material_id, length=170, width=260)

    with pytest.raises(OptimizerError) as exc:
        run_optimizer([part], {panel.material_id: panel}, params=DEFAULT_CUT_PARAMS)

    assert exc.value.code == "impossible_grain"
    assert exc.value.part_ref == "part-1"


@pytest.mark.parametrize(
    ("material_grain", "follow_grain", "expected_can_rotate", "expected_grain"),
    [
        (True, True, False, GrainDirection.VERTICAL),
        (True, False, True, GrainDirection.NONE),
        (False, True, False, GrainDirection.VERTICAL),
        (False, False, True, GrainDirection.NONE),
    ],
)
def test_engine_part_rotation_lock_follows_part_grain_matrix(
    material_grain: bool,
    follow_grain: bool,
    expected_can_rotate: bool,
    expected_grain: GrainDirection,
) -> None:
    panel = _panel(grain=material_grain)
    part = _part(material_id=panel.material_id, follow_grain=follow_grain)

    engine_part = optimizer_module._engine_part(panel, part)

    assert engine_part.can_rotate is expected_can_rotate
    assert engine_part.grain is expected_grain


def test_grained_material_allows_rotation_when_part_does_not_follow_grain() -> None:
    panel = _panel(length=300, width=200, grain=True)
    part = _part(
        material_id=panel.material_id,
        length=170,
        width=260,
        follow_grain=False,
    )

    result = run_optimizer([part], {panel.material_id: panel}, params=DEFAULT_CUT_PARAMS)

    placement = result.panels[0].placements[0]
    assert placement.rotated is True
    assert placement.length_mm == 260
    assert placement.width_mm == 170


def test_edge_metrics_split_shop_and_own_with_consumed_overhang() -> None:
    panel = _panel()
    shop_edge = uuid.uuid4()
    own_edge = uuid.uuid4()
    part = _part(
        material_id=panel.material_id,
        length=100,
        width=50,
        quantity=2,
        edge_top=EdgeBandInput(material_id=shop_edge, source=MaterialSource.SHOP),
        edge_left=EdgeBandInput(material_id=own_edge, source=MaterialSource.OWN),
    )

    result = run_optimizer([part], {panel.material_id: panel}, params=DEFAULT_CUT_PARAMS)

    assert result.total_edge_length_mm == 300
    assert result.edge_length_by_material == {str(shop_edge): 200, str(own_edge): 100}
    assert result.edge_length_shop_by_material == {str(shop_edge): 200}
    assert result.edge_length_own_by_material == {str(own_edge): 100}
    assert result.edge_consumed_shop_by_material == {str(shop_edge): (100 + EDGE_OVERHANG_MM) * 2}
    assert result.edge_consumed_own_by_material == {str(own_edge): (50 + EDGE_OVERHANG_MM) * 2}
    assert result.edge_banded_sides_by_material == {
        str(shop_edge): {"shop": 2, "own": 0},
        str(own_edge): {"shop": 0, "own": 2},
    }


def test_panel_cap_rejects_more_than_twenty_panels_for_one_material() -> None:
    panel = _panel(length=120, width=120)
    part = _part(material_id=panel.material_id, length=100, width=100, quantity=21)

    with pytest.raises(OptimizerError) as exc:
        run_optimizer([part], {panel.material_id: panel}, params=DEFAULT_CUT_PARAMS)

    assert exc.value.code == "too_many_panels_needed"


def test_timeout_rejected_before_work_starts() -> None:
    panel = _panel()
    part = _part(material_id=panel.material_id)

    with pytest.raises(OptimizerError) as exc:
        run_optimizer(
            [part], {panel.material_id: panel}, params=DEFAULT_CUT_PARAMS, timeout_seconds=0
        )

    assert exc.value.code == "optimization_timeout"


def test_outer_optimization_timeout_is_ten_seconds() -> None:
    """PACKINGSOLVER_PROVIDER_SPEC.md, 'Mebel Pro adapter changes': the outer
    timeout must be no lower than packingsolver_timeout_seconds (4s) + 2s, and
    is set to 10s for this release."""
    assert OPTIMIZATION_TIMEOUT_SECONDS == 10.0


def test_duplicate_part_refs_are_rejected() -> None:
    panel = _panel()
    parts = [
        _part(material_id=panel.material_id, part_ref="same"),
        _part(material_id=panel.material_id, part_ref="same"),
    ]

    with pytest.raises(OptimizerError) as exc:
        run_optimizer(parts, {panel.material_id: panel}, params=DEFAULT_CUT_PARAMS)

    assert exc.value.code == "duplicate_part_ref"


def test_branch_trim_changes_usable_area_and_panel_count() -> None:
    """Two branches with different edge trims must resolve to different usable
    panel area for the identical parts — the whole point of per-branch settings
    (cutting.md)."""
    panel = _panel(length=1000, width=800)
    parts = [_part(material_id=panel.material_id, length=480, width=380, quantity=3)]

    tight = run_optimizer(
        parts, {panel.material_id: panel}, params=CutParams(kerf_mm=4, edge_trim_mm=5)
    )
    generous_trim = run_optimizer(
        parts, {panel.material_id: panel}, params=CutParams(kerf_mm=4, edge_trim_mm=200)
    )

    assert tight.edge_trim_mm == 5
    assert generous_trim.edge_trim_mm == 200
    assert tight.waste_percentage != generous_trim.waste_percentage


def test_algorithm_stamp_native_only() -> None:
    solvers = [
        SolverMetadata(
            engine_version="0.3.2", provider=SolverProvider.NATIVE, provider_version="0.3.2"
        ),
        SolverMetadata(
            engine_version="0.3.2", provider=SolverProvider.NATIVE, provider_version="0.3.2"
        ),
    ]

    name, version = optimizer_module._algorithm_stamp(solvers)

    assert name == "cutting-engine/native"
    assert version == "0.3.2"


def test_algorithm_stamp_packingsolver_only() -> None:
    solvers = [
        SolverMetadata(
            engine_version="0.3.2",
            provider=SolverProvider.PACKINGSOLVER,
            provider_version="6915ff627a70ee0d71f5adca81f0ecbb0d0579e4",
        ),
    ]

    name, version = optimizer_module._algorithm_stamp(solvers)

    assert name == "cutting-engine/packingsolver"
    assert version == "0.3.2+packingsolver.6915ff627a70"


def test_algorithm_stamp_hybrid_when_providers_disagree() -> None:
    solvers = [
        SolverMetadata(
            engine_version="0.3.2", provider=SolverProvider.NATIVE, provider_version="0.3.2"
        ),
        SolverMetadata(
            engine_version="0.3.2",
            provider=SolverProvider.PACKINGSOLVER,
            provider_version="6915ff627a70ee0d71f5adca81f0ecbb0d0579e4",
        ),
    ]

    name, version = optimizer_module._algorithm_stamp(solvers)

    assert name == "cutting-engine/hybrid"
    assert version == "0.3.2+packingsolver.6915ff627a70"


def test_multi_material_mixed_providers_persists_one_hybrid_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PACKINGSOLVER_PROVIDER_SPEC.md, 'Mebel Pro adapter changes' item 9: one
    ``optimize()`` call runs per panel-material group, so a multi-material
    draft can have different winning providers per group. The adapter must
    still persist exactly one aggregate ``OptimizationResult`` for the whole
    draft, stamped ``cutting-engine/hybrid``. This host has no PackingSolver
    executable, so the second material's provider is faked onto the real
    engine result (only the ``solver`` metadata is swapped; the placements
    are the real, validated native output) rather than depending on the
    binary being installed.
    """
    native_panel = _panel(length=1000, width=800)
    packingsolver_panel = _panel(length=1000, width=800)
    parts = [
        _part(material_id=native_panel.material_id, part_ref="native-part"),
        _part(material_id=packingsolver_panel.material_id, part_ref="ps-part"),
    ]
    materials = {
        native_panel.material_id: native_panel,
        packingsolver_panel.material_id: packingsolver_panel,
    }

    real_optimize = optimizer_module.optimize

    def _fake_optimize(request: object) -> EngineCuttingResult:
        result = real_optimize(request)  # type: ignore[arg-type]
        part_ids = {part.id for part in request.parts}  # type: ignore[attr-defined]
        if "ps-part" in part_ids:
            return dataclasses.replace(
                result,
                solver=SolverMetadata(
                    engine_version=result.solver.engine_version,
                    provider=SolverProvider.PACKINGSOLVER,
                    provider_version="6915ff627a70ee0d71f5adca81f0ecbb0d0579e4",
                ),
            )
        return result

    monkeypatch.setattr(optimizer_module, "optimize", _fake_optimize)

    result = run_optimizer(parts, materials, params=DEFAULT_CUT_PARAMS)

    assert result.algorithm_name == "cutting-engine/hybrid"
    assert result.algorithm_version == "0.3.2+packingsolver.6915ff627a70"
    assert set(result.panels_used_by_material) == {
        str(native_panel.material_id),
        str(packingsolver_panel.material_id),
    }


def test_solver_absence_yields_native_result() -> None:
    """This host has no ``packingsolver_rectangleguillotine`` executable on
    PATH, so ``optimize()``'s default ``AUTO`` policy always falls back to the
    native provider — the engine handles this fallback internally, the
    adapter just persists whatever provider metadata comes back."""
    panel = _panel()
    part = _part(material_id=panel.material_id)

    result = run_optimizer([part], {panel.material_id: panel}, params=DEFAULT_CUT_PARAMS)

    assert result.algorithm_name == "cutting-engine/native"
    assert result.algorithm_version == "0.3.2"


def test_both_providers_failing_maps_to_existing_engine_error_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PACKINGSOLVER_PROVIDER_SPEC.md failure table: when native fails and the
    attempted external provider also fails, ``cutting-engine`` raises
    ``NoValidSolverResultError`` (a ``CuttingEngineError`` subclass). The
    adapter must not need a new error path for this — it already maps every
    ``CuttingEngineError`` to the product's existing ``engine_error`` contract."""
    panel = _panel()
    part = _part(material_id=panel.material_id)

    def _raise_no_valid_solver_result(request: object) -> EngineCuttingResult:
        raise NoValidSolverResultError(diagnostics=())

    monkeypatch.setattr(optimizer_module, "optimize", _raise_no_valid_solver_result)

    with pytest.raises(OptimizerError) as exc:
        run_optimizer([part], {panel.material_id: panel}, params=DEFAULT_CUT_PARAMS)

    assert exc.value.code == "engine_error"


def _assert_no_overlap(placements: list[PlacementResult]) -> None:
    for index, first in enumerate(placements):
        for second in placements[index + 1 :]:
            first_right = first.x_mm + first.length_mm
            second_right = second.x_mm + second.length_mm
            first_top = first.y_mm + first.width_mm
            second_top = second.y_mm + second.width_mm
            assert (
                first_right <= second.x_mm
                or second_right <= first.x_mm
                or first_top <= second.y_mm
                or second_top <= first.y_mm
            )
