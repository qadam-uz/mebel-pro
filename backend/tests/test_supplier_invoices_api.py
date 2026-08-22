"""Supplier invoices: the arrival document, its adjustments, and what it owes.

The point of the grain change lives here: a skidka on the document has to reach
the supplier balance, and a half-written arrival must not reach stock at all.
The lifecycle half is here too: a voided document reverses its stock and drops
out of every derived reader, and a header edit corrects the paper in place.
"""

import uuid

from app.models.enums import AuthenticatedPrincipalType
from app.modules.access.api import create_session
from app.modules.support.contracts import ActionLog, Notification
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_platform_user, seed_workshop_with_owner


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _platform_access(db_session: AsyncSession) -> str:
    platform = await seed_platform_user(
        db_session,
        login=f"platform-{uuid.uuid4().hex[:8]}",
        password_reset_required=False,
    )
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        principal_id=platform.id,
    )
    return tokens.access_token


async def _owner_fixture(
    db_session: AsyncSession,
    *,
    login: str = "owner",
) -> tuple[str, uuid.UUID, uuid.UUID]:
    """Logins are globally unique (QAD-157) — a test seeding a second workshop
    must pass a distinct `login`."""
    workshop, branch, owner = await seed_workshop_with_owner(db_session, login=login)
    owner.password_reset_required = False
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token, workshop.id, branch.id


async def _carried_material(
    client: AsyncClient,
    platform_access: str,
    owner_access: str,
    branch_id: uuid.UUID,
    *,
    color: str = "Sonoma oak",
) -> str:
    """Walk the whole chain: manufacturer → decor → platform format → branch row.

    Three owners, three writes. The platform enters the pattern and the concrete
    product; the branch only decides to carry that product at its own price.

    Returns the BRANCH material id — the id an invoice line, a stock row and an
    order item all point at.
    """
    manufacturer = await client.post(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(platform_access),
        json={"name": f"Egger {uuid.uuid4().hex[:6]}", "country": "AT"},
    )
    decor = await client.post(
        "/api/v1/platform/catalog/decors",
        headers=_auth(platform_access),
        json={
            "manufacturer_id": manufacturer.json()["id"],
            "code": f"H{uuid.uuid4().hex[:4]}",
            "name": color,
            "has_grain": True,
        },
    )
    assert decor.status_code == 201, decor.text
    decor_format = await client.post(
        f"/api/v1/platform/catalog/decors/{decor.json()['id']}/formats",
        headers=_auth(platform_access),
        json={
            "type": "ldsp",
            "thickness_mm": "18",
            "length_mm": 2750,
            "width_mm": 1830,
            "finished_sides": 2,
        },
    )
    assert decor_format.status_code == 201, decor_format.text
    added = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={
            "items": [
                {
                    "decor_format_id": decor_format.json()["id"],
                    "price_tiyin": 60_000_000,
                    "min_stock": 0,
                }
            ],
        },
    )
    assert added.status_code == 201, added.text
    branch_material_id: str = added.json()["created"][0]["id"]
    return branch_material_id


async def _supplier(client: AsyncClient, owner_access: str, branch_id: uuid.UUID) -> str:
    created = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/suppliers",
        headers=_auth(owner_access),
        json={"name": "Egger Uz", "phone": "+998712300010"},
    )
    assert created.status_code == 201
    supplier_id: str = created.json()["id"]
    return supplier_id


async def _supplier_balance(client: AsyncClient, owner_access: str, supplier_id: str) -> int:
    debts = await client.get(
        "/api/v1/workshop/finance/debts/suppliers?only_with_debt=false",
        headers=_auth(owner_access),
    )
    assert debts.status_code == 200
    for row in debts.json()["rows"]:
        if row["counterparty_id"] == supplier_id:
            balance: int = row["balance_tiyin"]
            return balance
    return 0


async def test_four_line_invoice_books_its_discount_into_the_supplier_debt(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    materials = [
        await _carried_material(client, platform_access, owner_access, branch_id, color=color)
        for color in ("Oak", "Walnut", "Ash", "Beech")
    ]
    supplier_id = await _supplier(client, owner_access, branch_id)

    # 9 510 000 of panels, 500 000 skidka on the document as a whole.
    created = await client.post(
        "/api/v1/workshop/inventory/invoices",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "discount_tiyin": 500_000,
            "note": "Iyul yetkazishi",
            "lines": [
                {"branch_material_id": materials[0], "quantity": 10, "unit_price_tiyin": 300_000},
                {"branch_material_id": materials[1], "quantity": 7, "unit_price_tiyin": 450_000},
                {"branch_material_id": materials[2], "quantity": 4, "unit_price_tiyin": 390_000},
                {"branch_material_id": materials[3], "quantity": 5, "unit_price_tiyin": 360_000},
            ],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["invoice_no"] == "K-0001"
    assert body["subtotal_tiyin"] == 9_510_000
    assert body["total_tiyin"] == 9_010_000
    assert body["line_count"] == 4
    assert body["payment_status"] == "unpaid"
    assert body["outstanding_tiyin"] == 9_010_000
    assert [line["quantity"] for line in body["lines"]] == [10, 7, 4, 5]

    # Stock moved exactly per line, as an unbatched arrival always did.
    stock = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock",
        headers=_auth(owner_access),
    )
    on_hand = {row["branch_material_id"]: row["on_hand"] for row in stock.json()}
    assert [on_hand[material] for material in materials] == [10, 7, 4, 5]

    transactions = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock-transactions",
        headers=_auth(owner_access),
    )
    stock_ins = [row for row in transactions.json() if row["type"] == "stock_in"]
    assert len(stock_ins) == 4

    # The whole point: the debt is the discounted total, not the raw line sum.
    assert await _supplier_balance(client, owner_access, supplier_id) == -9_010_000


async def test_surcharge_raises_the_total_and_the_debt_symmetrically(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)

    created = await client.post(
        "/api/v1/workshop/inventory/invoices",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "surcharge_tiyin": 120_000,
            "lines": [
                {"branch_material_id": material_id, "quantity": 3, "unit_price_tiyin": 500_000}
            ],
        },
    )
    assert created.status_code == 201
    assert created.json()["subtotal_tiyin"] == 1_500_000
    assert created.json()["total_tiyin"] == 1_620_000
    assert await _supplier_balance(client, owner_access, supplier_id) == -1_620_000


async def test_invoice_adjustments_stay_inside_their_bounds(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)
    line = {"branch_material_id": material_id, "quantity": 2, "unit_price_tiyin": 500_000}

    too_big = await client.post(
        "/api/v1/workshop/inventory/invoices",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "discount_tiyin": 1_000_001,
            "lines": [line],
        },
    )
    assert too_big.status_code == 400
    assert too_big.json()["code"] == "discount_above_subtotal"

    negative = await client.post(
        "/api/v1/workshop/inventory/invoices",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "surcharge_tiyin": -1,
            "lines": [line],
        },
    )
    assert negative.status_code == 400
    assert negative.json()["code"] == "invalid_adjustment"

    empty = await client.post(
        "/api/v1/workshop/inventory/invoices",
        headers=_auth(owner_access),
        json={"branch_id": str(branch_id), "supplier_id": supplier_id, "lines": []},
    )
    assert empty.status_code == 400
    assert empty.json()["code"] == "invoice_lines_required"


async def test_a_bad_line_leaves_no_invoice_and_no_stock_movement(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    good = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)

    failed = await client.post(
        "/api/v1/workshop/inventory/invoices",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "lines": [
                {"branch_material_id": good, "quantity": 5, "unit_price_tiyin": 300_000},
                {"branch_material_id": good, "quantity": 2, "unit_price_tiyin": 300_000},
                # Third line names a material this branch does not carry.
                {
                    "branch_material_id": str(uuid.uuid4()),
                    "quantity": 1,
                    "unit_price_tiyin": 100_000,
                },
            ],
        },
    )
    assert failed.status_code == 404

    invoices = await client.get(
        f"/api/v1/workshop/inventory/invoices?branch_id={branch_id}",
        headers=_auth(owner_access),
    )
    assert invoices.json() == []
    stock = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock",
        headers=_auth(owner_access),
    )
    assert [row["on_hand"] for row in stock.json()] == [0]
    assert await _supplier_balance(client, owner_access, supplier_id) == 0


async def test_invoice_numbers_run_per_workshop_not_per_branch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, first_branch = await _owner_fixture(db_session)
    second = await client.post(
        "/api/v1/workshop/branches",
        headers=_auth(owner_access),
        json={
            "name": "Chilonzor",
            "address": "Tashkent, Chilonzor",
            "phone": "+998901010101",
            "latitude": "41.28",
            "longitude": "69.20",
        },
    )
    assert second.status_code == 201
    second_branch = second.json()["id"]
    first_material = await _carried_material(client, platform_access, owner_access, first_branch)
    second_material = await _carried_material(
        client,
        platform_access,
        owner_access,
        second_branch,
        color="Walnut",
    )
    supplier_id = await _supplier(client, owner_access, first_branch)

    first_invoice = await client.post(
        "/api/v1/workshop/inventory/invoices",
        headers=_auth(owner_access),
        json={
            "branch_id": str(first_branch),
            "supplier_id": supplier_id,
            "lines": [
                {"branch_material_id": first_material, "quantity": 1, "unit_price_tiyin": 100_000}
            ],
        },
    )
    second_invoice = await client.post(
        "/api/v1/workshop/inventory/invoices",
        headers=_auth(owner_access),
        json={
            "branch_id": second_branch,
            "supplier_id": supplier_id,
            "lines": [
                {"branch_material_id": second_material, "quantity": 1, "unit_price_tiyin": 100_000}
            ],
        },
    )
    assert first_invoice.json()["invoice_no"] == "K-0001"
    assert second_invoice.json()["invoice_no"] == "K-0002"


async def test_payment_status_walks_unpaid_to_paid_and_lets_an_advance_through(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)

    invoice = await client.post(
        "/api/v1/workshop/inventory/invoices",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "lines": [
                {"branch_material_id": material_id, "quantity": 4, "unit_price_tiyin": 500_000}
            ],
        },
    )
    invoice_id = invoice.json()["id"]
    today = invoice.json()["invoice_date"]
    assert invoice.json()["total_tiyin"] == 2_000_000

    payable = await client.get(
        "/api/v1/workshop/finance/payable-invoices",
        headers=_auth(owner_access),
    )
    assert [row["id"] for row in payable.json()] == [invoice_id]
    assert payable.json()[0]["outstanding_tiyin"] == 2_000_000

    part = await client.post(
        "/api/v1/workshop/finance/expenses",
        headers=_auth(owner_access),
        json={
            "category": "raw_materials",
            "amount_tiyin": 800_000,
            "incurred_on": today,
            "description": "Qisman to'lov",
            "invoice_id": invoice_id,
        },
    )
    assert part.status_code == 201
    # Supplier and branch are taken from the invoice, not from the caller.
    assert part.json()["supplier_id"] == supplier_id
    assert part.json()["branch_id"] == str(branch_id)
    assert part.json()["invoice_no"] == "K-0001"

    partial = await client.get(
        f"/api/v1/workshop/inventory/invoices/{invoice_id}",
        headers=_auth(owner_access),
    )
    assert partial.json()["payment_status"] == "partial"
    assert partial.json()["outstanding_tiyin"] == 1_200_000

    # Overpaying is allowed on purpose — a supplier advance is a normal event.
    rest = await client.post(
        "/api/v1/workshop/finance/expenses",
        headers=_auth(owner_access),
        json={
            "category": "raw_materials",
            "amount_tiyin": 1_500_000,
            "incurred_on": today,
            "description": "Qoldiq + avans",
            "invoice_id": invoice_id,
        },
    )
    assert rest.status_code == 201

    paid = await client.get(
        f"/api/v1/workshop/inventory/invoices/{invoice_id}",
        headers=_auth(owner_access),
    )
    assert paid.json()["payment_status"] == "paid"
    assert paid.json()["outstanding_tiyin"] == 0
    # 2.3M paid against a 2.0M invoice leaves the supplier owing us 0.3M.
    assert await _supplier_balance(client, owner_access, supplier_id) == 300_000

    settled = await client.get(
        "/api/v1/workshop/finance/payable-invoices",
        headers=_auth(owner_access),
    )
    assert settled.json() == []


async def test_a_supplier_expense_without_an_invoice_still_pays_the_supplier(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The legacy shape: an advance booked straight against the supplier."""

    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)

    invoice = await client.post(
        "/api/v1/workshop/inventory/invoices",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "lines": [
                {"branch_material_id": material_id, "quantity": 2, "unit_price_tiyin": 500_000}
            ],
        },
    )
    today = invoice.json()["invoice_date"]
    # A supplier advance is a term in that supplier's per-branch balance
    # (QAD-182), so it has to name the branch it belongs to.
    unbranched = await client.post(
        "/api/v1/workshop/finance/expenses",
        headers=_auth(owner_access),
        json={
            "category": "raw_materials",
            "amount_tiyin": 400_000,
            "incurred_on": today,
            "description": "Avans",
            "supplier_id": supplier_id,
        },
    )
    assert unbranched.status_code == 400
    assert unbranched.json()["code"] == "branch_required_for_supplier_expense"

    advance = await client.post(
        "/api/v1/workshop/finance/expenses",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "category": "raw_materials",
            "amount_tiyin": 400_000,
            "incurred_on": today,
            "description": "Avans",
            "supplier_id": supplier_id,
        },
    )
    assert advance.status_code == 201
    assert advance.json()["invoice_id"] is None
    assert await _supplier_balance(client, owner_access, supplier_id) == -600_000
    # It pays the supplier, not the faktura — the invoice is still unpaid.
    still_open = await client.get(
        f"/api/v1/workshop/inventory/invoices/{invoice.json()['id']}",
        headers=_auth(owner_access),
    )
    assert still_open.json()["payment_status"] == "unpaid"


async def test_invoices_are_invisible_to_another_workshop(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)
    invoice = await client.post(
        "/api/v1/workshop/inventory/invoices",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "lines": [
                {"branch_material_id": material_id, "quantity": 1, "unit_price_tiyin": 100_000}
            ],
        },
    )
    invoice_id = invoice.json()["id"]

    outsider_access, _, outsider_branch = await _owner_fixture(db_session, login="rival-owner")
    assert (
        await client.get(
            f"/api/v1/workshop/inventory/invoices/{invoice_id}",
            headers=_auth(outsider_access),
        )
    ).status_code == 403
    assert (
        await client.get(
            f"/api/v1/workshop/inventory/invoices?branch_id={branch_id}",
            headers=_auth(outsider_access),
        )
    ).status_code == 403
    assert (
        await client.get(
            "/api/v1/workshop/finance/payable-invoices",
            headers=_auth(outsider_access),
        )
    ).json() == []
    # Paying another workshop's faktura is a 404, not a silent cross-tenant link.
    stolen = await client.post(
        "/api/v1/workshop/finance/expenses",
        headers=_auth(outsider_access),
        json={
            "branch_id": str(outsider_branch),
            "category": "raw_materials",
            "amount_tiyin": 100_000,
            "incurred_on": invoice.json()["invoice_date"],
            "description": "Begona faktura",
            "invoice_id": invoice_id,
        },
    )
    assert stolen.status_code == 404


async def _create_invoice(
    client: AsyncClient,
    owner_access: str,
    branch_id: uuid.UUID,
    supplier_id: str,
    lines: list[dict[str, object]],
    **header: object,
) -> dict[str, object]:
    created = await client.post(
        "/api/v1/workshop/inventory/invoices",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "lines": lines,
            **header,
        },
    )
    assert created.status_code == 201, created.text
    body: dict[str, object] = created.json()
    return body


async def _on_hand(client: AsyncClient, owner_access: str, branch_id: uuid.UUID) -> dict[str, int]:
    stock = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock",
        headers=_auth(owner_access),
    )
    assert stock.status_code == 200
    return {row["branch_material_id"]: row["on_hand"] for row in stock.json()}


async def test_voiding_an_invoice_reverses_stock_and_leaves_every_derived_reader(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    first = await _carried_material(client, platform_access, owner_access, branch_id, color="Oak")
    second = await _carried_material(client, platform_access, owner_access, branch_id, color="Ash")
    supplier_id = await _supplier(client, owner_access, branch_id)

    # An earlier priced arrival for the same material — the price the prefill has
    # to fall back to once the typo above it is voided.
    await _create_invoice(
        client,
        owner_access,
        branch_id,
        supplier_id,
        [{"branch_material_id": first, "quantity": 2, "unit_price_tiyin": 300_000}],
    )
    typo = await _create_invoice(
        client,
        owner_access,
        branch_id,
        supplier_id,
        [
            {"branch_material_id": first, "quantity": 10, "unit_price_tiyin": 3_000_000},
            {"branch_material_id": second, "quantity": 4, "unit_price_tiyin": 500_000},
        ],
        discount_tiyin=200_000,
    )
    invoice_id = typo["id"]
    assert typo["status"] == "recorded"
    assert await _on_hand(client, owner_access, branch_id) == {first: 12, second: 4}

    voided = await client.post(
        f"/api/v1/workshop/inventory/invoices/{invoice_id}/void",
        headers=_auth(owner_access),
        json={"reason": "Narx xato kiritilgan"},
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["status"] == "voided"
    assert voided.json()["voided_reason"] == "Narx xato kiritilgan"
    assert voided.json()["voided_by_name"] == "Workshop Owner"
    assert voided.json()["voided_at"] is not None
    # The document still reads as its own lines — the reversals are movements.
    assert len(voided.json()["lines"]) == 2

    # Stock is back where it was before the typo.
    assert await _on_hand(client, owner_access, branch_id) == {first: 2, second: 0}

    transactions = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock-transactions",
        headers=_auth(owner_access),
    )
    reversals = {
        row["branch_material_id"]: row
        for row in transactions.json()
        if row["type"] == "stock_in_void"
    }
    assert sorted(reversals) == sorted([first, second])
    assert reversals[first]["quantity"] == -10
    assert reversals[first]["balance_after"] == 2
    assert reversals[second]["quantity"] == -4
    assert reversals[second]["balance_after"] == 0
    # A reversal is not price history: it carries no money at all.
    assert reversals[first]["unit_price_tiyin"] is None
    assert reversals[first]["total_price_tiyin"] is None

    # Only the surviving 600 000 arrival is left in the fold.
    assert await _supplier_balance(client, owner_access, supplier_id) == -600_000
    statement = await client.get(
        f"/api/v1/workshop/finance/debts/suppliers/{supplier_id}/statement",
        headers=_auth(owner_access),
    )
    assert statement.status_code == 200, statement.text
    assert [row["invoice_no"] for row in statement.json()["rows"]] == ["K-0001"]

    payable = await client.get(
        "/api/v1/workshop/finance/payable-invoices",
        headers=_auth(owner_access),
    )
    assert invoice_id not in [row["id"] for row in payable.json()]

    # The voided 3 000 000 typo must not come back as tomorrow's suggestion.
    last_price = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials/{first}/last-price",
        headers=_auth(owner_access),
    )
    assert last_price.json()["unit_price_tiyin"] == 300_000

    # History is preserved: the row is in the unfiltered list, under no filter.
    listed = await client.get(
        f"/api/v1/workshop/inventory/invoices?branch_id={branch_id}",
        headers=_auth(owner_access),
    )
    assert invoice_id in [row["id"] for row in listed.json()]
    for wanted in ("unpaid", "partial", "paid"):
        filtered = await client.get(
            f"/api/v1/workshop/inventory/invoices?branch_id={branch_id}&payment_status={wanted}",
            headers=_auth(owner_access),
        )
        assert invoice_id not in [row["id"] for row in filtered.json()]


async def test_a_recorded_payment_blocks_the_void_until_it_is_itself_voided(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)
    invoice = await _create_invoice(
        client,
        owner_access,
        branch_id,
        supplier_id,
        [{"branch_material_id": material_id, "quantity": 4, "unit_price_tiyin": 500_000}],
    )
    invoice_id = invoice["id"]

    expense = await client.post(
        "/api/v1/workshop/finance/expenses",
        headers=_auth(owner_access),
        json={
            "category": "raw_materials",
            "amount_tiyin": 800_000,
            "incurred_on": invoice["invoice_date"],
            "description": "Qisman to'lov",
            "invoice_id": invoice_id,
        },
    )
    assert expense.status_code == 201

    blocked = await client.post(
        f"/api/v1/workshop/inventory/invoices/{invoice_id}/void",
        headers=_auth(owner_access),
        json={"reason": "Faktura xato"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "invoice_has_payments"

    blank = await client.post(
        f"/api/v1/workshop/inventory/invoices/{invoice_id}/void",
        headers=_auth(owner_access),
        json={"reason": "   "},
    )
    assert blank.status_code == 400
    assert blank.json()["code"] == "invoice_void_reason_required"

    dropped = await client.post(
        f"/api/v1/workshop/finance/expenses/{expense.json()['id']}/void",
        headers=_auth(owner_access),
        json={"reason": "Noto'g'ri fakturaga yozilgan"},
    )
    assert dropped.status_code == 200, dropped.text

    voided = await client.post(
        f"/api/v1/workshop/inventory/invoices/{invoice_id}/void",
        headers=_auth(owner_access),
        json={"reason": "Faktura xato"},
    )
    assert voided.status_code == 200, voided.text
    # The whole story stays readable — the voided payment is still listed.
    detail = await client.get(
        f"/api/v1/workshop/inventory/invoices/{invoice_id}",
        headers=_auth(owner_access),
    )
    assert [row["status"] for row in detail.json()["payments"]] == ["voided"]

    again = await client.post(
        f"/api/v1/workshop/inventory/invoices/{invoice_id}/void",
        headers=_auth(owner_access),
        json={"reason": "Yana"},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "invoice_already_voided"


async def test_a_void_that_takes_the_balance_negative_succeeds_and_notifies(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The goods already left; refusing the reversal would leave stock too high."""

    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)
    invoice = await _create_invoice(
        client,
        owner_access,
        branch_id,
        supplier_id,
        [{"branch_material_id": material_id, "quantity": 5, "unit_price_tiyin": 400_000}],
    )
    written_off = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-adjustments",
        headers=_auth(owner_access),
        json={"branch_material_id": material_id, "quantity": -3, "note": "Shikastlangan"},
    )
    assert written_off.status_code == 201, written_off.text

    voided = await client.post(
        f"/api/v1/workshop/inventory/invoices/{invoice['id']}/void",
        headers=_auth(owner_access),
        json={"reason": "Faktura bekor qilindi"},
    )
    assert voided.status_code == 200, voided.text
    assert (await _on_hand(client, owner_access, branch_id))[material_id] == -3

    notified = (
        await db_session.scalars(
            select(Notification.event_code).where(
                Notification.event_code == "inventory.negative_stock"
            )
        )
    ).all()
    assert list(notified) == ["inventory.negative_stock"]


async def test_header_edits_correct_the_document_in_place(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)
    other = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/suppliers",
        headers=_auth(owner_access),
        json={"name": "Kronospan Uz"},
    )
    other_id = other.json()["id"]
    invoice = await _create_invoice(
        client,
        owner_access,
        branch_id,
        supplier_id,
        [{"branch_material_id": material_id, "quantity": 4, "unit_price_tiyin": 500_000}],
        discount_tiyin=300_000,
        surcharge_tiyin=50_000,
    )
    invoice_id = invoice["id"]
    url = f"/api/v1/workshop/inventory/invoices/{invoice_id}"

    # The three fields that left the UI are refused rather than ignored, so a
    # stale client is told its request is wrong instead of half-saving.
    for retired in (
        {"note": "Yangi izoh"},
        {"discount_tiyin": 0},
        {"surcharge_tiyin": 0},
        {"supplier_doc_no": "№ 17/A"},
    ):
        refused = await client.patch(url, headers=_auth(owner_access), json=retired)
        assert refused.status_code == 422, refused.text

    edited = await client.patch(
        url,
        headers=_auth(owner_access),
        json={"supplier_id": other_id},
    )
    assert edited.status_code == 200, edited.text
    # The untouched adjustments are carried through, so the stored total formula
    # still holds after a header-only edit.
    assert edited.json()["subtotal_tiyin"] == 2_000_000
    assert edited.json()["total_tiyin"] == 1_750_000
    assert edited.json()["supplier_id"] == other_id
    # The debt moved with the header, no sync step anywhere.
    assert await _supplier_balance(client, owner_access, supplier_id) == 0
    assert await _supplier_balance(client, owner_access, other_id) == -1_750_000

    # The lines' denormalized supplier followed the header.
    transactions = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock-transactions",
        headers=_auth(owner_access),
    )
    assert [row["supplier_id"] for row in transactions.json()] == [other_id]

    audited = await db_session.scalar(
        select(func.count())
        .select_from(ActionLog)
        .where(ActionLog.action == "inventory.invoice.update")
    )
    assert audited == 1

    tomorrow = await client.patch(
        url, headers=_auth(owner_access), json={"invoice_date": "2999-01-01"}
    )
    assert tomorrow.status_code == 400
    assert tomorrow.json()["code"] == "future_date_not_allowed"

    await client.post(
        f"/api/v1/workshop/branches/{branch_id}/suppliers/{supplier_id}/deactivate",
        headers=_auth(owner_access),
    )
    inactive = await client.patch(
        url, headers=_auth(owner_access), json={"supplier_id": supplier_id}
    )
    assert inactive.status_code == 400
    assert inactive.json()["code"] == "supplier_inactive"

    # A legacy discount the lines can no longer cover is refused, not written —
    # the DB CHECK caps it at the subtotal.
    shrunk = await client.patch(
        url,
        headers=_auth(owner_access),
        json={
            "lines": [
                {"branch_material_id": material_id, "quantity": 1, "unit_price_tiyin": 100_000}
            ]
        },
    )
    assert shrunk.status_code == 400
    assert shrunk.json()["code"] == "invoice_discount_too_big"

    await client.post(f"{url}/void", headers=_auth(owner_access), json={"reason": "Butunlay xato"})
    frozen = await client.patch(
        url, headers=_auth(owner_access), json={"invoice_date": "2026-08-01"}
    )
    assert frozen.status_code == 409
    assert frozen.json()["code"] == "invoice_voided"


async def test_editing_lines_rewrites_the_arrival_and_replays_the_balance_chain(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The replay's whole point: movements *behind* the edited one stay true.

    Delta arithmetic can fix `on_hand`, but nothing can repair the
    `balance_after` snapshot a later movement already took against the old
    quantity — so the chain is recomputed instead.
    """

    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)
    other = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/suppliers",
        headers=_auth(owner_access),
        json={"name": "Kronospan Uz"},
    )
    other_id = other.json()["id"]
    invoice = await _create_invoice(
        client,
        owner_access,
        branch_id,
        supplier_id,
        [{"branch_material_id": material_id, "quantity": 10, "unit_price_tiyin": 300_000}],
    )
    invoice_id = invoice["id"]
    entered_at = (await _stock_ins(client, owner_access, branch_id))[0]["created_at"]

    # Two movements land on top of the arrival before anyone notices the typo.
    await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-adjustments",
        headers=_auth(owner_access),
        json={"branch_material_id": material_id, "quantity": -4, "note": "Shikastlangan"},
    )
    await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-adjustments",
        headers=_auth(owner_access),
        json={"branch_material_id": material_id, "quantity": 2, "note": "Topildi"},
    )
    assert (await _on_hand(client, owner_access, branch_id))[material_id] == 8

    edited = await client.patch(
        f"/api/v1/workshop/inventory/invoices/{invoice_id}",
        headers=_auth(owner_access),
        json={
            "supplier_id": other_id,
            "lines": [
                {"branch_material_id": material_id, "quantity": 6, "unit_price_tiyin": 250_000}
            ],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["subtotal_tiyin"] == 1_500_000
    assert edited.json()["total_tiyin"] == 1_500_000
    assert edited.json()["line_count"] == 1
    assert [line["quantity"] for line in edited.json()["lines"]] == [6]
    assert await _supplier_balance(client, owner_access, other_id) == -1_500_000

    # 6 - 4 + 2, and every row on the chain says so.
    assert (await _on_hand(client, owner_access, branch_id))[material_id] == 4
    ledger = await _ledger(client, owner_access, branch_id, material_id)
    assert [(row["quantity"], row["balance_after"]) for row in ledger] == [(6, 6), (-4, 2), (2, 4)]

    # The corrected arrival keeps its place in the log — a typo fix must not
    # push the delivery to the top of it — and the new supplier reached the row.
    assert ledger[0]["created_at"] == entered_at
    assert ledger[0]["supplier_id"] == other_id
    assert ledger[0]["invoice_id"] == invoice_id


async def test_editing_lines_below_what_was_consumed_goes_negative_and_notifies(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)
    invoice = await _create_invoice(
        client,
        owner_access,
        branch_id,
        supplier_id,
        [{"branch_material_id": material_id, "quantity": 5, "unit_price_tiyin": 400_000}],
    )
    await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-adjustments",
        headers=_auth(owner_access),
        json={"branch_material_id": material_id, "quantity": -3, "note": "Ishlab chiqarishga"},
    )

    edited = await client.patch(
        f"/api/v1/workshop/inventory/invoices/{invoice['id']}",
        headers=_auth(owner_access),
        json={
            "lines": [
                {"branch_material_id": material_id, "quantity": 1, "unit_price_tiyin": 400_000}
            ]
        },
    )
    assert edited.status_code == 200, edited.text
    # Only one panel ever arrived; three already left. The books say -2, which
    # is the true statement, and the next real arrival heals it.
    assert (await _on_hand(client, owner_access, branch_id))[material_id] == -2

    notified = (
        await db_session.scalars(
            select(Notification.event_code).where(
                Notification.event_code == "inventory.negative_stock"
            )
        )
    ).all()
    assert list(notified) == ["inventory.negative_stock"]


async def test_one_edit_can_add_and_remove_materials_at_once(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    kept = await _carried_material(client, platform_access, owner_access, branch_id, color="Oak")
    dropped = await _carried_material(client, platform_access, owner_access, branch_id, color="Ash")
    added = await _carried_material(client, platform_access, owner_access, branch_id, color="Beech")
    supplier_id = await _supplier(client, owner_access, branch_id)
    invoice = await _create_invoice(
        client,
        owner_access,
        branch_id,
        supplier_id,
        [
            {"branch_material_id": kept, "quantity": 4, "unit_price_tiyin": 300_000},
            {"branch_material_id": dropped, "quantity": 3, "unit_price_tiyin": 200_000},
        ],
    )

    edited = await client.patch(
        f"/api/v1/workshop/inventory/invoices/{invoice['id']}",
        headers=_auth(owner_access),
        json={
            "lines": [
                {"branch_material_id": kept, "quantity": 6, "unit_price_tiyin": 300_000},
                {"branch_material_id": added, "quantity": 2, "unit_price_tiyin": 150_000},
            ]
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["subtotal_tiyin"] == 2_100_000

    on_hand = await _on_hand(client, owner_access, branch_id)
    # The removed material's quantity goes back out — its balance is the point
    # of replaying the *union* of the old and the new material sets.
    assert (on_hand[kept], on_hand[dropped], on_hand[added]) == (6, 0, 2)


async def test_editing_a_paid_invoice_is_allowed_and_re_derives_the_outstanding(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Blocking here would trap a genuine correction; overpayment already warns."""

    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)
    invoice = await _create_invoice(
        client,
        owner_access,
        branch_id,
        supplier_id,
        [{"branch_material_id": material_id, "quantity": 4, "unit_price_tiyin": 500_000}],
    )
    paid = await client.post(
        "/api/v1/workshop/finance/expenses",
        headers=_auth(owner_access),
        json={
            "category": "raw_materials",
            "amount_tiyin": 800_000,
            "incurred_on": invoice["invoice_date"],
            "description": "Qisman to'lov",
            "invoice_id": invoice["id"],
        },
    )
    assert paid.status_code == 201, paid.text

    edited = await client.patch(
        f"/api/v1/workshop/inventory/invoices/{invoice['id']}",
        headers=_auth(owner_access),
        json={
            "lines": [
                {"branch_material_id": material_id, "quantity": 2, "unit_price_tiyin": 500_000}
            ]
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["total_tiyin"] == 1_000_000
    assert edited.json()["paid_tiyin"] == 800_000
    assert edited.json()["outstanding_tiyin"] == 200_000
    assert edited.json()["payment_status"] == "partial"


async def test_on_hand_always_equals_the_sum_of_the_item_s_transactions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The invariant the replay promotes from "true by construction" to enforced."""

    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)
    invoice = await _create_invoice(
        client,
        owner_access,
        branch_id,
        supplier_id,
        [{"branch_material_id": material_id, "quantity": 7, "unit_price_tiyin": 300_000}],
    )
    url = f"/api/v1/workshop/inventory/invoices/{invoice['id']}"
    await _assert_chain_holds(client, owner_access, branch_id, material_id)

    edited = await client.patch(
        url,
        headers=_auth(owner_access),
        json={
            "lines": [
                {"branch_material_id": material_id, "quantity": 3, "unit_price_tiyin": 300_000}
            ]
        },
    )
    assert edited.status_code == 200, edited.text
    await _assert_chain_holds(client, owner_access, branch_id, material_id)

    voided = await client.post(f"{url}/void", headers=_auth(owner_access), json={"reason": "Xato"})
    assert voided.status_code == 200, voided.text
    await _assert_chain_holds(client, owner_access, branch_id, material_id)
    assert (await _on_hand(client, owner_access, branch_id))[material_id] == 0


async def _ledger(
    client: AsyncClient,
    owner_access: str,
    branch_id: uuid.UUID,
    branch_material_id: str,
) -> list[dict[str, object]]:
    """One material's movements, oldest first — the order the chain runs in."""

    listed = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock-transactions"
        f"?branch_material_id={branch_material_id}",
        headers=_auth(owner_access),
    )
    assert listed.status_code == 200, listed.text
    rows: list[dict[str, object]] = listed.json()
    return sorted(rows, key=lambda row: (str(row["created_at"]), str(row["id"])))


async def _stock_ins(
    client: AsyncClient,
    owner_access: str,
    branch_id: uuid.UUID,
) -> list[dict[str, object]]:
    listed = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/stock-transactions",
        headers=_auth(owner_access),
    )
    assert listed.status_code == 200, listed.text
    return [row for row in listed.json() if row["type"] == "stock_in"]


async def _assert_chain_holds(
    client: AsyncClient,
    owner_access: str,
    branch_id: uuid.UUID,
    branch_material_id: str,
) -> None:
    rows = await _ledger(client, owner_access, branch_id, branch_material_id)
    running = 0
    for row in rows:
        running += int(str(row["quantity"]))
        assert row["balance_after"] == running, rows
    assert (await _on_hand(client, owner_access, branch_id))[branch_material_id] == running


async def test_search_finds_an_invoice_by_its_own_number(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)
    supplier_id = await _supplier(client, owner_access, branch_id)
    invoice = await _create_invoice(
        client,
        owner_access,
        branch_id,
        supplier_id,
        [{"branch_material_id": material_id, "quantity": 1, "unit_price_tiyin": 100_000}],
    )
    await _create_invoice(
        client,
        owner_access,
        branch_id,
        supplier_id,
        [{"branch_material_id": material_id, "quantity": 1, "unit_price_tiyin": 100_000}],
    )

    found = await client.get(
        f"/api/v1/workshop/inventory/invoices?branch_id={branch_id}&search={invoice['invoice_no']}",
        headers=_auth(owner_access),
    )
    assert [row["id"] for row in found.json()] == [invoice["id"]]
