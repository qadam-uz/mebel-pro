"""The order behind an order-payment income (QAD-123).

Two halves of one seam. Choosing: the picker only ever offered in-production
orders from one unfiltered page, so an order the client had already collected —
the most common moment money changes hands — vanished ("my order isn't in the
list"). Naming: the ledger then looked the order back up through `sales`, which
fails for exactly the role that keys the payments, so the income row carries its
own order label and settlement instead.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from app.core.security import hash_password
from app.models.enums import (
    AuthenticatedPrincipalType,
    LedgerStatus,
    OrderStatus,
    Permission,
    UserStatus,
)
from app.modules.access.api import create_session
from app.modules.access.contracts import Client, PermissionGrant, WorkshopUser
from app.modules.finance.contracts import Income
from app.modules.sales.contracts import Order
from app.modules.workshop.api import next_branch_no
from app.modules.workshop.contracts import Branch
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.factories import seed_workshop_with_owner

PAYABLE_ORDERS_URL = "/api/v1/workshop/finance/payable-orders"
INCOME_URL = "/api/v1/workshop/finance/income"


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _owner_fixture(db_session: AsyncSession) -> tuple[str, uuid.UUID, uuid.UUID, uuid.UUID]:
    workshop, branch, owner = await seed_workshop_with_owner(db_session)
    owner.password_reset_required = False
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token, workshop.id, branch.id, owner.id


async def _extra_branch(db_session: AsyncSession, *, workshop_id: uuid.UUID) -> uuid.UUID:
    branch = Branch(
        workshop_id=workshop_id,
        branch_no=await next_branch_no(db_session),
        name="Chilonzor",
        address="Tashkent, Chilonzor",
        phone="+998904444444",
    )
    db_session.add(branch)
    await db_session.flush()
    return branch.id


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
        full_name="Finance Staff",
        phone="+998901234555",
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
    await db_session.flush()
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=staff.id,
    )
    return tokens.access_token


async def _client_row(db_session: AsyncSession, *, phone: str, name: str) -> Client:
    row = Client(phone=phone, name=name)
    db_session.add(row)
    await db_session.flush()
    return row


async def _order(
    db_session: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID,
    client_id: uuid.UUID,
    order_number: str,
    total_tiyin: int,
    status: OrderStatus = OrderStatus.COMPLETED,
    contact_name: str = "Aziza Karimova",
    contact_phone: str = "+998901112233",
    created_at: datetime | None = None,
) -> Order:
    order = Order(
        order_number=order_number,
        client_id=client_id,
        workshop_id=workshop_id,
        branch_id=branch_id,
        cutting_result_id=uuid.uuid4(),
        status=status,
        contact_name=contact_name,
        contact_phone=contact_phone,
        subtotal_materials_tiyin=total_tiyin,
        total_tiyin=total_tiyin,
        created_at=created_at or datetime.now(UTC),
    )
    db_session.add(order)
    await db_session.flush()
    return order


async def _income(
    db_session: AsyncSession,
    *,
    workshop_id: uuid.UUID,
    branch_id: uuid.UUID,
    order_id: uuid.UUID,
    amount_tiyin: int,
    recorded_by_user_id: uuid.UUID,
    status: LedgerStatus = LedgerStatus.RECORDED,
) -> Income:
    income = Income(
        workshop_id=workshop_id,
        branch_id=branch_id,
        type="order_payment",
        order_id=order_id,
        amount_tiyin=amount_tiyin,
        method="cash",
        received_on=datetime.now(UTC).date(),
        status=status,
        recorded_by_user_id=recorded_by_user_id,
    )
    db_session.add(income)
    await db_session.flush()
    return income


async def test_payable_orders_offers_collected_orders_and_hides_settled_ones(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token, workshop_id, branch_id, owner_id = await _owner_fixture(db_session)
    buyer = await _client_row(db_session, phone="+998901112233", name="Aziza Karimova")

    collected = await _order(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        client_id=buyer.id,
        order_number="ORD-COLLECTED",
        total_tiyin=5_000_000,
        status=OrderStatus.COMPLETED,
    )
    in_production = await _order(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        client_id=buyer.id,
        order_number="ORD-CUTTING",
        total_tiyin=3_000_000,
        status=OrderStatus.CUTTING,
    )
    settled = await _order(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        client_id=buyer.id,
        order_number="ORD-SETTLED",
        total_tiyin=1_000_000,
        status=OrderStatus.READY,
    )
    cancelled = await _order(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        client_id=buyer.id,
        order_number="ORD-CANCELLED",
        total_tiyin=2_000_000,
        status=OrderStatus.CANCELLED,
    )
    voided_payment_order = await _order(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        client_id=buyer.id,
        order_number="ORD-VOIDED-PAYMENT",
        total_tiyin=800_000,
        status=OrderStatus.READY,
    )
    await _income(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        order_id=collected.id,
        amount_tiyin=2_000_000,
        recorded_by_user_id=owner_id,
    )
    await _income(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        order_id=settled.id,
        amount_tiyin=1_000_000,
        recorded_by_user_id=owner_id,
    )
    await _income(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        order_id=cancelled.id,
        amount_tiyin=500_000,
        recorded_by_user_id=owner_id,
    )
    await _income(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        order_id=voided_payment_order.id,
        amount_tiyin=800_000,
        recorded_by_user_id=owner_id,
        status=LedgerStatus.VOIDED,
    )

    response = await client.get(PAYABLE_ORDERS_URL, headers=_auth(access_token))

    assert response.status_code == 200
    by_number = {row["order_number"]: row for row in response.json()}
    assert set(by_number) == {
        "ORD-COLLECTED",
        "ORD-CUTTING",
        "ORD-VOIDED-PAYMENT",
    }
    assert by_number["ORD-COLLECTED"]["order_id"] == str(collected.id)
    assert by_number["ORD-COLLECTED"]["status"] == "completed"
    assert by_number["ORD-COLLECTED"]["total_tiyin"] == 5_000_000
    assert by_number["ORD-COLLECTED"]["recorded_tiyin"] == 2_000_000
    assert by_number["ORD-COLLECTED"]["balance_tiyin"] == 3_000_000
    assert by_number["ORD-CUTTING"]["order_id"] == str(in_production.id)
    assert by_number["ORD-VOIDED-PAYMENT"]["balance_tiyin"] == 800_000

    settle = await client.post(
        "/api/v1/workshop/finance/income",
        headers=_auth(access_token),
        json={
            "type": "order_payment",
            "order_id": str(collected.id),
            "amount_tiyin": 3_000_000,
            "method": "cash",
            "received_on": datetime.now(UTC).date().isoformat(),
        },
    )
    after = await client.get(PAYABLE_ORDERS_URL, headers=_auth(access_token))

    assert settle.status_code == 201
    assert "ORD-COLLECTED" not in {row["order_number"] for row in after.json()}


async def test_payable_orders_search_matches_number_name_and_formatted_phone(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access_token, workshop_id, branch_id, _ = await _owner_fixture(db_session)
    buyer = await _client_row(db_session, phone="+998901112233", name="Aziza Karimova")
    other = await _client_row(db_session, phone="+998935556677", name="Bobur Rasulov")

    old = await _order(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        client_id=buyer.id,
        order_number="ORD-2026-000042",
        total_tiyin=4_000_000,
        contact_name="Aziza Karimova",
        contact_phone="+998901112233",
        created_at=datetime(2026, 1, 9, 9, 0, tzinfo=UTC),
    )
    for index in range(25):
        await _order(
            db_session,
            workshop_id=workshop_id,
            branch_id=branch_id,
            client_id=other.id,
            order_number=f"ORD-2026-9000{index:02d}",
            total_tiyin=1_000_000,
            contact_name="Bobur Rasulov",
            contact_phone="+998935556677",
            created_at=datetime(2026, 7, 1 + index % 20, 9, 0, tzinfo=UTC),
        )

    unfiltered = await client.get(PAYABLE_ORDERS_URL, headers=_auth(access_token))
    by_number = await client.get(
        f"{PAYABLE_ORDERS_URL}?search=000042",
        headers=_auth(access_token),
    )
    by_name = await client.get(
        f"{PAYABLE_ORDERS_URL}?search=aziza",
        headers=_auth(access_token),
    )
    by_formatted_phone = await client.get(
        f"{PAYABLE_ORDERS_URL}?search=90 111 22 33",
        headers=_auth(access_token),
    )
    by_phone_tail = await client.get(
        f"{PAYABLE_ORDERS_URL}?search=2233",
        headers=_auth(access_token),
    )

    # The six-months-old order is off the default page — search is what finds it.
    assert len(unfiltered.json()) == 20
    assert old.order_number not in {row["order_number"] for row in unfiltered.json()}
    for response in (by_number, by_name, by_formatted_phone, by_phone_tail):
        assert response.status_code == 200
        assert [row["order_id"] for row in response.json()] == [str(old.id)]


async def test_payable_orders_scope_by_branch_permission_and_tenant(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, workshop_id, branch_id, _ = await _owner_fixture(db_session)
    other_branch_id = await _extra_branch(db_session, workshop_id=workshop_id)
    _, rival_branch, _ = await seed_workshop_with_owner(db_session, login="rival-owner")
    buyer = await _client_row(db_session, phone="+998901112233", name="Aziza Karimova")

    home = await _order(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        client_id=buyer.id,
        order_number="ORD-HOME",
        total_tiyin=1_000_000,
    )
    away = await _order(
        db_session,
        workshop_id=workshop_id,
        branch_id=other_branch_id,
        client_id=buyer.id,
        order_number="ORD-AWAY",
        total_tiyin=1_000_000,
    )
    await _order(
        db_session,
        workshop_id=rival_branch.workshop_id,
        branch_id=rival_branch.id,
        client_id=buyer.id,
        order_number="ORD-RIVAL",
        total_tiyin=1_000_000,
    )
    finance_staff = await _staff_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_FINANCE,
    )
    reports_staff = await _staff_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.VIEW_FINANCE_REPORTS,
    )

    owner_all = await client.get(PAYABLE_ORDERS_URL, headers=_auth(owner_access))
    owner_scoped = await client.get(
        f"{PAYABLE_ORDERS_URL}?branch_id={other_branch_id}",
        headers=_auth(owner_access),
    )
    staff_all = await client.get(PAYABLE_ORDERS_URL, headers=_auth(finance_staff))
    staff_foreign_branch = await client.get(
        f"{PAYABLE_ORDERS_URL}?branch_id={other_branch_id}",
        headers=_auth(finance_staff),
    )
    reports_only = await client.get(PAYABLE_ORDERS_URL, headers=_auth(reports_staff))

    assert {row["order_number"] for row in owner_all.json()} == {"ORD-HOME", "ORD-AWAY"}
    assert [row["order_id"] for row in owner_scoped.json()] == [str(away.id)]
    assert [row["order_id"] for row in staff_all.json()] == [str(home.id)]
    assert staff_foreign_branch.status_code == 403
    assert staff_foreign_branch.json()["code"] == "forbidden"
    assert reports_only.status_code == 403
    assert reports_only.json()["code"] == "forbidden"


@contextmanager
def _order_reads(db_session: AsyncSession) -> Iterator[list[str]]:
    """Collects every SQL statement issued against the orders table."""
    bind = db_session.bind
    assert isinstance(bind, AsyncEngine)
    statements: list[str] = []

    def _record(
        conn: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if " orders" in statement.lower():
            statements.append(statement)

    event.listen(bind.sync_engine, "before_cursor_execute", _record)
    try:
        yield statements
    finally:
        event.remove(bind.sync_engine, "before_cursor_execute", _record)


async def test_income_rows_name_their_order_for_finance_only_staff(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The ledger must name an order for the role that keys the payments.

    An accountant holds `manage_finance` and nothing else, so reading the order
    back through `sales` 404s — asserted here, because that 404 is the whole
    reason the label travels on the income row. A fully settled order leaves the
    picker for good, so its rows can't be named from there either.
    """
    _, workshop_id, branch_id, _ = await _owner_fixture(db_session)
    accountant = await _staff_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_FINANCE,
    )
    buyer = await _client_row(db_session, phone="+998901112233", name="Aziza Karimova")
    order = await _order(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        client_id=buyer.id,
        order_number="ORD-2026-000007",
        total_tiyin=5_000_000,
        contact_name="Aziza Karimova",
    )
    today = datetime.now(UTC).date().isoformat()

    advance = await client.post(
        INCOME_URL,
        headers=_auth(accountant),
        json={
            "type": "order_payment",
            "order_id": str(order.id),
            "amount_tiyin": 2_000_000,
            "method": "cash",
            "received_on": today,
        },
    )
    unlinked = await client.post(
        INCOME_URL,
        headers=_auth(accountant),
        json={
            "type": "other",
            "branch_id": str(branch_id),
            "amount_tiyin": 400_000,
            "method": "cash",
            "received_on": today,
        },
    )
    corrected = await client.patch(
        f"{INCOME_URL}/{advance.json()['id']}",
        headers=_auth(accountant),
        json={"amount_tiyin": 2_500_000},
    )
    await client.post(
        INCOME_URL,
        headers=_auth(accountant),
        json={
            "type": "order_payment",
            "order_id": str(order.id),
            "amount_tiyin": 2_500_000,
            "method": "cash",
            "received_on": today,
        },
    )
    listed = await client.get(INCOME_URL, headers=_auth(accountant))
    picker = await client.get(PAYABLE_ORDERS_URL, headers=_auth(accountant))
    order_read = await client.get(
        f"/api/v1/workshop/orders/{order.id}",
        headers=_auth(accountant),
    )

    assert advance.status_code == 201
    assert advance.json()["order"] == {
        "order_id": str(order.id),
        "order_number": "ORD-2026-000007",
        "contact_name": "Aziza Karimova",
        "total_tiyin": 5_000_000,
        "recorded_tiyin": 2_000_000,
        "balance_tiyin": 3_000_000,
    }
    # An income with no order says so, rather than carrying an empty shell.
    assert unlinked.json()["order"] is None
    # The edit modal reads its headroom off this: 5 000 000 - 2 500 000 recorded.
    assert corrected.json()["order"]["recorded_tiyin"] == 2_500_000
    assert corrected.json()["order"]["balance_tiyin"] == 2_500_000
    # Settled: gone from the picker, still named in the ledger.
    assert [row["order_number"] for row in picker.json()] == []
    order_rows = [row for row in listed.json() if row["order_id"] == str(order.id)]
    assert len(order_rows) == 2
    for row in order_rows:
        assert row["order"]["order_number"] == "ORD-2026-000007"
        assert row["order"]["contact_name"] == "Aziza Karimova"
        assert row["order"]["balance_tiyin"] == 0
    assert order_read.status_code == 404


async def test_income_page_resolves_every_order_in_one_query(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Set-based, not per-row: `list_incomes` returns a whole period."""
    access_token, workshop_id, branch_id, owner_id = await _owner_fixture(db_session)
    buyer = await _client_row(db_session, phone="+998901112233", name="Aziza Karimova")
    for index in range(4):
        order = await _order(
            db_session,
            workshop_id=workshop_id,
            branch_id=branch_id,
            client_id=buyer.id,
            order_number=f"ORD-2026-00002{index}",
            total_tiyin=1_000_000,
        )
        await _income(
            db_session,
            workshop_id=workshop_id,
            branch_id=branch_id,
            order_id=order.id,
            amount_tiyin=100_000,
            recorded_by_user_id=owner_id,
        )

    with _order_reads(db_session) as order_statements:
        listed = await client.get(INCOME_URL, headers=_auth(access_token))

    assert listed.status_code == 200
    assert {row["order"]["order_number"] for row in listed.json()} == {
        f"ORD-2026-00002{index}" for index in range(4)
    }
    assert len(order_statements) == 1


async def test_ledger_names_who_handled_the_money_and_filters_by_them(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """ "Who took this cash?" is answered on the row, and is a filter.

    The id was always stored; a ledger that prints it is unreadable, and an
    owner reconciling a till needs one person's rows, not the whole day's.
    """

    owner_access, workshop_id, branch_id, owner_id = await _owner_fixture(db_session)
    buyer = await _client_row(db_session, phone="+998901112299", name="Sardor")
    order = await _order(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        client_id=buyer.id,
        order_number="#26-1-0034",
        total_tiyin=9_000_000,
    )
    cashier = await _staff_access(
        db_session,
        workshop_id=workshop_id,
        branch_id=branch_id,
        permission=Permission.MANAGE_FINANCE,
    )
    today = datetime.now(UTC).date().isoformat()

    for access, amount in ((cashier, 1_000_000), (owner_access, 2_000_000)):
        booked = await client.post(
            INCOME_URL,
            headers=_auth(access),
            json={
                "type": "order_payment",
                "order_id": str(order.id),
                "amount_tiyin": amount,
                "method": "cash",
                "received_on": today,
            },
        )
        assert booked.status_code == 201, booked.text

    listed = await client.get(
        f"{INCOME_URL}?date_from={today}&date_to={today}", headers=_auth(owner_access)
    )
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len(rows) == 2
    assert {row["recorded_by_name"] for row in rows} == {"Finance Staff", "Workshop Owner"}

    cashier_id = next(
        row["recorded_by_user_id"] for row in rows if row["recorded_by_name"] == "Finance Staff"
    )
    filtered = await client.get(
        f"{INCOME_URL}?date_from={today}&date_to={today}&recorded_by_user_id={cashier_id}",
        headers=_auth(owner_access),
    )
    assert filtered.status_code == 200, filtered.text
    assert [row["amount_tiyin"] for row in filtered.json()] == [1_000_000]
    assert owner_id is not None
