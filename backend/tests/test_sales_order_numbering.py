"""Order numbers (`#26-14-0003`) and the branch numbers they are built from."""

import uuid
from datetime import UTC, datetime

from app.models.enums import AuthenticatedPrincipalType, Currency, OrderStatus
from app.modules.access.api import create_session
from app.modules.access.contracts import Client
from app.modules.sales.contracts import Order
from app.modules.sales.service import _next_order_number
from app.modules.workshop.contracts import Branch
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_workshop_with_owner


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _buyer(db: AsyncSession) -> Client:
    buyer = Client(phone=f"+99890{uuid.uuid4().int % 10**7:07d}", name="Dilshod")
    db.add(buyer)
    await db.flush()
    return buyer


async def _order(db: AsyncSession, *, number: str, branch: Branch, client_id: uuid.UUID) -> Order:
    """A minimal persisted order — only its number matters to these tests."""
    order = Order(
        order_number=number,
        client_id=client_id,
        workshop_id=branch.workshop_id,
        branch_id=branch.id,
        cutting_result_id=uuid.uuid4(),
        status=OrderStatus.NEW,
        version=1,
        contact_name="Dilshod",
        contact_phone="+998901112233",
        subtotal_cutting_tiyin=0,
        subtotal_materials_tiyin=0,
        subtotal_edge_banding_tiyin=0,
        discount_tiyin=0,
        surcharge_tiyin=0,
        total_tiyin=0,
        currency=Currency.UZS,
    )
    db.add(order)
    await db.flush()
    return order


async def _branch(db: AsyncSession, *, workshop_id: uuid.UUID, branch_no: int) -> Branch:
    branch = Branch(
        workshop_id=workshop_id,
        branch_no=branch_no,
        name=f"Branch {branch_no}",
        address="Tashkent",
        phone="+998901111111",
    )
    db.add(branch)
    await db.flush()
    return branch


async def test_sequence_counts_per_branch_and_per_year(db_session: AsyncSession) -> None:
    workshop, first, _ = await seed_workshop_with_owner(db_session)
    fourteen = await _branch(db_session, workshop_id=workshop.id, branch_no=14)
    buyer = await _buyer(db_session)
    now = datetime(2026, 3, 1, tzinfo=UTC)

    for expected in ("#26-14-0001", "#26-14-0002", "#26-14-0003"):
        number = await _next_order_number(db_session, now, fourteen.branch_no)
        assert number == expected
        await _order(db_session, number=number, branch=fourteen, client_id=buyer.id)

    # The year is in the number, so the sequence restarts with it.
    assert (
        await _next_order_number(db_session, datetime(2027, 1, 4, tzinfo=UTC), fourteen.branch_no)
        == "#27-14-0001"
    )
    # The workshop's other branch counts from its own 1 and never collides.
    assert await _next_order_number(db_session, now, first.branch_no) == "#26-1-0001"


async def test_branch_1_is_not_counted_into_branch_14(db_session: AsyncSession) -> None:
    """The trailing dash keeps `#26-1-` from matching `#26-14-0003`."""
    workshop, one, _ = await seed_workshop_with_owner(db_session)
    fourteen = await _branch(db_session, workshop_id=workshop.id, branch_no=14)
    buyer = await _buyer(db_session)
    now = datetime(2026, 3, 1, tzinfo=UTC)
    assert one.branch_no == 1

    for number in ("#26-14-0001", "#26-14-0002", "#26-14-0003"):
        await _order(db_session, number=number, branch=fourteen, client_id=buyer.id)

    assert await _next_order_number(db_session, now, one.branch_no) == "#26-1-0001"
    await _order(db_session, number="#26-1-0001", branch=one, client_id=buyer.id)
    assert await _next_order_number(db_session, now, fourteen.branch_no) == "#26-14-0004"


async def test_legacy_numbers_do_not_shift_the_new_sequence(db_session: AsyncSession) -> None:
    """`ORD-2026-…` orders keep their numbers and stay out of the new count."""
    _, branch, _ = await seed_workshop_with_owner(db_session)
    buyer = await _buyer(db_session)
    for number in ("ORD-2026-000015", "ORD-2026-000016"):
        await _order(db_session, number=number, branch=branch, client_id=buyer.id)

    now = datetime(2026, 3, 1, tzinfo=UTC)
    assert (
        await _next_order_number(db_session, now, branch.branch_no)
        == f"#26-{branch.branch_no}-0001"
    )


async def test_order_search_finds_both_number_eras(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, branch, owner = await seed_workshop_with_owner(db_session)
    owner.password_reset_required = False
    buyer = await _buyer(db_session)
    current_number = f"#26-{branch.branch_no}-0001"
    await _order(db_session, number="ORD-2026-000015", branch=branch, client_id=buyer.id)
    await _order(db_session, number=current_number, branch=branch, client_id=buyer.id)
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )

    legacy = await client.get(
        "/api/v1/workshop/orders",
        headers=_auth(tokens.access_token),
        params={"search": "2026-000015"},
    )
    assert legacy.status_code == 200, legacy.text
    assert [row["order_number"] for row in legacy.json()] == ["ORD-2026-000015"]

    current = await client.get(
        "/api/v1/workshop/orders",
        headers=_auth(tokens.access_token),
        params={"search": current_number[:-4]},
    )
    assert current.status_code == 200, current.text
    assert [row["order_number"] for row in current.json()] == [current_number]


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
    """It is baked into every order number the branch has ever printed."""
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
