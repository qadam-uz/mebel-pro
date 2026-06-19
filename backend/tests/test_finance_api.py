from app.models.enums import AuthenticatedPrincipalType
from app.modules.access.api import create_session
from app.modules.support.api import InMemoryFileStorage, file_storage
from app.modules.support.contracts import ActionLog, StatusChangeLog
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_platform_user, seed_workshop_with_owner


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _owner_access_token(db_session: AsyncSession) -> str:
    _, _, owner = await seed_workshop_with_owner(db_session)
    owner.password_reset_required = False
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token


async def test_finance_ledger_records_updates_voids_and_reports(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    storage = InMemoryFileStorage()
    from app.main import app

    app.dependency_overrides[file_storage] = lambda: storage
    access_token = await _owner_access_token(db_session)
    receipt = await client.post(
        "/api/v1/files",
        headers=_auth(access_token),
        files={"upload": ("finance-receipt.pdf", b"finance-receipt", "application/pdf")},
    )

    income = await client.post(
        "/api/v1/workshop/finance/income",
        headers=_auth(access_token),
        json={
            "type": "other",
            "amount_tiyin": 100_000,
            "method": "cash",
            "received_on": "2026-06-07",
            "note": "Counter payment",
            "receipt_file_id": receipt.json()["id"],
        },
    )
    expense = await client.post(
        "/api/v1/workshop/finance/expenses",
        headers=_auth(access_token),
        json={
            "category": "rent",
            "amount_tiyin": 30_000,
            "incurred_on": "2026-06-07",
            "description": "June rent",
            "vendor": "Landlord",
        },
    )
    updated_income = await client.patch(
        f"/api/v1/workshop/finance/income/{income.json()['id']}",
        headers=_auth(access_token),
        json={"amount_tiyin": 120_000, "note": "Counter payment corrected"},
    )
    voided_expense = await client.post(
        f"/api/v1/workshop/finance/expenses/{expense.json()['id']}/void",
        headers=_auth(access_token),
        json={"reason": "Duplicate entry"},
    )
    salary_expense = await client.post(
        "/api/v1/workshop/finance/expenses",
        headers=_auth(access_token),
        json={
            "category": "salary",
            "amount_tiyin": 40_000,
            "incurred_on": "2026-06-07",
            "description": "Manual salary booking",
            "vendor": "Worker",
        },
    )
    summary = await client.get(
        "/api/v1/workshop/finance/summary?date_from=2026-06-01&date_to=2026-06-30",
        headers=_auth(access_token),
    )
    incomes = await client.get(
        "/api/v1/workshop/finance/income?date_from=2026-06-01&date_to=2026-06-30",
        headers=_auth(access_token),
    )
    expenses = await client.get(
        "/api/v1/workshop/finance/expenses?date_from=2026-06-01&date_to=2026-06-30",
        headers=_auth(access_token),
    )
    owner_receipt = await client.get(
        f"/api/v1/files/{receipt.json()['id']}",
        headers=_auth(access_token),
    )
    filtered_incomes = await client.get(
        "/api/v1/workshop/finance/income"
        "?date_from=2026-06-01&date_to=2026-06-30"
        "&type=other&status=recorded&min_amount_tiyin=110000",
        headers=_auth(access_token),
    )
    filtered_expenses = await client.get(
        "/api/v1/workshop/finance/expenses"
        "?date_from=2026-06-01&date_to=2026-06-30"
        "&category=salary&status=recorded&max_amount_tiyin=40000",
        headers=_auth(access_token),
    )
    invalid_amount_range = await client.get(
        "/api/v1/workshop/finance/income"
        "?date_from=2026-06-01&date_to=2026-06-30"
        "&min_amount_tiyin=200000&max_amount_tiyin=100000",
        headers=_auth(access_token),
    )
    future_income = await client.post(
        "/api/v1/workshop/finance/income",
        headers=_auth(access_token),
        json={
            "type": "other",
            "amount_tiyin": 100_000,
            "method": "cash",
            "received_on": "2999-01-01",
        },
    )
    future_expense_update = await client.patch(
        f"/api/v1/workshop/finance/expenses/{salary_expense.json()['id']}",
        headers=_auth(access_token),
        json={"incurred_on": "2999-01-01"},
    )
    production = await client.get(
        "/api/v1/workshop/finance/production?date_from=2026-06-01&date_to=2026-06-30",
        headers=_auth(access_token),
    )
    action_count = await db_session.scalar(
        select(func.count()).select_from(ActionLog).where(ActionLog.action.like("finance.%"))
    )
    status_count = await db_session.scalar(
        select(func.count())
        .select_from(StatusChangeLog)
        .where(StatusChangeLog.entity_type == "expense")
    )

    assert income.status_code == 201
    assert income.json()["status"] == "recorded"
    assert income.json()["receipt_file_id"] == receipt.json()["id"]
    assert expense.status_code == 201
    assert updated_income.status_code == 200
    assert updated_income.json()["amount_tiyin"] == 120_000
    assert voided_expense.status_code == 200
    assert voided_expense.json()["status"] == "voided"
    assert salary_expense.status_code == 201
    assert summary.status_code == 200
    assert summary.json()["income_tiyin"] == 120_000
    assert summary.json()["expense_tiyin"] == 40_000
    assert summary.json()["net_tiyin"] == 80_000
    assert summary.json()["income_by_type"]["other"] == 120_000
    assert summary.json()["income_by_type"]["order_payment"] == 0
    assert summary.json()["expense_by_category"]["rent"] == 0
    assert summary.json()["expense_by_category"]["salary"] == 40_000
    assert summary.json()["salary_expense_tiyin"] == 40_000
    assert len(summary.json()["daily_income"]) == 30
    assert sum(row["income_tiyin"] for row in summary.json()["daily_income"]) == 120_000
    assert summary.json()["daily_income"][6] == {
        "day": "2026-06-07",
        "income_tiyin": 120_000,
    }
    assert incomes.status_code == 200
    assert len(incomes.json()) == 1
    assert expenses.status_code == 200
    assert {row["status"] for row in expenses.json()} == {"recorded", "voided"}
    assert owner_receipt.status_code == 200
    assert owner_receipt.content == b"finance-receipt"
    assert filtered_incomes.status_code == 200
    assert [row["id"] for row in filtered_incomes.json()] == [updated_income.json()["id"]]
    assert filtered_expenses.status_code == 200
    assert [row["id"] for row in filtered_expenses.json()] == [salary_expense.json()["id"]]
    assert invalid_amount_range.status_code == 400
    assert invalid_amount_range.json()["code"] == "invalid_amount_range"
    assert future_income.status_code == 400
    assert future_income.json()["code"] == "future_date_not_allowed"
    assert future_expense_update.status_code == 400
    assert future_expense_update.json()["code"] == "future_date_not_allowed"
    assert production.status_code == 200
    assert production.json()["rows"] == []
    assert action_count == 5
    assert status_count == 1


async def test_finance_routes_reject_non_workshop_principals(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform = await seed_platform_user(
        db_session,
        login="finance-platform",
        password="Admin123",
        password_reset_required=False,
    )
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        principal_id=platform.id,
    )

    response = await client.get(
        "/api/v1/workshop/finance/summary?date_from=2026-06-01&date_to=2026-06-30",
        headers=_auth(tokens.access_token),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
