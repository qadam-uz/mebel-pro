"""Client-supplied material: what the workshop charges for and what it doesn't.

Ownership is counted per material in sheets, not flagged per part, because a
part cannot say which physical sheet carried it — parts of one material share
one layout that does not exist until the optimiser has run. These tests pin the
split that follows from that: sheets come off the top of the demand, the tape
material goes free while the gluing does not, and a claim larger than the layout
is a claim, not a cap.
"""

import uuid
from types import SimpleNamespace

from app.modules.cutting.service import clamp_own_claim
from app.modules.sales.service import (
    _edge_banded_millimetres,
    _own_panels_used,
    _panel_stock_demands,
)

PANEL_A = uuid.uuid4()
PANEL_B = uuid.uuid4()
EDGE_A = uuid.uuid4()
EDGE_B = uuid.uuid4()


def _part(material_id: uuid.UUID, *, quantity: int = 1) -> dict[str, object]:
    return {
        "material_id": str(material_id),
        "material_source": "shop",
        "length_mm": 600,
        "width_mm": 400,
        "quantity": quantity,
    }


def _result(
    *,
    panels: dict[uuid.UUID, int],
    own: dict[uuid.UUID, int] | None = None,
    edge_shop: dict[uuid.UUID, int] | None = None,
    edge_own: dict[uuid.UUID, int] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        panels_used_by_material={str(k): v for k, v in panels.items()},
        own_panel_counts={str(k): v for k, v in (own or {}).items()},
        parts_snapshot=[_part(material_id) for material_id in panels],
        edge_consumed_shop_by_material={str(k): v for k, v in (edge_shop or {}).items()},
        edge_consumed_own_by_material={str(k): v for k, v in (edge_own or {}).items()},
    )


def test_client_sheets_come_off_the_top_of_the_demand() -> None:
    result = _result(panels={PANEL_A: 5}, own={PANEL_A: 3})

    assert _panel_stock_demands(result) == {PANEL_A: 2}


def test_a_claim_larger_than_the_layout_is_a_claim_not_a_cap() -> None:
    # The client owns seven sheets and this layout needs five; the extra two are
    # not an error and must not be clamped away on save — the next edit may need
    # them. Only what the layout uses is applied.
    result = _result(panels={PANEL_A: 5}, own={PANEL_A: 7})

    assert _own_panels_used(result) == {PANEL_A: 5}
    assert _panel_stock_demands(result) == {PANEL_A: 0}


def test_a_material_kept_at_zero_demand_still_has_to_be_carried() -> None:
    # The key survives so `_price_result`'s carry check still runs: the client
    # picked this material from the branch catalog and the cutting plan names it
    # whoever supplies the sheets.
    result = _result(panels={PANEL_A: 3}, own={PANEL_A: 3})

    assert _panel_stock_demands(result) == {PANEL_A: 0}


def test_ownership_of_one_material_leaves_the_others_alone() -> None:
    result = _result(panels={PANEL_A: 5, PANEL_B: 2}, own={PANEL_A: 3})

    assert _panel_stock_demands(result) == {PANEL_A: 2, PANEL_B: 2}


def test_no_claim_prices_exactly_as_before() -> None:
    result = _result(panels={PANEL_A: 5, PANEL_B: 2})

    assert _own_panels_used(result) == {}
    assert _panel_stock_demands(result) == {PANEL_A: 5, PANEL_B: 2}


def test_banding_labour_counts_the_clients_own_tape_too() -> None:
    # Gluing someone else's tape is still the workshop's work: only the tape
    # material is free, which `edge_consumed_shop_by_material` already scopes.
    result = _result(
        panels={PANEL_A: 1},
        edge_shop={EDGE_B: 8000},
        edge_own={EDGE_A: 13500},
    )

    assert _edge_banded_millimetres(result) == {EDGE_A: 13500, EDGE_B: 8000}


def test_a_tape_supplied_from_both_rolls_sums_its_banded_length() -> None:
    result = _result(
        panels={PANEL_A: 1},
        edge_shop={EDGE_A: 4000},
        edge_own={EDGE_A: 2500},
    )

    assert _edge_banded_millimetres(result) == {EDGE_A: 6500}


def test_the_claim_is_clamped_per_layout_not_stored_clamped() -> None:
    # Same draft, two layouts. The claim of seven is kept whole on the draft and
    # each result applies only what it can use — which is what lets an edit that
    # grows the job start charging the client's spare sheets instead of the
    # workshop's.
    claim = {str(PANEL_A): 7}

    assert clamp_own_claim(claim, {str(PANEL_A): 5}) == {str(PANEL_A): 5}
    assert clamp_own_claim(claim, {str(PANEL_A): 9}) == {str(PANEL_A): 7}


def test_a_claim_for_a_material_this_layout_dropped_disappears() -> None:
    # The client removed every part of PANEL_B; their claim on it must not keep
    # discounting a material the layout no longer uses.
    assert clamp_own_claim({str(PANEL_B): 3}, {str(PANEL_A): 4}) == {}
