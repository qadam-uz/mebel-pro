"""Integration tests for the finance module — income, expenses, settlement
guards, void semantics, and the worker-production + finance reports."""

from datetime import UTC, datetime, timedelta

from app.models.enums import Permission, PrincipalType
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_orders import (
    AuthFactory,
    World,
    _approve,
    _build_world,
    _make_draft_with_result,
    _place,
    _staff,
)

F = "/api/v1/workshop/finance"
W = "/api/v1/workshop"
C = "/api/v1/c"

_TODAY = datetime.now(UTC).date().isoformat()
_FUTURE = (datetime.now(UTC).date() + timedelta(days=2)).isoformat()


async def _placed_order(client: AsyncClient, db: AsyncSession, world: World) -> tuple[str, int]:
    draft_id = await _make_draft_with_result(client, db, world, world.client_headers)
    r = await _place(client, world, draft_id)
    assert r.status_code == 201, r.text
    return r.json()["id"], r.json()["price"]["total_tiyin"]


# --- income -----------------------------------------------------------------


async def test_record_order_payment_and_settlement(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    order_id, total = await _placed_order(client, db_session, world)

    r = await client.post(
        f"{F}/income",
        headers=world.owner_headers,
        json={
            "type": "order_payment",
            "order_id": order_id,
            "amount_tiyin": total // 2,
            "method": "cash",
            "received_on": _TODAY,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "recorded"

    # workshop settlement summary reflects the payment at any status
    r = await client.get(f"{W}/orders/{order_id}", headers=world.owner_headers)
    settlement = r.json()["settlement"]
    assert settlement["recorded_tiyin"] == total // 2
    assert settlement["balance_tiyin"] == total - total // 2


async def test_income_cannot_exceed_order_total(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    order_id, total = await _placed_order(client, db_session, world)

    r = await client.post(
        f"{F}/income",
        headers=world.owner_headers,
        json={
            "type": "order_payment",
            "order_id": order_id,
            "amount_tiyin": total + 1,
            "method": "cash",
            "received_on": _TODAY,
        },
    )
    assert r.status_code == 409 and r.json()["code"] == "payment_exceeds_total"


async def test_income_running_sum_guard(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    order_id, total = await _placed_order(client, db_session, world)
    body = {
        "type": "order_payment",
        "order_id": order_id,
        "amount_tiyin": total,
        "method": "cash",
        "received_on": _TODAY,
    }
    r = await client.post(f"{F}/income", headers=world.owner_headers, json=body)
    assert r.status_code == 201
    # a second payment, even of 1 tiyin, exceeds the total
    r = await client.post(
        f"{F}/income", headers=world.owner_headers, json={**body, "amount_tiyin": 1}
    )
    assert r.status_code == 409 and r.json()["code"] == "payment_exceeds_total"


async def test_order_payment_requires_order_id(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    r = await client.post(
        f"{F}/income",
        headers=world.owner_headers,
        json={
            "type": "order_payment",
            "amount_tiyin": 100,
            "method": "cash",
            "received_on": _TODAY,
        },
    )
    assert r.status_code == 400 and r.json()["code"] == "order_required"


async def test_income_future_date_rejected(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    r = await client.post(
        f"{F}/income",
        headers=world.owner_headers,
        json={"type": "other", "amount_tiyin": 100, "method": "cash", "received_on": _FUTURE},
    )
    assert r.status_code == 400 and r.json()["code"] == "date_in_future"


async def test_void_income_excludes_from_settlement_and_reports(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    order_id, total = await _placed_order(client, db_session, world)
    r = await client.post(
        f"{F}/income",
        headers=world.owner_headers,
        json={
            "type": "order_payment",
            "order_id": order_id,
            "amount_tiyin": total,
            "method": "bank_transfer",
            "received_on": _TODAY,
        },
    )
    income_id = r.json()["id"]

    # void requires a reason
    r = await client.post(f"{F}/income/{income_id}/void", headers=world.owner_headers, json={})
    assert r.status_code == 422  # missing reason -> validation

    r = await client.post(
        f"{F}/income/{income_id}/void",
        headers=world.owner_headers,
        json={"reason": "client disputed"},
    )
    assert r.status_code == 200 and r.json()["status"] == "voided"

    # settlement no longer counts it
    r = await client.get(f"{W}/orders/{order_id}", headers=world.owner_headers)
    assert r.json()["settlement"]["recorded_tiyin"] == 0

    # finance report excludes the voided income
    r = await client.get(
        f"{F}/report",
        headers=world.owner_headers,
        params={"period_start": _TODAY, "period_end": _TODAY},
    )
    assert r.json()["income_total_tiyin"] == 0


# --- expenses ---------------------------------------------------------------


async def test_record_expense_and_report(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    r = await client.post(
        f"{F}/expenses",
        headers=world.owner_headers,
        json={
            "category": "rent",
            "amount_tiyin": 5_000_000,
            "incurred_on": _TODAY,
            "description": "Monthly rent",
            "branch_id": str(world.branch.id),
        },
    )
    assert r.status_code == 201, r.text

    r = await client.post(
        f"{F}/expenses",
        headers=world.owner_headers,
        json={
            "category": "salary",
            "amount_tiyin": 3_000_000,
            "incurred_on": _TODAY,
            "description": "Asror salary",
        },
    )
    assert r.status_code == 201

    r = await client.get(
        f"{F}/report",
        headers=world.owner_headers,
        params={"period_start": _TODAY, "period_end": _TODAY},
    )
    body = r.json()
    assert body["expense_total_tiyin"] == 8_000_000
    assert body["expenses_by_category"]["rent"] == 5_000_000
    assert body["expenses_by_category"]["salary"] == 3_000_000
    assert body["net_tiyin"] == -8_000_000


async def test_expense_description_required(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    r = await client.post(
        f"{F}/expenses",
        headers=world.owner_headers,
        json={"category": "other", "amount_tiyin": 100, "incurred_on": _TODAY, "description": ""},
    )
    assert r.status_code == 422  # min_length on description


async def test_void_expense_excluded_from_report(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    r = await client.post(
        f"{F}/expenses",
        headers=world.owner_headers,
        json={
            "category": "supplies",
            "amount_tiyin": 1000,
            "incurred_on": _TODAY,
            "description": "glue",
        },
    )
    expense_id = r.json()["id"]
    r = await client.post(
        f"{F}/expenses/{expense_id}/void",
        headers=world.owner_headers,
        json={"reason": "double-entered"},
    )
    assert r.status_code == 200
    r = await client.get(
        f"{F}/report",
        headers=world.owner_headers,
        params={"period_start": _TODAY, "period_end": _TODAY},
    )
    assert r.json()["expense_total_tiyin"] == 0


# --- worker production report -----------------------------------------------


async def test_worker_production_report_sums_from_stamps(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers, sheet_on_hand=100, edge_on_hand=1000)
    worker = await _staff(
        db_session,
        world,
        login="cutter",
        perms=[Permission.PROCESS_PRODUCTION],
        home_branch_id=world.branch.id,
    )
    draft_id = await _make_draft_with_result(
        client, db_session, world, world.client_headers, banded=True
    )
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]
    await _approve(client, world, order_id)
    await client.post(
        f"{W}/orders/{order_id}/assign",
        headers=world.owner_headers,
        json={"cutter_user_id": str(worker.id), "edger_user_id": str(worker.id)},
    )
    worker_headers = await auth_headers(PrincipalType.WORKSHOP_USER, worker.id)
    await client.post(f"{W}/orders/{order_id}/cutting-done", headers=worker_headers, json={})
    await client.post(f"{W}/orders/{order_id}/banding-done", headers=worker_headers, json={})

    r = await client.get(
        f"{F}/production",
        headers=world.owner_headers,
        params={"period_start": _TODAY, "period_end": _TODAY},
    )
    rows = r.json()
    mine = [row for row in rows if row["user_id"] == str(worker.id)]
    assert len(mine) == 1
    assert mine[0]["sheets_cut"] > 0
    assert mine[0]["cut_count"] > 0
    assert mine[0]["orders_banded"] == 1
    assert mine[0]["metres_by_thickness"].get("2.0", 0) > 0


async def test_reverted_work_excluded_from_production(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    draft_id = await _make_draft_with_result(client, db_session, world, world.client_headers)
    r = await _place(client, world, draft_id)
    order_id = r.json()["id"]
    await _approve(client, world, order_id)
    await client.post(
        f"{W}/orders/{order_id}/assign",
        headers=world.owner_headers,
        json={"cutter_user_id": str(world.owner.id)},
    )
    await client.post(f"{W}/orders/{order_id}/cutting-done", headers=world.owner_headers, json={})
    # revert clears the cut stamp
    await client.post(
        f"{W}/orders/{order_id}/revert", headers=world.owner_headers, json={"reason": "redo"}
    )

    r = await client.get(
        f"{F}/production",
        headers=world.owner_headers,
        params={"period_start": _TODAY, "period_end": _TODAY},
    )
    rows = [row for row in r.json() if row["user_id"] == str(world.owner.id)]
    # the owner's cut credit is gone (stamp cleared)
    assert rows == [] or rows[0]["sheets_cut"] == 0


# --- finance report income split --------------------------------------------


async def test_finance_report_income_split(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    order_id, total = await _placed_order(client, db_session, world)
    await client.post(
        f"{F}/income",
        headers=world.owner_headers,
        json={
            "type": "order_payment",
            "order_id": order_id,
            "amount_tiyin": 100,
            "method": "cash",
            "received_on": _TODAY,
        },
    )
    await client.post(
        f"{F}/income",
        headers=world.owner_headers,
        json={
            "type": "other",
            "amount_tiyin": 250,
            "method": "other",
            "received_on": _TODAY,
            "branch_id": str(world.branch.id),
        },
    )
    r = await client.get(
        f"{F}/report",
        headers=world.owner_headers,
        params={"period_start": _TODAY, "period_end": _TODAY},
    )
    body = r.json()
    assert body["income_order_payment_tiyin"] == 100
    assert body["income_other_tiyin"] == 250
    assert body["income_total_tiyin"] == 350
    assert body["net_tiyin"] == 350


# --- access -----------------------------------------------------------------


async def test_non_finance_staff_cannot_read_reports(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    staff = await _staff(
        db_session,
        world,
        login="orders_only",
        perms=[Permission.MANAGE_ORDERS],
        home_branch_id=world.branch.id,
    )
    headers = await auth_headers(PrincipalType.WORKSHOP_USER, staff.id)
    r = await client.get(
        f"{F}/report",
        headers=headers,
        params={"period_start": _TODAY, "period_end": _TODAY},
    )
    assert r.status_code == 403


async def test_view_finance_reports_can_read_but_not_mutate(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    world = await _build_world(db_session, auth_headers)
    staff = await _staff(
        db_session,
        world,
        login="viewer",
        perms=[Permission.VIEW_FINANCE_REPORTS],
        home_branch_id=world.branch.id,
    )
    headers = await auth_headers(PrincipalType.WORKSHOP_USER, staff.id)
    # can read
    r = await client.get(
        f"{F}/report", headers=headers, params={"period_start": _TODAY, "period_end": _TODAY}
    )
    assert r.status_code == 200
    # cannot record an expense (needs manage_finance)
    r = await client.post(
        f"{F}/expenses",
        headers=headers,
        json={
            "category": "other",
            "amount_tiyin": 100,
            "incurred_on": _TODAY,
            "description": "x",
            "branch_id": str(world.branch.id),
        },
    )
    assert r.status_code == 403
