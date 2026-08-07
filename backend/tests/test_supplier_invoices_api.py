"""Supplier invoices: the arrival document, its adjustments, and what it owes.

The point of the grain change lives here: a skidka on the document has to reach
the supplier balance, and a half-written arrival must not reach stock at all.
"""

import uuid

from app.models.enums import AuthenticatedPrincipalType
from app.modules.access.api import create_session
from httpx import AsyncClient
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
    """Create a dekor and have the branch carry it in one format.

    Returns the BRANCH material id — the id an invoice line, a stock row and an
    order item all point at since the reshape.
    """
    manufacturer = await client.post(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(platform_access),
        json={"name": f"Egger {uuid.uuid4().hex[:6]}", "country": "AT"},
    )
    dekor = await client.post(
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(platform_access),
        json={
            "manufacturer_id": manufacturer.json()["id"],
            "tur": "ldsp",
            "kod": f"H{uuid.uuid4().hex[:4]}",
            "nomi": color,
            "tolali": True,
        },
    )
    assert dekor.status_code == 201, dekor.text
    added = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={
            "items": [
                {
                    "dekor_id": dekor.json()["id"],
                    "formats": [
                        {
                            "qalinlik_mm": "18",
                            "uzunlik_mm": 2750,
                            "eni_mm": 1830,
                            "price_tiyin": 60_000_000,
                            "min_stock": 0,
                        }
                    ],
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
