"""Decor formats: the platform's product list, and what a branch does with it.

A format is the manufacturer's fact, not the branch's. Only the platform writes
one; a branch picks from what exists. Three rules carry the whole design and
each is tested here through the real HTTP surface:

1. **Shape** — which columns a format carries is decided by its `type`, and the
   service names the offending field so the admin form can put the message next
   to the input (`decor_format_shape_mismatch`). The DB backs most of it with
   `ck_decor_formats_shape`; see tests/test_catalog_material_identity.py.
2. **Immutability** — there is no PATCH. A format's id is what branch rows,
   stock, cutting panels and order history all resolve through, so a wrong one
   is deactivated and a correct one created.
3. **Three levels of "off"** (spec §6) — a decor going inactive, a format going
   inactive and a branch row going inactive mean three different things. The
   middle one is the one nobody guesses: "this product is no longer made" stops
   new attaches and nothing else. The branch keeps its row, its stock, its
   price, and keeps selling the remainder and receiving arrivals, because a
   supplier may still have stock of a discontinued product.
"""

import uuid
from typing import Any

import pytest
from app.models.enums import AuthenticatedPrincipalType
from app.modules.access.api import create_session
from app.modules.access.contracts import Client
from app.modules.catalog.contracts import BranchMaterial
from app.modules.inventory.contracts import StockItem
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_panel_material, seed_platform_user, seed_workshop_with_owner

BOARD = {
    "type": "ldsp",
    "thickness_mm": "18",
    "length_mm": 2800,
    "width_mm": 2070,
    "finished_sides": 2,
}
TAPE = {"type": "kromka", "thickness_mm": "0.4", "tape_width_mm": 22}


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _platform_access(db: AsyncSession) -> str:
    platform = await seed_platform_user(
        db, login=f"platform-{uuid.uuid4().hex[:8]}", password_reset_required=False
    )
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        principal_id=platform.id,
    )
    return tokens.access_token


async def _owner_access(db: AsyncSession, *, login: str = "owner") -> tuple[str, uuid.UUID]:
    _, branch, owner = await seed_workshop_with_owner(db, login=login)
    owner.password_reset_required = False
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token, branch.id


async def _client_access(db: AsyncSession) -> str:
    row = Client(phone=f"+99890{uuid.uuid4().int % 10**7:07d}", name="Browser")
    db.add(row)
    await db.flush()
    tokens = await create_session(
        db, principal_type=AuthenticatedPrincipalType.CLIENT, principal_id=row.id
    )
    return tokens.access_token


async def _decor(
    client: AsyncClient,
    access: str,
    *,
    code: str = "H1145",
    name: str = "Sonoma eman",
) -> str:
    manufacturer = await client.post(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(access),
        json={"name": f"Egger {uuid.uuid4().hex[:6]}", "country": "AT"},
    )
    assert manufacturer.status_code == 201, manufacturer.text
    created = await client.post(
        "/api/v1/platform/catalog/decors",
        headers=_auth(access),
        json={"manufacturer_id": manufacturer.json()["id"], "code": code, "name": name},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def _post_format(
    client: AsyncClient, access: str, decor_id: str, body: dict[str, Any]
) -> Response:
    return await client.post(
        f"/api/v1/platform/catalog/decors/{decor_id}/formats",
        headers=_auth(access),
        json=body,
    )


async def _create_format(
    client: AsyncClient, access: str, decor_id: str, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    response = await _post_format(client, access, decor_id, dict(body or BOARD))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


# --------------------------------------------------------------------------- #
# Format create: the shape rule, per type
# --------------------------------------------------------------------------- #


async def test_a_tape_carries_a_tape_width_and_nothing_else(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A kromka has no sheet size and no finished faces — it is a strip.

    Each refusal names its own field, because the admin form shows the panel
    inputs and the tape input in the same card and has to know which one to
    flag.
    """
    access = await _platform_access(db_session)
    decor_id = await _decor(client, access)

    ok = await _post_format(client, access, decor_id, dict(TAPE))
    without_width = await _post_format(
        client, access, decor_id, {"type": "kromka", "thickness_mm": "0.4"}
    )
    zero_width = await _post_format(client, access, decor_id, {**TAPE, "tape_width_mm": 0})
    with_panel_size = await _post_format(
        client, access, decor_id, {**TAPE, "length_mm": 2800, "width_mm": 2070}
    )
    with_finished_sides = await _post_format(
        client, access, decor_id, {**TAPE, "tape_width_mm": 19, "finished_sides": 2}
    )

    assert ok.status_code == 201, ok.text
    assert ok.json()["tape_width_mm"] == 22
    assert ok.json()["length_mm"] is None
    assert ok.json()["width_mm"] is None
    assert ok.json()["finished_sides"] is None
    for response, field in (
        (without_width, "tape_width_mm"),
        (zero_width, "tape_width_mm"),
        (with_panel_size, "length_mm"),
        (with_finished_sides, "finished_sides"),
    ):
        assert response.status_code == 400, response.text
        assert response.json()["code"] == "decor_format_shape_mismatch"
        assert response.json()["details"]["field"] == field


async def test_a_board_carries_a_sheet_size_and_no_tape_width(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _platform_access(db_session)
    decor_id = await _decor(client, access)

    without_size = await _post_format(
        client, access, decor_id, {"type": "ldsp", "thickness_mm": "18", "finished_sides": 2}
    )
    half_size = await _post_format(client, access, decor_id, {**BOARD, "width_mm": None})
    with_tape_width = await _post_format(client, access, decor_id, {**BOARD, "tape_width_mm": 22})
    zero_thickness = await _post_format(client, access, decor_id, {**BOARD, "thickness_mm": "0"})

    for response, field in (
        (without_size, "length_mm"),
        (half_size, "length_mm"),
        (with_tape_width, "tape_width_mm"),
        (zero_thickness, "thickness_mm"),
    ):
        assert response.status_code == 400, response.text
        assert response.json()["code"] == "decor_format_shape_mismatch"
        assert response.json()["details"]["field"] == field


async def test_finished_sides_is_required_for_boards_and_refused_for_the_rest(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """How many faces are finished is a product fact only where it varies.

    A one-sided sheet is the norm for facade MDF and for the cheap white LDSP
    used on hidden parts: a different product at a different price, not a
    variant. Fanera, yog'och and «boshqa» have no laminate to count, so a value
    there would be noise nobody could act on — and the DB cannot catch a
    *missing* one on a board type (`NULL IN (1,2)` is NULL, which a CHECK
    passes), so this rule is the service's to keep.
    """
    access = await _platform_access(db_session)
    decor_id = await _decor(client, access)

    for board_type in ("ldsp", "dsp", "mdf"):
        one_sided = await _post_format(
            client,
            access,
            decor_id,
            {**BOARD, "type": board_type, "finished_sides": 1},
        )
        missing = await _post_format(
            client,
            access,
            decor_id,
            {
                "type": board_type,
                "thickness_mm": "16",
                "length_mm": 2800,
                "width_mm": 2070,
            },
        )
        out_of_range = await _post_format(
            client,
            access,
            decor_id,
            {**BOARD, "type": board_type, "thickness_mm": "10", "finished_sides": 3},
        )
        assert one_sided.status_code == 201, one_sided.text
        assert one_sided.json()["finished_sides"] == 1
        for response in (missing, out_of_range):
            assert response.status_code == 400, response.text
            assert response.json()["code"] == "decor_format_shape_mismatch"
            assert response.json()["details"]["field"] == "finished_sides"

    for other_type in ("fanera", "yogoch", "boshqa"):
        plain = await _post_format(
            client,
            access,
            decor_id,
            {"type": other_type, "thickness_mm": "18", "length_mm": 2440, "width_mm": 1220},
        )
        with_sides = await _post_format(
            client,
            access,
            decor_id,
            {
                "type": other_type,
                "thickness_mm": "12",
                "length_mm": 2440,
                "width_mm": 1220,
                "finished_sides": 2,
            },
        )
        assert plain.status_code == 201, plain.text
        assert plain.json()["finished_sides"] is None
        assert with_sides.status_code == 400, with_sides.text
        assert with_sides.json()["details"]["field"] == "finished_sides"


async def test_a_swapped_sheet_size_is_normalized_not_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """`2070x2800` and `2800x2070` are the same sheet, entered two ways.

    The natural key compares the columns literally, so without normalisation the
    platform would end up with two ids for one product — and two branch rows,
    two stock rows and two lines on the same order.
    """
    access = await _platform_access(db_session)
    decor_id = await _decor(client, access)

    swapped = await _create_format(
        client, access, decor_id, {**BOARD, "length_mm": 2070, "width_mm": 2800}
    )
    replay = await _post_format(client, access, decor_id, dict(BOARD))

    assert (swapped["length_mm"], swapped["width_mm"]) == (2800, 2070)
    assert replay.status_code == 409, replay.text
    assert replay.json()["code"] == "decor_format_exists"
    assert replay.json()["details"]["decor_format_id"] == swapped["id"]


async def test_a_duplicate_format_names_the_row_that_already_exists(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """409 with the existing id, so the admin form can link to it.

    Every column of the natural key has to participate: the same sheet in a
    different thickness, a different size or a different finished-face count is
    a different product and must be accepted.
    """
    access = await _platform_access(db_session)
    decor_id = await _decor(client, access)
    first = await _create_format(client, access, decor_id)

    duplicate = await _post_format(client, access, decor_id, dict(BOARD))
    thinner = await _post_format(client, access, decor_id, {**BOARD, "thickness_mm": "16"})
    smaller = await _post_format(
        client, access, decor_id, {**BOARD, "length_mm": 2750, "width_mm": 1830}
    )
    one_sided = await _post_format(client, access, decor_id, {**BOARD, "finished_sides": 1})
    other_substrate = await _post_format(client, access, decor_id, {**BOARD, "type": "mdf"})

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "decor_format_exists"
    assert duplicate.json()["details"]["decor_format_id"] == first["id"]
    for response in (thinner, smaller, one_sided, other_substrate):
        assert response.status_code == 201, response.text
        assert response.json()["id"] != first["id"]


async def test_a_format_cannot_be_added_to_an_inactive_decor(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The pattern left the catalog; entering new products of it is a mistake."""
    access = await _platform_access(db_session)
    decor_id = await _decor(client, access)
    await _create_format(client, access, decor_id)

    deactivated = await client.post(
        f"/api/v1/platform/catalog/decors/{decor_id}/deactivate", headers=_auth(access)
    )
    refused = await _post_format(client, access, decor_id, {**BOARD, "thickness_mm": "16"})
    unknown_decor = await _post_format(client, access, str(uuid.uuid4()), dict(BOARD))

    assert deactivated.status_code == 200
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "decor_inactive"
    assert unknown_decor.status_code == 404
    assert unknown_decor.json()["code"] == "decor_not_found"


async def test_a_format_has_no_patch_only_a_status_switch(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Immutability is the reason branch rows can point at a shared id at all.

    Re-dimensioning a format in place would rewrite what every branch row, stock
    row, cutting panel and historical order item that resolves through it means
    — across workshops, since the id is shared. So the endpoint does not exist.
    """
    access = await _platform_access(db_session)
    decor_id = await _decor(client, access)
    created = await _create_format(client, access, decor_id)

    patched = await client.patch(
        f"/api/v1/platform/catalog/decors/{decor_id}/formats/{created['id']}",
        headers=_auth(access),
        json={"thickness_mm": "16"},
    )
    deactivated = await client.post(
        f"/api/v1/platform/catalog/decors/{decor_id}/formats/{created['id']}/deactivate",
        headers=_auth(access),
    )
    reactivated = await client.post(
        f"/api/v1/platform/catalog/decors/{decor_id}/formats/{created['id']}/activate",
        headers=_auth(access),
    )
    unknown = await client.post(
        f"/api/v1/platform/catalog/decors/{decor_id}/formats/{uuid.uuid4()}/deactivate",
        headers=_auth(access),
    )

    # 404, not 405: nothing is mounted at the format's own path at all — not a
    # GET, not a PATCH — only the two status switches beneath it. A 405 would
    # mean a sibling method exists there, and none should.
    assert patched.status_code == 404
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "inactive"
    assert deactivated.json()["thickness_mm"] == "18"
    assert reactivated.json()["status"] == "active"
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "decor_format_not_found"


# --------------------------------------------------------------------------- #
# Attach: what a branch does with the platform's list
# --------------------------------------------------------------------------- #


async def test_a_branch_attaches_by_format_id_and_the_second_time_is_a_skip(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The picker shows what is already carried, so a repeat is a race.

    Rejecting it would fail an entire batch over a row the operator could not
    have known about; skipping it and naming the format lets the client
    reconcile without a second round trip.
    """
    platform_access = await _platform_access(db_session)
    owner_access, branch_id = await _owner_access(db_session)
    decor_id = await _decor(client, platform_access)
    board = await _create_format(client, platform_access, decor_id)
    tape = await _create_format(client, platform_access, decor_id, dict(TAPE))

    first = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"items": [{"decor_format_id": board["id"], "price_tiyin": 500_000}]},
    )
    # The second call carries the format the branch already has AND a new one:
    # the skip must not take the new row down with it.
    second = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={
            "items": [
                {"decor_format_id": board["id"], "price_tiyin": 900_000},
                {"decor_format_id": tape["id"], "price_tiyin": 9_000},
            ]
        },
    )
    carried = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials", headers=_auth(owner_access)
    )

    assert first.status_code == 201, first.text
    assert first.json()["created"][0]["decor_format_id"] == board["id"]
    assert second.status_code == 201, second.text
    assert second.json()["skipped"] == [board["id"]]
    assert [row["decor_format_id"] for row in second.json()["created"]] == [tape["id"]]
    # The skipped row keeps the price it was attached with — a skip is not an
    # update in disguise.
    prices = {row["decor_format_id"]: row["price_tiyin"] for row in carried.json()}
    assert prices == {board["id"]: 500_000, tape["id"]: 9_000}


async def test_two_branches_carry_one_format_at_their_own_prices(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """One id per physical product across every workshop — the point of the move.

    The format is shared; the price, the threshold and the shelf are not. That
    shared id is what later makes cross-workshop analytics and a central price
    list possible; without it the same Egger sheet is a different row in every
    branch and nothing can be compared.
    """
    platform_access = await _platform_access(db_session)
    first_access, first_branch = await _owner_access(db_session, login="owner-one")
    second_access, second_branch = await _owner_access(db_session, login="owner-two")
    decor_id = await _decor(client, platform_access)
    board = await _create_format(client, platform_access, decor_id)

    async def attach(access: str, branch_id: uuid.UUID, price: int) -> Response:
        return await client.post(
            f"/api/v1/workshop/branches/{branch_id}/materials",
            headers=_auth(access),
            json={
                "items": [{"decor_format_id": board["id"], "price_tiyin": price, "min_stock": 2}]
            },
        )

    first = await attach(first_access, first_branch, 500_000)
    second = await attach(second_access, second_branch, 610_000)
    # Uniqueness is `(branch, format)`, not `format` — the same branch cannot
    # carry it twice, a second branch obviously can.
    replay = await attach(first_access, first_branch, 700_000)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    first_row = first.json()["created"][0]
    second_row = second.json()["created"][0]
    assert first_row["decor_format_id"] == second_row["decor_format_id"] == board["id"]
    assert first_row["id"] != second_row["id"]
    assert (first_row["price_tiyin"], second_row["price_tiyin"]) == (500_000, 610_000)
    assert replay.status_code == 201
    assert replay.json()["created"] == []
    assert replay.json()["skipped"] == [board["id"]]


async def test_an_inactive_format_cannot_be_newly_attached(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Offering a branch a discontinued product would be offering a dead end.

    Not a 404: the branch can see the decor perfectly well, so it gets a message
    it can act on — and the format id, so the sheet can say which row it was.
    """
    platform_access = await _platform_access(db_session)
    owner_access, branch_id = await _owner_access(db_session)
    decor_id = await _decor(client, platform_access)
    board = await _create_format(client, platform_access, decor_id)

    await client.post(
        f"/api/v1/platform/catalog/decors/{decor_id}/formats/{board['id']}/deactivate",
        headers=_auth(platform_access),
    )
    refused = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"items": [{"decor_format_id": board["id"], "price_tiyin": 1}]},
    )
    unknown = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"items": [{"decor_format_id": str(uuid.uuid4()), "price_tiyin": 1}]},
    )

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "decor_format_inactive"
    assert refused.json()["details"]["decor_format_id"] == board["id"]
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "decor_format_not_found"


async def test_the_attach_sheets_second_step_lists_active_formats_with_carried_flagged(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Carried rows stay in the list, flagged — hiding them raises the exact
    question the sheet exists to answer ("does this size exist at all?")."""
    platform_access = await _platform_access(db_session)
    owner_access, branch_id = await _owner_access(db_session)
    decor_id = await _decor(client, platform_access)
    board = await _create_format(client, platform_access, decor_id)
    tape = await _create_format(client, platform_access, decor_id, dict(TAPE))

    await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"items": [{"decor_format_id": board["id"], "price_tiyin": 500_000}]},
    )
    listed = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/decors/{decor_id}/formats",
        headers=_auth(owner_access),
    )
    unknown_decor = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/decors/{uuid.uuid4()}/formats",
        headers=_auth(owner_access),
    )

    assert listed.status_code == 200, listed.text
    carried = {row["decor_format"]["id"]: row["carried"] for row in listed.json()}
    assert carried == {board["id"]: True, tape["id"]: False}
    assert unknown_decor.status_code == 404
    assert unknown_decor.json()["code"] == "decor_not_found"


# --------------------------------------------------------------------------- #
# Spec §6: the three levels of "off"
# --------------------------------------------------------------------------- #


async def test_deactivating_a_format_only_removes_it_from_the_attach_list(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """«Ishlab chiqarishdan chiqqan» is a statement about the factory.

    It says the maker stopped producing this product. It says nothing about the
    branch's shelf: a supplier may still have stock, the branch may still have a
    pile of it, and both selling the remainder and receiving an arrival stay
    open. So the branch row, its price, its threshold, its stock and its
    visibility to clients are all untouched — the only thing that changes is
    that nobody can start carrying it. The branch retires its own row when the
    shelf is empty, which is level three.
    """
    platform_access = await _platform_access(db_session)
    owner_access, branch_id = await _owner_access(db_session)
    client_access = await _client_access(db_session)
    decor_id = await _decor(client, platform_access)
    board = await _create_format(client, platform_access, decor_id)
    tape = await _create_format(client, platform_access, decor_id, dict(TAPE))

    attached = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={
            "items": [
                {"decor_format_id": board["id"], "price_tiyin": 500_000, "min_stock": 3},
                {"decor_format_id": tape["id"], "price_tiyin": 9_000},
            ]
        },
    )
    assert attached.status_code == 201, attached.text
    board_row = next(
        row for row in attached.json()["created"] if row["decor_format_id"] == board["id"]
    )
    stock_in = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "branch_material_id": board_row["id"],
            "quantity": 7,
            "unit_price_tiyin": 400_000,
            "supplier": {"name": "Egger Uz"},
        },
    )
    assert stock_in.status_code == 201, stock_in.text

    before_client = await client.get(
        f"/api/v1/client/branches/{branch_id}/materials", headers=_auth(client_access)
    )
    deactivated = await client.post(
        f"/api/v1/platform/catalog/decors/{decor_id}/formats/{board['id']}/deactivate",
        headers=_auth(platform_access),
    )
    after_client = await client.get(
        f"/api/v1/client/branches/{branch_id}/materials", headers=_auth(client_access)
    )
    after_workshop = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials", headers=_auth(owner_access)
    )
    attach_list = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/decors/{decor_id}/formats",
        headers=_auth(owner_access),
    )
    # An arrival of a discontinued product is legitimate: a supplier may still
    # have a pallet of it.
    later_arrival = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "branch_material_id": board_row["id"],
            "quantity": 3,
            "unit_price_tiyin": 400_000,
            "supplier": {"name": "Egger Uz"},
        },
    )

    assert deactivated.status_code == 200
    # The branch row is exactly as it was — price, threshold, status.
    row_after = next(row for row in after_workshop.json() if row["decor_format_id"] == board["id"])
    assert (row_after["price_tiyin"], row_after["min_stock"], row_after["status"]) == (
        500_000,
        3,
        "active",
    )
    assert row_after["decor_format"]["status"] == "inactive"
    # Clients see the same shelf before and after: the sheets are still there.
    assert [row["id"] for row in before_client.json()] == [row["id"] for row in after_client.json()]
    assert board_row["id"] in [row["id"] for row in after_client.json()]
    # Stock is untouched and still receives arrivals.
    assert later_arrival.status_code == 201, later_arrival.text
    on_hand = await db_session.scalar(
        select(StockItem.on_hand).where(StockItem.branch_material_id == uuid.UUID(board_row["id"]))
    )
    assert on_hand == 10
    # The ONLY change: it is gone from step two of the attach sheet.
    assert [row["decor_format"]["id"] for row in attach_list.json()] == [tape["id"]]


async def test_the_branch_retiring_its_own_row_is_what_hides_it_from_clients(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Level three of the §6 matrix, for contrast with the level-two test above.

    "We don't offer this" is the branch's own statement and the only one of the
    three that takes a row off the client's screen while leaving the stock and
    the history alone.
    """
    platform_access = await _platform_access(db_session)
    owner_access, branch_id = await _owner_access(db_session)
    client_access = await _client_access(db_session)
    decor_id = await _decor(client, platform_access)
    board = await _create_format(client, platform_access, decor_id)

    attached = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"items": [{"decor_format_id": board["id"], "price_tiyin": 500_000}]},
    )
    row_id = attached.json()["created"][0]["id"]
    retired = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials/{row_id}/deactivate",
        headers=_auth(owner_access),
    )
    client_view = await client.get(
        f"/api/v1/client/branches/{branch_id}/materials", headers=_auth(client_access)
    )
    workshop_view = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials", headers=_auth(owner_access)
    )

    assert retired.status_code == 200
    assert retired.json()["status"] == "inactive"
    assert client_view.json() == []
    # The branch still sees its own retired row — the stock on it is real.
    assert [row["id"] for row in workshop_view.json()] == [row_id]


async def test_the_branch_format_pair_is_unique_at_the_database(db_session: AsyncSession) -> None:
    """`uq_branch_materials_branch_format` is full, not partial.

    The old index was partial only because customer boards lived in this table
    and two walk-ins with the same sheet collided. Boards have their own table
    now, so nothing may bypass the rule — and the attach service's skip above is
    a courtesy on top of it, not the rule itself.
    """
    _, branch, _ = await seed_workshop_with_owner(db_session, login=f"uq-{uuid.uuid4().hex[:6]}")
    carried = await seed_panel_material(db_session, branch_id=branch.id)

    db_session.add(
        BranchMaterial(
            branch_id=branch.id,
            decor_format_id=carried.decor_format_id,
            price_tiyin=1,
            min_stock=0,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
