"""Order numbers (`482917`) — how they are minted, displayed and searched."""

import re
import uuid
from typing import Any

import pytest
from app.core.errors import APIError
from app.core.order_number import (
    NUMBER_SIGN,
    THIN_SPACE,
    format_order_number,
    normalize_order_number_query,
)
from app.models.enums import AuthenticatedPrincipalType, Currency, OrderStatus
from app.modules.access.api import create_session
from app.modules.access.contracts import Client
from app.modules.sales import service as sales_service
from app.modules.sales.contracts import Order
from app.modules.sales.service import _insert_order, _random_order_number
from app.modules.workshop.contracts import Branch
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_workshop_with_owner

GENERATED = re.compile(r"^[1-9]\d{5}$")


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _buyer(db: AsyncSession) -> Client:
    buyer = Client(phone=f"+99890{uuid.uuid4().int % 10**7:07d}", name="Dilshod")
    db.add(buyer)
    await db.flush()
    return buyer


def _new_order(*, number: str, branch: Branch, client_id: uuid.UUID) -> Order:
    """A minimal order — only its number matters to these tests."""
    fields: dict[str, Any] = {
        "order_number": number,
        "client_id": client_id,
        "workshop_id": branch.workshop_id,
        "branch_id": branch.id,
        "cutting_result_id": uuid.uuid4(),
        "status": OrderStatus.NEW,
        "version": 1,
        "contact_name": "Dilshod",
        "contact_phone": "+998901112233",
        "subtotal_cutting_tiyin": 0,
        "subtotal_materials_tiyin": 0,
        "subtotal_edge_banding_tiyin": 0,
        "discount_tiyin": 0,
        "surcharge_tiyin": 0,
        "total_tiyin": 0,
        "currency": Currency.UZS,
    }
    return Order(**fields)


async def _order(db: AsyncSession, *, number: str, branch: Branch, client_id: uuid.UUID) -> Order:
    order = _new_order(number=number, branch=branch, client_id=client_id)
    db.add(order)
    await db.flush()
    return order


def test_generated_numbers_are_six_digits_with_no_leading_zero() -> None:
    """The number is dictated over the phone and typed on a numeric keypad."""
    drawn = [_random_order_number() for _ in range(2000)]
    assert all(GENERATED.match(number) for number in drawn)
    assert all(100_000 <= int(number) <= 999_999 for number in drawn)
    # 2000 draws out of 900 000 landing on a handful of values would mean a
    # broken source, not bad luck.
    assert len(set(drawn)) > 1900


async def test_insert_redraws_the_number_when_the_first_draw_is_taken(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The retry on `uq_orders_order_number` IS the collision strategy."""
    _, branch, _ = await seed_workshop_with_owner(db_session)
    buyer = await _buyer(db_session)
    await _order(db_session, number="482917", branch=branch, client_id=buyer.id)

    draws = iter(["482917", "555111"])
    monkeypatch.setattr(sales_service, "_random_order_number", lambda: next(draws))
    order = _new_order(number="482917", branch=branch, client_id=buyer.id)
    await _insert_order(db_session, order)

    assert order.order_number == "555111"
    numbers = (await db_session.scalars(select(Order.order_number))).all()
    assert sorted(numbers) == ["482917", "555111"]


async def test_insert_gives_up_rather_than_reusing_a_number(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Five taken draws in a row is an error, never a duplicated handle."""
    _, branch, _ = await seed_workshop_with_owner(db_session)
    buyer = await _buyer(db_session)
    await _order(db_session, number="482917", branch=branch, client_id=buyer.id)

    monkeypatch.setattr(sales_service, "_random_order_number", lambda: "482917")
    order = _new_order(number="482917", branch=branch, client_id=buyer.id)
    with pytest.raises(APIError) as raised:
        await _insert_order(db_session, order)
    assert raised.value.code == "order_number_unavailable"

    # The caller's transaction survived the failed attempts.
    assert await db_session.scalar(select(Order.order_number)) == "482917"


def test_display_groups_the_digits_and_leaves_legacy_numbers_alone() -> None:
    # One separator rule: a thin space after the sign as well as between the
    # groups, so the backend and `formatOrderNumber` on the web agree byte for byte.
    assert format_order_number("482917") == f"{NUMBER_SIGN}{THIN_SPACE}482{THIN_SPACE}917"
    assert " " not in format_order_number("482917")
    # Widening to seven digits must not move the grouping: it counts from the right.
    assert (
        format_order_number("4829175")
        == f"{NUMBER_SIGN}{THIN_SPACE}4{THIN_SPACE}829{THIN_SPACE}175"
    )
    assert format_order_number("#26-14-0003") == "#26-14-0003"
    assert format_order_number("ORD-2026-000123") == "ORD-2026-000123"


def test_search_normalisation_strips_what_a_client_dictates() -> None:
    typed_forms = (
        format_order_number("482917"),
        "482 917",
        "482917",
        "#482917",
        " 482 917 ",
    )
    for typed in typed_forms:
        assert normalize_order_number_query(typed) == "482917", typed
    # A legacy number keeps enough of itself to match on the raw text too.
    assert normalize_order_number_query("#26-14-0003") == "26-14-0003"


async def test_order_search_finds_both_number_eras(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """As displayed, as stored, and every legacy shape it ever printed."""
    _, branch, owner = await seed_workshop_with_owner(db_session)
    owner.password_reset_required = False
    buyer = await _buyer(db_session)
    await _order(db_session, number="ORD-2026-000015", branch=branch, client_id=buyer.id)
    await _order(db_session, number="482917", branch=branch, client_id=buyer.id)
    await _order(db_session, number="#26-1-0003", branch=branch, client_id=buyer.id)
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )

    async def _search(term: str) -> list[str]:
        response = await client.get(
            "/api/v1/workshop/orders",
            headers=_auth(tokens.access_token),
            params={"search": term},
        )
        assert response.status_code == 200, response.text
        return [row["order_number"] for row in response.json()]

    assert await _search("2026-000015") == ["ORD-2026-000015"]
    assert await _search("#26-1-0003") == ["#26-1-0003"]
    for typed in ("482917", "482 917", format_order_number("482917")):
        assert await _search(typed) == ["482917"], typed


async def test_client_order_search_normalises_the_same_way(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The client reads the number off their own screen and types it back."""
    _, branch, _ = await seed_workshop_with_owner(db_session)
    buyer = await _buyer(db_session)
    await _order(db_session, number="482917", branch=branch, client_id=buyer.id)
    await _order(db_session, number="311204", branch=branch, client_id=buyer.id)
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=buyer.id,
    )

    found = await client.get(
        "/api/v1/client/orders",
        headers=_auth(tokens.access_token),
        params={"search": format_order_number("482917")},
    )
    assert found.status_code == 200, found.text
    assert [row["order_number"] for row in found.json()] == ["482917"]


async def test_created_branches_get_distinct_platform_wide_numbers(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, seeded, owner = await seed_workshop_with_owner(db_session)
    owner.password_reset_required = False
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    payload = {
        "name": "Chilonzor",
        "address": "Tashkent, Chilonzor",
        "phone": "+998901234599",
    }

    first = await client.post(
        "/api/v1/workshop/branches", headers=_auth(tokens.access_token), json=payload
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        "/api/v1/workshop/branches",
        headers=_auth(tokens.access_token),
        json={**payload, "name": "Yakkasaroy"},
    )
    assert second.status_code == 201, second.text

    assert first.json()["branch_no"] == seeded.branch_no + 1
    assert second.json()["branch_no"] == seeded.branch_no + 2


async def test_branch_no_cannot_be_patched(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """It addresses the branch in every printed QR (`/w/{code}/{branch_no}`)."""
    _, branch, owner = await seed_workshop_with_owner(db_session)
    owner.password_reset_required = False
    original = branch.branch_no
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )

    patched = await client.patch(
        f"/api/v1/workshop/branches/{branch.id}",
        headers=_auth(tokens.access_token),
        json={"name": "Renamed", "branch_no": 999},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["branch_no"] == original
    stored = await db_session.scalar(select(Branch.branch_no).where(Branch.id == branch.id))
    assert stored == original
