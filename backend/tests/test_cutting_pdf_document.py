"""Tests for the detailed cutting PDF document builder."""

# ruff: noqa: RUF001 -- expected report labels use Uzbek copy.

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.models.enums import CuttingResultSource, CuttingResultStatus
from app.modules.cutting import pdf_document
from app.modules.cutting.schemas import (
    CuttingOffcutResponse,
    CuttingPanelResponse,
    CuttingPlacementResponse,
    CuttingResultResponse,
)

PANEL_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PANEL_B_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
EDGE_A_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
EDGE_B_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b1")


def _placement(part_ref: str, x: int, y: int, *, index: int = 1) -> CuttingPlacementResponse:
    return CuttingPlacementResponse(
        id=uuid.uuid4(),
        part_ref=part_ref,
        part_quantity_index=index,
        x_mm=x,
        y_mm=y,
        length_mm=400,
        width_mm=200,
        rotated=False,
    )


def _panel(
    panel_id: uuid.UUID,
    *,
    panel_index: int,
    placements: list[CuttingPlacementResponse],
    offcuts: list[CuttingOffcutResponse] | None = None,
) -> CuttingPanelResponse:
    return CuttingPanelResponse(
        id=uuid.uuid4(),
        material_id=panel_id,
        panel_index=panel_index,
        waste_area_mm2=0,
        placements=placements,
        offcuts=offcuts or [],
    )


def _part(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "part_ref": "part-a",
        "name": "Shelf",
        "material_id": str(PANEL_ID),
        "material_source": "shop",
        "follow_grain": True,
        "length_mm": 400,
        "width_mm": 200,
        "quantity": 1,
        "edge_top": None,
        "edge_bottom": None,
        "edge_left": None,
        "edge_right": None,
    }
    row.update(overrides)
    return row


def _result(
    *,
    parts: list[dict[str, Any]],
    panels: list[CuttingPanelResponse],
    edge_shop: dict[str, int] | None = None,
    edge_own: dict[str, int] | None = None,
) -> CuttingResultResponse:
    return CuttingResultResponse(
        id=uuid.uuid4(),
        draft_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        algorithm_name="guillotine",
        algorithm_version="1",
        source=CuttingResultSource.OPTIMIZER,
        status=CuttingResultStatus.CANDIDATE,
        kerf_mm=4,
        edge_trim_mm=10,
        panels_used_by_material={str(PANEL_ID): len(panels)},
        waste_percentage=Decimal("0.1"),
        total_cut_length_mm=0,
        total_edge_length_mm=0,
        edge_length_by_material={},
        parts_snapshot=parts,
        material_snapshots={
            str(PANEL_ID): {
                "id": str(PANEL_ID),
                "kind": "panel",
                "manufacturer_name": "Egger",
                "type": "dsp",
                "name": "H1334 ST9",
                "thickness_mm": "18.0",
                "color": "Sanoma",
                "decor_code": "H1334 ST9",
                "panel_length_mm": 1000,
                "panel_width_mm": 1000,
            },
            str(PANEL_B_ID): {
                "id": str(PANEL_B_ID),
                "kind": "panel",
                "manufacturer_name": "Kronospan",
                "type": "dsp",
                "name": "TD-W18",
                "thickness_mm": "18.0",
                "color": "White",
                "decor_code": "TD-W18",
                "panel_length_mm": 1000,
                "panel_width_mm": 1000,
            },
            str(EDGE_A_ID): {
                "id": str(EDGE_A_ID),
                "kind": "edge",
                "manufacturer_name": "Egger",
                "name": "ABS H1334",
                "thickness_mm": "0.4",
                "color": "Sanoma",
                "decor_code": "H1334 ST9",
                "edge_width_mm": 20,
            },
            str(EDGE_B_ID): {
                "id": str(EDGE_B_ID),
                "kind": "edge",
                "manufacturer_name": "Egger",
                "name": "ABS White",
                "thickness_mm": "2",
                "color": "White",
                "decor_code": "W980",
                "edge_width_mm": 20,
            },
        },
        edge_length_shop_by_material={},
        edge_length_own_by_material={},
        edge_consumed_shop_by_material=edge_shop or {},
        edge_consumed_own_by_material=edge_own or {},
        edge_banded_sides_by_material={},
        order_id=None,
        created_at=datetime.now(UTC),
        confirmed_at=None,
        invalidated_at=None,
        panels=panels,
    )


def test_edge_registry_matches_web_first_use_order() -> None:
    parts = [
        _part(
            edge_top={"material_id": str(EDGE_A_ID), "source": "shop"},
            edge_bottom={"material_id": str(EDGE_A_ID), "source": "shop"},
        ),
        _part(
            part_ref="part-b",
            edge_left={"material_id": str(EDGE_A_ID), "source": "own"},
            edge_right={"material_id": str(EDGE_B_ID), "source": "shop"},
        ),
    ]

    entries = pdf_document._derive_edge_registry(parts)

    assert [(entry.material_id, entry.source, entry.number) for entry in entries] == [
        (str(EDGE_A_ID), "shop", 1),
        (str(EDGE_A_ID), "own", 2),
        (str(EDGE_B_ID), "shop", 3),
    ]
    assert pdf_document._registry_number(1) == "①"


def test_identical_consecutive_sheets_group_and_offcut_breaks_group() -> None:
    first = _panel(
        PANEL_ID,
        panel_index=1,
        placements=[_placement("part-a", 0, 0, index=1)],
        offcuts=[
            CuttingOffcutResponse(x_mm=400, y_mm=0, length_mm=600, width_mm=1000, usable=True)
        ],
    )
    second = _panel(
        PANEL_ID,
        panel_index=2,
        placements=[_placement("part-a", 0, 0, index=2)],
        offcuts=[
            CuttingOffcutResponse(x_mm=400, y_mm=0, length_mm=600, width_mm=1000, usable=True)
        ],
    )
    third = _panel(
        PANEL_ID,
        panel_index=3,
        placements=[_placement("part-a", 0, 0, index=3)],
        offcuts=[
            CuttingOffcutResponse(x_mm=500, y_mm=0, length_mm=500, width_mm=1000, usable=True)
        ],
    )
    result = _result(parts=[_part()], panels=[first, second, third])

    groups = pdf_document._group_identical_sheets(result)

    assert [(group.start, group.end, len(group.panels)) for group in groups] == [
        (1, 2, 2),
        (3, 3, 1),
    ]


def test_area_stats_compute_two_kim_inputs() -> None:
    panel = _panel(
        PANEL_ID,
        panel_index=1,
        placements=[_placement("part-a", 0, 0)],
        offcuts=[
            CuttingOffcutResponse(x_mm=400, y_mm=0, length_mm=500, width_mm=1000, usable=True)
        ],
    )
    result = _result(parts=[_part()], panels=[panel])

    stats = pdf_document._material_stats(result)[0]

    assert stats.parts_area == 80_000
    assert stats.usable_area == 500_000
    assert stats.sheet_area == 1_000_000
    assert pdf_document._percent(stats.parts_area, stats.sheet_area) == "8.0%"
    assert pdf_document._percent(stats.parts_area + stats.usable_area, stats.sheet_area) == "58.0%"


def test_part_rows_use_registry_numbers_and_texture_marker() -> None:
    part = _part(
        edge_top={"material_id": str(EDGE_A_ID), "source": "shop"},
        edge_right={"material_id": str(EDGE_B_ID), "source": "shop"},
        follow_grain=False,
    )
    panel = _panel(PANEL_ID, panel_index=1, placements=[_placement("part-a", 0, 0)])
    result = _result(parts=[part], panels=[panel])
    registry = pdf_document._derive_edge_registry(result.parts_snapshot)

    rows = pdf_document._panel_part_rows(result, panel, registry)

    assert rows == [["1", "Shelf", "400×200", "1", "①", "·", "·", "②", "·"]]


def test_render_pdf_smoke_uses_a4_portrait_and_summary_plus_sheet_pages() -> None:
    panel = _panel(PANEL_ID, panel_index=1, placements=[_placement("part-a", 0, 0)])
    result = _result(
        parts=[_part(edge_top={"material_id": str(EDGE_A_ID), "source": "shop"})],
        panels=[panel],
        edge_shop={str(EDGE_A_ID): 2500},
    )

    pdf = pdf_document.render_cutting_pdf(
        result,
        pdf_document.PdfContext(
            order_number="MP-1",
            client_name="Ali",
            branch_name="Yunusobod",
            generated_at=datetime(2026, 7, 12, tzinfo=UTC),
        ),
    )

    assert pdf.startswith(b"%PDF")
    assert pdf.count(b"/Type /Page") >= 2
    assert b"/MediaBox [ 0 0 595.2756 841.8898 ]" in pdf
