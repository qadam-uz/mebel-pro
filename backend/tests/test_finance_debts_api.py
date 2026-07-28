"""Supplier and client debt folds, statements, and signed adjustments."""

import uuid
from datetime import UTC, datetime

from app.core.security import hash_password
from app.models.enums import (
    AuthenticatedPrincipalType,
    OrderStatus,
    Permission,
    UserStatus,
)
from app.modules.access.api import create_session
from app.modules.access.contracts import Client, PermissionGrant, WorkshopUser
from app.modules.sales.contracts import Order
from app.modules.workshop.api import next_branch_no
from app.modules.workshop.contracts import Branch
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
    workshop, branch, owner = await seed_workshop_with_owner(db_session, login=login)
    owner.password_reset_required = False
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token, workshop.id, branch.id


async def _staff_access(
    db_session: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID,
    permission: Permission,
) -> str:
    staff = WorkshopUser(
        workshop_id=workshop_id,
        login=f"staff-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("StaffTemp123"),
        full_name="Debt Staff",
        phone="+998901234222",
        is_owner=False,
        home_branch_id=branch_id,
        status=UserStatus.ACTIVE,
        password_reset_required=False,
    )
    db_session.add(staff)
    await db_session.flush()
    db_session.add(
        PermissionGrant(
            workshop_user_id=staff.id,
            permission=permission,
            branch_id=branch_id,
            granted_by_user_id=staff.id,
            granted_at=datetime.now(UTC),
        )
    )
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=staff.id,
    )
    return tokens.access_token


async def _carried_material(
    client: AsyncClient, platform_access: str, owner_access: str, branch_id: uuid.UUID
) -> str:
    manufacturer = await client.post(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(platform_access),
        json={"name": f"Egger {uuid.uuid4().hex[:6]}", "country": "AT"},
    )
    material = await client.post(
        "/api/v1/platform/catalog/materials",
        headers=_auth(platform_access),
        json={
            "kind": "panel",
            "manufacturer_id": manufacturer.json()["id"],
            "type": "dsp",
            "thickness_mm": "18",
            "color": "Sonoma oak",
            "decor_code": "H1334",
            "panel_length_mm": 2750,
            "panel_width_mm": 1830,
            "grain_direction": True,
        },
    )
    material_id: str = material.json()["id"]
    added = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"material_id": material_id, "price_tiyin": 60000000, "min_stock": 0},
    )
    assert added.status_code == 201
    return material_id


async def test_supplier_debt_fold_statement_and_voids(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, _, branch_id = await _owner_fixture(db_session)
    material_id = await _carried_material(client, platform_access, owner_access, branch_id)

    supplier = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/suppliers",
        headers=_auth(owner_access),
        json={"name": "Panel Trade MChJ", "phone": "+998712300010"},
    )
    supplier_id = supplier.json()["id"]
    idle = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/suppliers",
        headers=_auth(owner_access),
        json={"name": "Idle Supplier"},
    )
    idle_id = idle.json()["id"]

    # The worked example, in tiyin: opening -4.2M -> delivery -10.3M -> payment
    # +10M -> discount +0.5M => "Bizning qarzimiz" 4.0M.
    opening = await client.post(
        "/api/v1/workshop/finance/debts/adjustments",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "amount_tiyin": -4_200_000,
            "adjusted_on": "2026-06-01",
            "note": "boshlang'ich qoldiq",
        },
    )
    assert opening.status_code == 201
    stock_in = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/stock-in",
        headers=_auth(owner_access),
        json={
            "material_id": material_id,
            "quantity": 20,
            "unit_price_tiyin": 515_000,
            "supplier_id": supplier_id,
        },
    )
    assert stock_in.status_code == 201
    today = stock_in.json()["created_at"][:10]
    payment = await client.post(
        "/api/v1/workshop/finance/expenses",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "category": "raw_materials",
            "amount_tiyin": 10_000_000,
            "incurred_on": today,
            "description": "Panel Trade to'lovi",
            "supplier_id": supplier_id,
        },
    )
    assert payment.status_code == 201
    assert payment.json()["supplier_id"] == supplier_id
    assert payment.json()["vendor"] == "Panel Trade MChJ"
    discount = await client.post(
        "/api/v1/workshop/finance/debts/adjustments",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "amount_tiyin": 500_000,
            "adjusted_on": today,
            "note": "chegirma",
        },
    )
    assert discount.status_code == 201

    debts = await client.get(
        "/api/v1/workshop/finance/debts/suppliers",
        headers=_auth(owner_access),
    )
    assert debts.status_code == 200
    assert [row["counterparty_id"] for row in debts.json()["rows"]] == [supplier_id]
    assert debts.json()["rows"][0]["balance_tiyin"] == -4_000_000
    assert debts.json()["we_owe_total_tiyin"] == 4_000_000
    assert debts.json()["they_owe_total_tiyin"] == 0

    with_idle = await client.get(
        "/api/v1/workshop/finance/debts/suppliers?only_with_debt=false",
        headers=_auth(owner_access),
    )
    assert {row["counterparty_id"] for row in with_idle.json()["rows"]} == {supplier_id, idle_id}

    statement = await client.get(
        f"/api/v1/workshop/finance/debts/suppliers/{supplier_id}/statement",
        headers=_auth(owner_access),
    )
    assert statement.status_code == 200
    body = statement.json()
    assert [row["kind"] for row in body["rows"]] == [
        "adjustment",
        "delivery",
        "payment",
        "adjustment",
    ]
    assert [row["balance_after_tiyin"] for row in body["rows"]] == [
        -4_200_000,
        -14_500_000,
        -4_500_000,
        -4_000_000,
    ]
    # A delivery term is now one invoice, not one stock-in line: same money,
    # the grain the supplier's own document is written in.
    assert body["rows"][1]["amount_tiyin"] == -10_300_000
    assert body["rows"][1]["invoice_no"] == "K-0001"
    assert body["rows"][1]["line_count"] == 1
    assert body["rows"][1]["discount_tiyin"] == 0
    assert body["opening_balance_tiyin"] == 0
    assert body["closing_balance_tiyin"] == -4_000_000
    assert body["current_balance_tiyin"] == -4_000_000
    # The document names both parties, not just the counterparty.
    assert body["workshop_name"]
    assert body["workshop_phone"]
    # Period turnover, in the stored sign convention: 10.5M grew their side of
    # the balance (payment + discount), 14.5M shrank it (opening + delivery).
    assert body["period_increase_tiyin"] == 10_500_000
    assert body["period_decrease_tiyin"] == 14_500_000

    ranged = await client.get(
        f"/api/v1/workshop/finance/debts/suppliers/{supplier_id}/statement?date_from={today}",
        headers=_auth(owner_access),
    )
    assert ranged.json()["opening_balance_tiyin"] == -4_200_000
    assert len(ranged.json()["rows"]) == 3
    assert ranged.json()["closing_balance_tiyin"] == -4_000_000
    assert ranged.json()["period_increase_tiyin"] == 10_500_000
    assert ranged.json()["period_decrease_tiyin"] == 10_300_000

    document = await client.get(
        f"/api/v1/workshop/finance/debts/suppliers/{supplier_id}/statement.pdf",
        headers=_auth(owner_access),
    )
    assert document.status_code == 200
    assert document.headers["content-type"] == "application/pdf"
    assert document.content.startswith(b"%PDF-")

    # Voids self-correct the fold — no cleanup, no sync.
    voided_discount = await client.post(
        f"/api/v1/workshop/finance/debts/adjustments/{discount.json()['id']}/void",
        headers=_auth(owner_access),
        json={"reason": "xato kiritildi"},
    )
    assert voided_discount.status_code == 200
    voided_payment = await client.post(
        f"/api/v1/workshop/finance/expenses/{payment.json()['id']}/void",
        headers=_auth(owner_access),
        json={"reason": "xato to'lov"},
    )
    assert voided_payment.status_code == 200
    after_voids = await client.get(
        "/api/v1/workshop/finance/debts/suppliers",
        headers=_auth(owner_access),
    )
    assert after_voids.json()["rows"][0]["balance_tiyin"] == -14_500_000
    double_void = await client.post(
        f"/api/v1/workshop/finance/debts/adjustments/{discount.json()['id']}/void",
        headers=_auth(owner_access),
        json={"reason": "yana"},
    )
    assert double_void.status_code == 409


def _order(
    *,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID,
    client_id: uuid.UUID,
    total_tiyin: int,
    status: OrderStatus,
    confirmed_at: datetime | None,
) -> Order:
    return Order(
        order_number=f"ORD-{uuid.uuid4().hex[:10]}",
        client_id=client_id,
        workshop_id=workshop_id,
        branch_id=branch_id,
        cutting_result_id=uuid.uuid4(),
        status=status,
        contact_name="Debt Client",
        contact_phone="+998909999333",
        subtotal_materials_tiyin=total_tiyin,
        total_tiyin=total_tiyin,
        confirmed_at=confirmed_at,
    )


async def test_client_debt_fold_statement_and_cancelled_advance(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, workshop_id, branch_id = await _owner_fixture(db_session)
    aziza = Client(phone="+998909999444", name="Aziza Karimova")
    quoted = Client(phone="+998909999445", name="Quoted Only")
    prepaid = Client(phone="+998909999446", name="Prepaid Cancelled")
    db_session.add_all([aziza, quoted, prepaid])
    await db_session.flush()

    confirmed_order = _order(
        workshop_id=workshop_id,
        branch_id=branch_id,
        client_id=aziza.id,
        total_tiyin=5_000_000,
        status=OrderStatus.CONFIRMED,
        confirmed_at=datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
    )
    doomed_order = _order(
        workshop_id=workshop_id,
        branch_id=branch_id,
        client_id=aziza.id,
        total_tiyin=1_000_000,
        status=OrderStatus.CONFIRMED,
        confirmed_at=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )
    quote_only = _order(
        workshop_id=workshop_id,
        branch_id=branch_id,
        client_id=quoted.id,
        total_tiyin=9_000_000,
        status=OrderStatus.NEW,
        confirmed_at=None,
    )
    prepaid_order = _order(
        workshop_id=workshop_id,
        branch_id=branch_id,
        client_id=prepaid.id,
        total_tiyin=300_000,
        status=OrderStatus.CONFIRMED,
        confirmed_at=datetime(2026, 6, 15, 10, 0, tzinfo=UTC),
    )
    db_session.add_all([confirmed_order, doomed_order, quote_only, prepaid_order])
    await db_session.flush()

    async def pay(order_id: uuid.UUID, amount: int, on: str) -> None:
        response = await client.post(
            "/api/v1/workshop/finance/income",
            headers=_auth(owner_access),
            json={
                "type": "order_payment",
                "order_id": str(order_id),
                "amount_tiyin": amount,
                "method": "cash",
                "received_on": on,
            },
        )
        assert response.status_code == 201

    await pay(confirmed_order.id, 2_000_000, "2026-06-11")
    await pay(doomed_order.id, 1_000_000, "2026-06-12")
    await pay(prepaid_order.id, 300_000, "2026-06-15")
    # Both cancellations happen after money was taken: the order total leaves
    # the fold, the payment stays — the truth is we hold their advance.
    doomed_order.status = OrderStatus.CANCELLED
    prepaid_order.status = OrderStatus.CANCELLED
    await db_session.flush()
    notebook = await client.post(
        "/api/v1/workshop/finance/debts/adjustments",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "client_id": str(aziza.id),
            "amount_tiyin": 250_000,
            "adjusted_on": "2026-06-13",
            "note": "daftar qarzi",
        },
    )
    assert notebook.status_code == 201

    debts = await client.get(
        "/api/v1/workshop/finance/debts/clients",
        headers=_auth(owner_access),
    )
    assert debts.status_code == 200
    rows = {row["counterparty_id"]: row for row in debts.json()["rows"]}
    # Aziza: 5M (confirmed) - 2M - 1M (payments incl. the cancelled order's) + 250k.
    assert rows[str(aziza.id)]["balance_tiyin"] == 2_250_000
    # The prepaid-then-cancelled client flips to our debt (we hold the advance).
    assert rows[str(prepaid.id)]["balance_tiyin"] == -300_000
    # A quote (status new) never joins the fold.
    assert str(quoted.id) not in rows
    assert debts.json()["they_owe_total_tiyin"] == 2_250_000
    assert debts.json()["we_owe_total_tiyin"] == 300_000
    # Receivables first: Aziza sorts above the client we owe.
    assert [row["counterparty_id"] for row in debts.json()["rows"]] == [
        str(aziza.id),
        str(prepaid.id),
    ]

    statement = await client.get(
        f"/api/v1/workshop/finance/debts/clients/{aziza.id}/statement",
        headers=_auth(owner_access),
    )
    assert statement.status_code == 200
    body = statement.json()
    assert [row["kind"] for row in body["rows"]] == [
        "order",
        "payment",
        "payment",
        "adjustment",
    ]
    assert [row["balance_after_tiyin"] for row in body["rows"]] == [
        5_000_000,
        3_000_000,
        2_000_000,
        2_250_000,
    ]
    assert body["rows"][0]["order_number"] == confirmed_order.order_number
    assert body["rows"][2]["order_number"] == doomed_order.order_number
    assert body["rows"][1]["method"] == "cash"
    assert body["current_balance_tiyin"] == 2_250_000
    # 5M order + 250k adjustment grew her debt; 3M of payments shrank it.
    assert body["period_increase_tiyin"] == 5_250_000
    assert body["period_decrease_tiyin"] == 3_000_000

    document = await client.get(
        f"/api/v1/workshop/finance/debts/clients/{aziza.id}/statement.pdf",
        headers=_auth(owner_access),
    )
    assert document.status_code == 200
    assert document.headers["content-type"] == "application/pdf"
    assert document.content.startswith(b"%PDF-")

    unknown_client = await client.get(
        f"/api/v1/workshop/finance/debts/clients/{uuid.uuid4()}/statement",
        headers=_auth(owner_access),
    )
    assert unknown_client.status_code == 404


async def test_adjustment_validation_and_scope(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, workshop_id, branch_id = await _owner_fixture(db_session)
    other_owner_access, _, other_branch_id = await _owner_fixture(db_session, login="owner_b")
    supplier = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/suppliers",
        headers=_auth(owner_access),
        json={"name": "Scoped Supplier"},
    )
    supplier_id = supplier.json()["id"]
    client_row = Client(phone="+998909999111", name="Debt Client")
    db_session.add(client_row)
    await db_session.flush()

    both_parties = await client.post(
        "/api/v1/workshop/finance/debts/adjustments",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "client_id": str(client_row.id),
            "amount_tiyin": 1000,
            "adjusted_on": "2026-06-01",
            "note": "invalid",
        },
    )
    no_party = await client.post(
        "/api/v1/workshop/finance/debts/adjustments",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "amount_tiyin": 1000,
            "adjusted_on": "2026-06-01",
            "note": "invalid",
        },
    )
    zero_amount = await client.post(
        "/api/v1/workshop/finance/debts/adjustments",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "amount_tiyin": 0,
            "adjusted_on": "2026-06-01",
            "note": "invalid",
        },
    )
    blank_note = await client.post(
        "/api/v1/workshop/finance/debts/adjustments",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "supplier_id": supplier_id,
            "amount_tiyin": 1000,
            "adjusted_on": "2026-06-01",
            "note": "   ",
        },
    )
    unknown_client = await client.post(
        "/api/v1/workshop/finance/debts/adjustments",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "client_id": str(uuid.uuid4()),
            "amount_tiyin": 1000,
            "adjusted_on": "2026-06-01",
            "note": "no such client",
        },
    )
    # A supplier from another workshop is invisible to this workshop's fold.
    # The branch has to be the *other* owner's own, or the branch scope refuses
    # the write before the supplier lookup ever runs.
    foreign_supplier = await client.post(
        "/api/v1/workshop/finance/debts/adjustments",
        headers=_auth(other_owner_access),
        json={
            "branch_id": str(other_branch_id),
            "supplier_id": supplier_id,
            "amount_tiyin": 1000,
            "adjusted_on": "2026-06-01",
            "note": "foreign",
        },
    )
    client_opening = await client.post(
        "/api/v1/workshop/finance/debts/adjustments",
        headers=_auth(owner_access),
        json={
            "branch_id": str(branch_id),
            "client_id": str(client_row.id),
            "amount_tiyin": 250_000,
            "adjusted_on": "2026-06-01",
            "note": "daftar qarzi",
        },
    )

    assert both_parties.status_code == 400
    assert both_parties.json()["code"] == "invalid_party"
    assert no_party.status_code == 400
    assert zero_amount.status_code == 400
    assert zero_amount.json()["code"] == "invalid_amount"
    assert blank_note.status_code == 400
    assert blank_note.json()["code"] == "note_required"
    assert unknown_client.status_code == 404
    assert foreign_supplier.status_code == 404
    assert client_opening.status_code == 201
    assert client_opening.json()["client_id"] == str(client_row.id)

    inventory_staff = await _staff_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_INVENTORY,
    )
    finance_staff = await _staff_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_FINANCE,
    )
    forbidden = await client.get(
        "/api/v1/workshop/finance/debts/suppliers",
        headers=_auth(inventory_staff),
    )
    allowed = await client.get(
        "/api/v1/workshop/finance/debts/suppliers",
        headers=_auth(finance_staff),
    )
    assert forbidden.status_code == 403
    assert allowed.status_code == 200

    # Another workshop's statement view of this supplier 404s.
    foreign_statement = await client.get(
        f"/api/v1/workshop/finance/debts/suppliers/{supplier_id}/statement",
        headers=_auth(other_owner_access),
    )
    assert foreign_statement.status_code == 404
    assert other_branch_id is not None


async def test_per_branch_debt_balances_sum_to_the_workshop_total(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The invariant behind branch-scoped debts (QAD-182).

    Every term in the fold names a branch, so asking for one branch and asking
    for the workshop must never disagree: the parts add up to the whole. Without
    that, an accountant reconciling per branch would be chasing money the
    workshop view says exists and no branch claims.
    """

    owner_access, workshop_id, branch_one = await _owner_fixture(db_session)
    second = Branch(
        workshop_id=workshop_id,
        branch_no=await next_branch_no(db_session),
        name="Chilonzor",
        address="Tashkent, Chilonzor",
        phone="+998904444444",
    )
    db_session.add(second)
    await db_session.flush()
    branch_two = second.id

    supplier = await client.post(
        f"/api/v1/workshop/branches/{branch_one}/suppliers",
        headers=_auth(owner_access),
        json={"name": "Ikki Filial Ta'minot"},
    )
    assert supplier.status_code == 201
    supplier_id = supplier.json()["id"]

    # One adjustment in each branch, deliberately different amounts and signs.
    for branch_id, amount in ((branch_one, -1_500_000), (branch_two, 400_000)):
        created = await client.post(
            "/api/v1/workshop/finance/debts/adjustments",
            headers=_auth(owner_access),
            json={
                "branch_id": str(branch_id),
                "supplier_id": supplier_id,
                "amount_tiyin": amount,
                "adjusted_on": "2026-06-01",
                "note": "ochilish qoldig'i",
            },
        )
        assert created.status_code == 201
        assert created.json()["branch_id"] == str(branch_id)

    async def balance(branch_id: uuid.UUID | None) -> int:
        query = "" if branch_id is None else f"?branch_id={branch_id}"
        response = await client.get(
            f"/api/v1/workshop/finance/debts/suppliers{query}",
            headers=_auth(owner_access),
        )
        assert response.status_code == 200
        rows = response.json()["rows"]
        return sum(row["balance_tiyin"] for row in rows)

    first_total = await balance(branch_one)
    second_total = await balance(branch_two)
    whole = await balance(None)

    assert first_total == -1_500_000
    assert second_total == 400_000
    assert whole == first_total + second_total == -1_100_000

    # The statement obeys the same split: one row per branch, both workshop-wide.
    async def statement_rows(branch_id: uuid.UUID | None) -> int:
        query = "" if branch_id is None else f"?branch_id={branch_id}"
        response = await client.get(
            f"/api/v1/workshop/finance/debts/suppliers/{supplier_id}/statement{query}",
            headers=_auth(owner_access),
        )
        assert response.status_code == 200
        return len(response.json()["rows"])

    assert await statement_rows(branch_one) == 1
    assert await statement_rows(branch_two) == 1
    assert await statement_rows(None) == 2
