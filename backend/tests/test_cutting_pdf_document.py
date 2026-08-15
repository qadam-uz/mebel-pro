# ruff: noqa: RUF001 -- the drawn dimension strings use the display format's
# multiplication sign, so the expectations must too.

"""Tests for the detailed cutting PDF document builder.

The `material_snapshots` fixtures here deliberately use the **legacy** key
vocabulary (`kind`/`type`/`name`/`color`/`decor_code`/`panel_length_mm`/…).
`cutting_results.material_snapshots` is frozen history the reshape migration does
not rewrite, so the PDF must keep rendering pre-reshape results byte-identically.
`test_a_new_vocabulary_snapshot_renders_the_same_pdf` covers the other side.
"""

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

import pytest
from app.models.enums import CuttingResultSource, CuttingResultStatus
from app.modules.cutting import pdf_document
from app.modules.cutting.schemas import (
    CuttingOffcutResponse,
    CuttingPanelResponse,
    CuttingPlacementResponse,
    CuttingResultResponse,
)
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as rl_canvas

PANEL_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PANEL_B_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
EDGE_A_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
EDGE_B_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b1")


def _placement(
    part_ref: str,
    x: int,
    y: int,
    *,
    index: int = 1,
    length: int = 400,
    width: int = 200,
) -> CuttingPlacementResponse:
    return CuttingPlacementResponse(
        id=uuid.uuid4(),
        part_ref=part_ref,
        part_quantity_index=index,
        x_mm=x,
        y_mm=y,
        length_mm=length,
        width_mm=width,
        rotated=False,
    )


def _panel(
    panel_id: uuid.UUID,
    *,
    panel_index: int,
    placements: list[CuttingPlacementResponse],
    offcuts: list[CuttingOffcutResponse] | None = None,
    cut_count: int | None = None,
    cut_length_mm: int | None = None,
) -> CuttingPanelResponse:
    return CuttingPanelResponse(
        id=uuid.uuid4(),
        branch_material_id=panel_id,
        panel_index=panel_index,
        waste_area_mm2=0,
        cut_count=cut_count,
        cut_length_mm=cut_length_mm,
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


def test_part_rows_carry_dimensions_and_band_counts_not_identity() -> None:
    """The register row is `[length, width, qty, length_bands, width_bands]` —
    no index, name, registry number or grain arrow (CB redesign: a part is
    identified by size + band pattern alone)."""
    part = _part(
        edge_top={"material_id": str(EDGE_A_ID), "source": "shop"},
        edge_right={"material_id": str(EDGE_B_ID), "source": "shop"},
        follow_grain=False,
    )
    panel = _panel(PANEL_ID, panel_index=1, placements=[_placement("part-a", 0, 0)])
    result = _result(parts=[part], panels=[panel])
    registry = pdf_document._derive_edge_registry(result.parts_snapshot)

    rows = pdf_document._panel_part_rows(result, panel, registry)

    # edge_top only -> 1 length-side band; edge_right only -> 1 width-side band.
    assert rows == [["400", "200", "1", "1", "1"]]


def test_part_rows_merge_identical_size_and_band_pattern_by_summing_quantity() -> None:
    """Two different parts that happen to share size + band pattern are
    indistinguishable on the sheet, so they collapse into one register row."""
    twin_a = _part(part_ref="part-a", edge_top={"material_id": str(EDGE_A_ID), "source": "shop"})
    twin_b = _part(
        part_ref="part-b",
        name="Different name",
        edge_top={"material_id": str(EDGE_A_ID), "source": "shop"},
    )
    odd_one_out = _part(
        part_ref="part-c",
        edge_top={"material_id": str(EDGE_A_ID), "source": "shop"},
        edge_left={"material_id": str(EDGE_B_ID), "source": "shop"},
    )
    panel = _panel(
        PANEL_ID,
        panel_index=1,
        placements=[
            _placement("part-a", 0, 0),
            _placement("part-b", 400, 0),
            _placement("part-c", 800, 0),
        ],
    )
    result = _result(parts=[twin_a, twin_b, odd_one_out], panels=[panel])
    registry = pdf_document._derive_edge_registry(result.parts_snapshot)

    rows = pdf_document._panel_part_rows(result, panel, registry)

    # twin_a/twin_b share (400, 200, 1 length band, 0 width bands) -> merged qty 2;
    # odd_one_out differs in width-band count (1) so it stays its own row.
    assert rows == [["400", "200", "2", "1", "0"], ["400", "200", "1", "1", "1"]]


def test_register_widths_are_three_columns_summing_to_the_total_width() -> None:
    widths = pdf_document._register_widths(120.0)
    assert len(widths) == 3  # Uzunlik, Kenglik, Soni — no more #/Detal/D1/D2/Sh1/Sh2
    assert sum(widths) == pytest.approx(120.0)


def test_register_draws_rules_and_band_ticks_not_per_cell_boxes() -> None:
    """The redesigned register has no `pdf.rect(...)` per cell (those made
    empty cells read as stray boxes) — only a header rule, row hairlines and a
    closing rule, plus N short tick marks under a banded number."""
    pdf_document._register_fonts()
    buf = BytesIO()
    pdf = rl_canvas.Canvas(buf, pagesize=(400, 200))
    # One row: 2 length-side bands (Uzunlik ticks), 1 width-side band (Kenglik tick).
    rows = [["400", "200", "3", "2", "1"]]

    pdf_document._draw_register(pdf, 10, 190, 120, rows)

    tokens = " ".join(pdf._code).split()
    assert "re" not in tokens  # no rectangle operator anywhere -> no cell boxes
    # header rule + closing rule (2) + band ticks (2 length-side + 1 width-side) = 5
    assert tokens.count("l") == 5


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


def _layout_units(result: CuttingResultResponse) -> list[pdf_document.LayoutUnit]:
    registry = pdf_document._derive_edge_registry(result.parts_snapshot)
    return [
        pdf_document.LayoutUnit(
            group, pdf_document._panel_part_rows(result, group.panels[0], registry)
        )
        for group in pdf_document._group_identical_sheets(result)
    ]


def _dense_result(row_count: int) -> CuttingResultResponse:
    # Each part gets its own length so the new identical-row merge (same
    # length/width/band-counts collapse to one row) never kicks in here — this
    # fixture exists specifically to overflow the register's row capacity.
    parts = [
        _part(part_ref=f"part-{index}", name=f"Detail {index}", length_mm=100 + index, width_mm=100)
        for index in range(row_count)
    ]
    placements = [
        _placement(
            f"part-{index}",
            (index % 9) * 100,
            (index // 9) * 100,
            length=100 + index,
            width=100,
        )
        for index in range(row_count)
    ]
    return _result(parts=parts, panels=[_panel(PANEL_ID, panel_index=1, placements=placements)])


def _standard_sheet_result() -> CuttingResultResponse:
    # "narrow"/"thin" are deliberately slim trim strips, but still wide enough
    # for the 7 pt edges-mode dimension fallback to fit both numbers at the
    # two-up portrait scale — see test_standard_2750_by_1830_sheet_... below.
    parts = [
        _part(part_ref="tall", name="Yon panel", length_mm=350, width_mm=1288),
        _part(part_ref="wide", name="Tokcha", length_mm=900, width_mm=350),
        _part(part_ref="square", name="Eshik", length_mm=668, width_mm=600),
        _part(part_ref="narrow", name="Tasma", length_mm=140, width_mm=524),
        _part(part_ref="thin", name="Qirra", length_mm=150, width_mm=468),
    ]
    first = [
        _placement("tall", 0, 0, length=350, width=1288),
        _placement("wide", 350, 0, length=900, width=350),
        _placement("square", 1250, 0, length=668, width=600),
        _placement("narrow", 1918, 0, length=140, width=524),
        _placement("thin", 2058, 0, length=150, width=468),
    ]
    second = [
        _placement("tall", 10, 0, length=350, width=1288),
        _placement("wide", 360, 0, length=900, width=350),
        _placement("square", 1260, 0, length=668, width=600),
        _placement("narrow", 1928, 0, length=140, width=524),
        _placement("thin", 2068, 0, length=150, width=468),
    ]
    result = _result(
        parts=parts,
        panels=[
            _panel(PANEL_ID, panel_index=1, placements=first, cut_count=14, cut_length_mm=12_480),
            _panel(PANEL_ID, panel_index=2, placements=second, cut_count=14, cut_length_mm=12_480),
        ],
    )
    result.material_snapshots[str(PANEL_ID)]["panel_length_mm"] = 2750
    result.material_snapshots[str(PANEL_ID)]["panel_width_mm"] = 1830
    return result


def test_work_page_planner_puts_two_units_on_one_portrait_page() -> None:
    result = _result(
        parts=[_part()],
        panels=[
            _panel(PANEL_ID, panel_index=1, placements=[_placement("part-a", 0, 0)]),
            _panel(PANEL_ID, panel_index=2, placements=[_placement("part-a", 500, 0)]),
        ],
    )

    pages = pdf_document._plan_work_pages(result, _layout_units(result))

    assert [(page.orientation, len(page.units)) for page in pages] == [("portrait", 2)]


def test_work_page_planner_pairs_every_sheet_two_up_leaving_the_odd_one_alone() -> None:
    """Two sheets to a page is unconditional — five sheets are 2 + 2 + 1."""
    panels = [
        _panel(PANEL_ID, panel_index=index, placements=[_placement("part-a", index * 100, 0)])
        for index in range(1, 6)
    ]
    result = _result(parts=[_part()], panels=panels)

    pages = pdf_document._plan_work_pages(result, _layout_units(result))

    assert [(page.orientation, len(page.units)) for page in pages] == [
        ("portrait", 2),
        ("portrait", 2),
        ("portrait", 1),
    ]


def test_standard_2750_by_1830_sheet_uses_two_up_portrait_with_fixed_7pt_fallbacks() -> None:
    result = _standard_sheet_result()

    pages = pdf_document._plan_work_pages(result, _layout_units(result))

    assert [(page.orientation, len(page.units)) for page in pages] == [("portrait", 2)]


def test_a_standard_sheet_map_is_width_bound_and_spends_the_page_it_is_given() -> None:
    """The map is the document — it is what the operator reads at the saw. For a
    standard 2750x1830 sheet the map box is wider-than-tall relative to the
    sheet, so page width is what limits it: the margin and the register column
    beside it are the only two things standing between the map and the paper,
    and both are held at their floor."""
    slot_h = (pdf_document._PAGE_H - 2 * pdf_document._MARGIN - pdf_document._PORTRAIT_SLOT_GAP) / 2
    map_h = slot_h - pdf_document._CARD_HEADER_H
    map_w = pdf_document._CONTENT_W - pdf_document._PORTRAIT_REGISTER_W - 16

    assert map_w / 2750 < map_h / 1830  # width-bound: extra height would not help
    assert map_w / pdf_document._PAGE_W > 0.70  # was 0.64 at a 14 mm margin

    # The register still fits its widest content: a 4-digit mm value over a band
    # tick, and the narrow quantity column under its own bold header.
    pdf_document._register_fonts()
    length_w, _, qty_w = pdf_document._register_widths(pdf_document._PORTRAIT_REGISTER_W)
    assert length_w > max(
        pdfmetrics.stringWidth("2750", pdf_document._FONT_REGULAR, pdf_document._MIN_PRINT_TEXT_PT),
        pdf_document._REGISTER_TICK_W,
    )
    assert qty_w > pdfmetrics.stringWidth(
        "Soni", pdf_document._FONT_BOLD, pdf_document._MIN_PRINT_TEXT_PT
    )


def test_unlabelable_map_still_shares_a_two_up_page() -> None:
    """A sheet whose parts are too small to label no longer earns a page of its
    own — two-up is unconditional, and the register still carries every size."""
    result = _result(
        parts=[_part(length_mm=20, width_mm=20)],
        panels=[
            _panel(
                PANEL_ID,
                panel_index=1,
                placements=[_placement("part-a", 0, 0, length=20, width=20)],
            )
        ],
    )

    pages = pdf_document._plan_work_pages(result, _layout_units(result))

    assert [page.orientation for page in pages] == ["portrait"]


def test_work_page_planner_keeps_an_odd_eligible_unit_in_portrait_top_slot() -> None:
    result = _result(
        parts=[_part()],
        panels=[_panel(PANEL_ID, panel_index=1, placements=[_placement("part-a", 0, 0)])],
    )

    pages = pdf_document._plan_work_pages(result, _layout_units(result))

    assert [(page.orientation, len(page.units)) for page in pages] == [("portrait", 1)]


def test_a_dense_sheet_keeps_its_two_up_slot_and_spills_rows_to_a_continuation() -> None:
    """A long register no longer promotes its sheet to a page of its own: the
    sheet keeps its half-page slot and the overflow rows follow on their own
    page, so nothing is dropped."""
    simple = _panel(PANEL_ID, panel_index=1, placements=[_placement("part-a", 0, 0)])
    dense = _dense_result(90)
    result = _result(parts=[_part(), *dense.parts_snapshot], panels=[simple, *dense.panels])
    units = _layout_units(result)
    dense_row_count = len(units[1].rows)

    pages = pdf_document._plan_work_pages(result, units)

    assert pages[0].orientation == "portrait"
    assert len(pages[0].units) == 2
    continuations = [page for page in pages[1:] if page.orientation == "portrait_continuation"]
    assert continuations
    capacity = pdf_document._portrait_slot_capacity()
    printed = capacity + sum((page.row_end or 0) - page.row_start for page in continuations)
    assert printed == dense_row_count
    assert all(page.orientation.startswith("portrait") for page in pages)


def test_work_card_metrics_line_reads_foydali_qoldiq_and_chiqindi_not_bold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CB layout change: the card metrics line dropped "Jami qoldiq" /
    "Foydasiz qoldiq" (bold) for "Foydali qoldiq" / "Chiqindi" (normal
    weight) — pin both the new wording and that it no longer prints bold."""
    calls: list[tuple[str, bool]] = []

    def spy_draw_text(
        pdf: Any, x: float, y: float, text: str, size: float, *, bold: bool = False, gray: float = 0
    ) -> None:
        calls.append((text, bold))

    monkeypatch.setattr(pdf_document, "_draw_text", spy_draw_text)
    monkeypatch.setattr(pdf_document, "draw_sheet_map", lambda *args, **kwargs: None)

    panel = _panel(
        PANEL_ID,
        panel_index=1,
        placements=[_placement("part-a", 0, 0)],
        offcuts=[
            CuttingOffcutResponse(x_mm=400, y_mm=0, length_mm=600, width_mm=1000, usable=True)
        ],
    )
    result = _result(parts=[_part()], panels=[panel])
    unit = _layout_units(result)[0]

    pdf_document._draw_work_card(
        rl_canvas.Canvas(BytesIO(), pagesize=(600, 400)),
        result,
        pdf_document.PdfContext(),
        [],
        unit,
        (10.0, 10.0, 500.0, 300.0),
    )

    metrics_calls = [
        text_and_bold for text_and_bold in calls if "qoldiq" in text_and_bold[0].lower()
    ]
    assert len(metrics_calls) == 1
    text, bold = metrics_calls[0]
    assert "Foydali qoldiq:" in text
    assert "Chiqindi:" in text
    assert "Jami qoldiq" not in text
    assert "Foydasiz qoldiq" not in text
    assert bold is False
    # D3.1: the utilisation figure lost the `KIM:` prefix in the same line.
    assert "ishlatildi" in text
    assert "KIM" not in text


def test_portrait_slot_capacity_is_the_exact_max_the_drawn_card_fits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_portrait_slot_capacity` must match `_draw_work_card`'s real register
    geometry exactly. Before this fix the planner discounted the map's bottom
    padding twice, undercounting by one row and sending it to a needless
    continuation page even though the card had room for it."""
    captured: dict[str, float] = {}
    original_draw_register = pdf_document._draw_register

    def spy_draw_register(
        pdf: Any, x: float, top: float, width: float, rows: list[list[str]]
    ) -> None:
        captured["top"] = top
        original_draw_register(pdf, x, top, width, rows)

    monkeypatch.setattr(pdf_document, "_draw_register", spy_draw_register)

    result = _dense_result(200)
    unit = _layout_units(result)[0]
    slot_h = (pdf_document._PAGE_H - 2 * pdf_document._MARGIN - pdf_document._PORTRAIT_SLOT_GAP) / 2
    frame = (pdf_document._MARGIN, pdf_document._MARGIN, pdf_document._CONTENT_W, slot_h)
    pdf_document._register_fonts()
    pdf = rl_canvas.Canvas(BytesIO(), pagesize=(pdf_document._PAGE_W, pdf_document._PAGE_H))

    pdf_document._draw_work_card(pdf, result, pdf_document.PdfContext(), [], unit, frame)

    capacity = pdf_document._portrait_slot_capacity()
    available = captured["top"] - frame[1]  # register's real top down to the slot's bottom edge
    fits_capacity_rows = pdf_document._REGISTER_HEADER_H + capacity * pdf_document._REGISTER_ROW_H
    fits_one_more_row = fits_capacity_rows + pdf_document._REGISTER_ROW_H

    assert fits_capacity_rows <= available  # what the planner promises actually fits
    assert fits_one_more_row > available  # capacity is the true max, not an undercount


def test_register_continuation_uses_the_full_page_width_not_a_narrow_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A continuation page has no map beside the register, so it should use
    the full content width instead of the work card's narrow
    `_PORTRAIT_REGISTER_W` — a lone 120pt column would look wrong stranded on
    an otherwise empty A4 page."""
    captured: dict[str, float] = {}
    original_draw_register = pdf_document._draw_register

    def spy_draw_register(
        pdf: Any, x: float, top: float, width: float, rows: list[list[str]]
    ) -> None:
        captured["width"] = width
        original_draw_register(pdf, x, top, width, rows)

    monkeypatch.setattr(pdf_document, "_draw_register", spy_draw_register)

    result = _dense_result(200)
    unit = _layout_units(result)[0]
    page = pdf_document.PdfPagePlan("portrait_continuation", (unit,), 0, 10)
    pdf_document._register_fonts()
    pdf = rl_canvas.Canvas(BytesIO(), pagesize=(pdf_document._PAGE_W, pdf_document._PAGE_H))

    pdf_document._draw_register_continuation(pdf, result, pdf_document.PdfContext(), [], unit, page)

    assert captured["width"] == pdf_document._CONTENT_W


def test_identity_block_prints_the_kerf_and_edge_trim_the_layout_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The layout coordinates only reproduce on the machine under the same two
    cutting parameters, so the summary identity block has to carry them."""
    calls: list[str] = []

    def spy_draw_text(
        pdf: Any, x: float, y: float, text: str, size: float, *, bold: bool = False, gray: float = 0
    ) -> None:
        calls.append(text)

    monkeypatch.setattr(pdf_document, "_draw_text", spy_draw_text)

    result = _result(
        parts=[_part()],
        panels=[_panel(PANEL_ID, panel_index=1, placements=[_placement("part-a", 0, 0)])],
    )

    pdf_document._draw_adaptive_identity(
        rl_canvas.Canvas(BytesIO(), pagesize=(600, 800)),
        result,
        pdf_document.PdfContext(),
        780.0,
    )

    matches = [text for text in calls if "Arra kesigi" in text]
    assert len(matches) == 1
    assert matches[0] == "Arra kesigi: 4 mm · chetki qirqim: 10 mm"


def _identity_draw_calls(
    monkeypatch: pytest.MonkeyPatch, context: pdf_document.PdfContext
) -> tuple[list[tuple[float, str, float]], float]:
    """Draw the identity block with `_draw_text` spied; return its body lines
    (title excluded) and the height the block claimed."""
    drawn: list[tuple[float, str, float]] = []

    def spy_draw_text(
        pdf: Any, x: float, y: float, text: str, size: float, *, bold: bool = False, gray: float = 0
    ) -> None:
        drawn.append((x, text, size))

    pdf_document._register_fonts()
    monkeypatch.setattr(pdf_document, "_draw_text", spy_draw_text)

    result = _result(
        parts=[_part()],
        panels=[_panel(PANEL_ID, panel_index=1, placements=[_placement("part-a", 0, 0)])],
    )
    top = 780.0
    bottom = pdf_document._draw_adaptive_identity(
        rl_canvas.Canvas(BytesIO(), pagesize=A4), result, context, top
    )
    body = [(x, text, size) for x, text, size in drawn if "kesish hujjati" not in text]
    return body, top - bottom


def _assert_within_columns(body: list[tuple[float, str, float]]) -> None:
    right_x = pdf_document._MARGIN + pdf_document._CONTENT_W * pdf_document._IDENTITY_SPLIT
    for x, text, size in body:
        width = pdfmetrics.stringWidth(text, pdf_document._FONT_REGULAR, size)
        limit = right_x if x < right_x else pdf_document._MARGIN + pdf_document._CONTENT_W
        assert x + width <= limit, f"{text!r} overruns its column"


def test_branch_identity_keeps_both_columns_inside_their_own_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real workshop address plus phone overran the left column and printed
    on top of the right-hand stats."""
    body, height = _identity_draw_calls(
        monkeypatch,
        pdf_document.PdfContext(
            workshop_name="Mebel Master",
            branch_name="Chilonzor filiali",
            branch_address="Toshkent, Chilonzor tumani, Bunyodkor ko'chasi 12",
            branch_phone="+998712001212",
        ),
    )

    _assert_within_columns(body)
    # These fit as-is, so the box stays its normal height and neither line wraps.
    lines = [text for _, text, _ in body]
    assert "Filial: Mebel Master · Chilonzor filiali · +998712001212" in lines
    assert "Toshkent, Chilonzor tumani, Bunyodkor ko'chasi 12" in lines
    assert height == pdf_document._IDENTITY_MIN_H


def test_overlong_workshop_name_wraps_down_instead_of_being_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Names longer than the column continue on the next line and the box grows
    to hold them — no ellipsis, nothing lost, nothing over the stats column."""
    body, height = _identity_draw_calls(
        monkeypatch,
        pdf_document.PdfContext(
            workshop_name="Zamonaviy Mebel Konstruksiyalari Ishlab Chiqarish Korxonasi",
            branch_name="Yunusobod tumani markaziy ishlab chiqarish filiali",
            branch_address="Toshkent shahri, Yunusobod tumani, Amir Temur shoh ko'chasi 108A",
            branch_phone="+998712001212",
        ),
    )

    _assert_within_columns(body)
    lines = [text for _, text, _ in body]
    assert not any(text.endswith("…") for text in lines)
    # Every word survives somewhere in the block, in order.
    assert "Korxonasi" in " ".join(lines)
    assert "108A" in " ".join(lines)
    # Wrapping pushed past the four-line minimum, so the box had to grow.
    assert height > pdf_document._IDENTITY_MIN_H


def test_a_single_unbreakable_token_is_split_not_run_over_the_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """There is no space to wrap on, so the split has to happen mid-token."""
    body, _ = _identity_draw_calls(monkeypatch, pdf_document.PdfContext(workshop_name="Z" * 200))

    _assert_within_columns(body)
    assert sum(text.count("Z") for _, text, _ in body) == 200  # every glyph survives


def test_summary_planner_budgets_the_identity_height_it_actually_draws() -> None:
    """The planner subtracted a hardcoded height; once the box can grow, a long
    workshop name would push the first table under the box it was sized for."""
    # A summary long enough to fill the first page, so a taller identity box has
    # to push rows off it: one distinct usable offcut per sheet is one row each.
    panels = [
        _panel(
            PANEL_ID,
            panel_index=index + 1,
            placements=[_placement("part-a", 0, 0)],
            offcuts=[
                CuttingOffcutResponse(
                    x_mm=400, y_mm=0, length_mm=600 + index, width_mm=1000, usable=True
                )
            ],
        )
        for index in range(60)
    ]
    result = _result(parts=[_part()], panels=panels)
    registry = pdf_document._derive_edge_registry(result.parts_snapshot)
    plain = pdf_document.PdfContext()
    tall = pdf_document.PdfContext(
        workshop_name="Zamonaviy Mebel Konstruksiyalari Ishlab Chiqarish Korxonasi",
        branch_name="Yunusobod tumani markaziy ishlab chiqarish qo'shma filiali",
        branch_address="Toshkent shahri, Yunusobod tumani, Amir Temur shoh ko'chasi 108A-uy",
        client_name="Abdurahmon Sultonmurodov Xurshidbek o'g'li",
        client_phone="+998901234567",
        order_number="B-0042",
    )
    pdf_document._register_fonts()

    def first_page_rows(context: pdf_document.PdfContext) -> int:
        page = pdf_document._plan_summary_pages(result, registry, context)[0]
        return sum(end - start for _, start, end in page)

    grew_by = pdf_document._identity_box_h(
        *pdf_document._identity_columns(result, tall)
    ) - pdf_document._identity_box_h(*pdf_document._identity_columns(result, plain))

    assert grew_by >= pdf_document._REGISTER_ROW_H  # the case is only meaningful if it grew
    assert first_page_rows(tall) < first_page_rows(plain)


def test_every_work_page_is_portrait_and_embeds_the_unicode_font() -> None:
    simple = _panel(PANEL_ID, panel_index=1, placements=[_placement("part-a", 0, 0)])
    dense = _dense_result(36)
    result = _result(parts=[_part(), *dense.parts_snapshot], panels=[simple, *dense.panels])

    pdf = pdf_document.render_cutting_pdf(result)
    sizes = [
        (float(width), float(height))
        for width, height in re.findall(rb"/MediaBox \[ 0 0 ([0-9.]+) ([0-9.]+) \]", pdf)
    ]

    assert pdf.startswith(b"%PDF")
    assert b"/FontFile2" in pdf
    assert sizes
    assert all(width < height for width, height in sizes)


def test_every_planned_page_gets_its_own_sheet() -> None:
    """Each planned page must be broken; without it the work pages overprint one another."""
    parts = [
        _part(part_ref=f"part-{index}", name=f"Detail {index}", length_mm=400 + index * 10)
        for index in range(5)
    ]
    panels = [
        _panel(
            PANEL_ID,
            panel_index=index + 1,
            placements=[_placement(f"part-{index}", 0, 0, length=400 + index * 10)],
        )
        for index in range(5)
    ]
    result = _result(parts=parts, panels=panels)

    registry = pdf_document._derive_edge_registry(result.parts_snapshot)
    planned = len(pdf_document._plan_summary_pages(result, registry)) + len(
        pdf_document._plan_work_pages(result, _layout_units(result))
    )
    pdf = pdf_document.render_cutting_pdf(result)

    assert planned > 2  # the case is only meaningful with several work pages
    assert pdf.count(b"/Type /Page\n") == planned


# --------------------------------------------------------------------------- #
# Dual-vocabulary snapshot reads
# --------------------------------------------------------------------------- #

_NEW_PANEL_SNAPSHOT = {
    "id": str(PANEL_ID),
    "dekor_id": str(uuid.uuid4()),
    "manufacturer_id": str(uuid.uuid4()),
    "manufacturer_name": "Egger",
    "tur": "ldsp",
    "kod": "H1334 ST9",
    "nomi": "Sanoma",
    "qalinlik_mm": "18",
    "uzunlik_mm": 1000,
    "eni_mm": 1000,
    "kromka_eni_mm": None,
    "tolali": False,
    "image_file_id": None,
}

_LEGACY_PANEL_SNAPSHOT = {
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
}


def test_material_short_reads_both_snapshot_vocabularies() -> None:
    """Old and new snapshots must name the sheet the same way.

    `cutting_results.material_snapshots` is frozen history the migration does not
    rewrite, so both vocabularies live in the database forever. Reading only the
    new keys would silently print an 8-character id fragment on every re-rendered
    pre-reshape PDF — green tests, wrong paper.
    """
    assert pdf_document._material_short(_NEW_PANEL_SNAPSHOT, str(PANEL_ID)) == "H1334 ST9"
    assert pdf_document._material_short(_LEGACY_PANEL_SNAPSHOT, str(PANEL_ID)) == "H1334 ST9"
    # A snapshot with no identity at all still degrades to the id fragment
    # rather than raising.
    assert pdf_document._material_short({}, str(PANEL_ID)) == str(PANEL_ID)[:8]


def test_sheet_dimensions_read_both_snapshot_vocabularies() -> None:
    """The sheet size drives the drawn map's scale, so a miss is silent and total."""
    for snapshot in (_NEW_PANEL_SNAPSHOT, _LEGACY_PANEL_SNAPSHOT):
        assert pdf_document._panel_length_for_snapshot(snapshot) == 1000
        assert pdf_document._panel_width_for_snapshot(snapshot) == 1000


def test_a_new_vocabulary_snapshot_prints_the_same_summary_row() -> None:
    """The summary table, not just the label helper, is vocabulary-agnostic.

    This is the row that names the sheet and prints its size — the two places a
    missed legacy key degrades silently (an id fragment, and a 0x0 sheet).
    """
    parts = [_part()]
    panels = [_panel(PANEL_ID, panel_index=1, placements=[_placement("part-1", 0, 0)])]

    legacy = _result(parts=parts, panels=panels)
    modern = _result(parts=parts, panels=panels)
    modern.material_snapshots = {
        **modern.material_snapshots,
        str(PANEL_ID): dict(_NEW_PANEL_SNAPSHOT),
    }

    def summary_row(result: CuttingResultResponse) -> tuple[str, str]:
        stats = pdf_document._material_stats(result)
        row = next(entry for entry in stats if entry.material_id == str(PANEL_ID))
        snapshot = pdf_document._material_snapshot(result, row.material_id)
        return (
            pdf_document._material_label(snapshot, row.material_id),
            f"{pdf_document._panel_length_for_snapshot(snapshot)}"
            f"×{pdf_document._panel_width_for_snapshot(snapshot)}",
        )

    assert summary_row(modern) == summary_row(legacy)
    assert summary_row(modern)[1] == "1000×1000"


def test_summary_section_headers_survive_their_own_column_widths() -> None:
    """`_clip` truncates by character count, silently and without an error.

    D3.1 renamed the `KIM` column to `Ishlatildi` — three times longer, in a
    column sized for three glyphs. Nothing in the render path raises when a
    header is clipped, and no rendered-PDF assertion reads it, so the only
    guard against `Ishlati…` is this one: every header must fit the width its
    own section hands `_draw_table_row`.
    """
    panel = _panel(PANEL_ID, panel_index=1, placements=[_placement("part-a", 0, 0)])
    result = _result(parts=[_part()], panels=[panel])
    sections = pdf_document._summary_sections(result, [])

    clipped = [
        (section.title, header)
        for section in sections
        for header, width in zip(section.headers, section.widths, strict=True)
        if pdf_document._clip(header, width) != header
    ]

    assert clipped == []
    materials = next(section for section in sections if section.title == "Materiallar")
    assert materials.headers[-1] == "Ishlatildi"
