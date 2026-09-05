"""Workshop-scoped client entry: the link code, the resolve, the pin, the page.

The client app is something a workshop hands its own clients, so the surfaces
here are deliberately narrow: the public resolve says who the shop is and where
its counters are and nothing else, the pin is set only by a code that names the
workshop, and "my workshops" is derived from what the client actually did.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.enums import (
    AuthenticatedPrincipalType,
    BranchStatus,
    FileStorageStatus,
    WorkshopStatus,
)
from app.modules.access.api import create_session
from app.modules.access.contracts import Client
from app.modules.client_portal.contracts import ClientWorkshopEntry
from app.modules.cutting.contracts import CuttingDraft
from app.modules.sales.contracts import Order
from app.modules.support.api import FILE_CACHE_CONTROL, InMemoryFileStorage
from app.modules.support.contracts import ActionLog, File
from app.modules.support.files import file_storage
from app.modules.workshop.api import (
    PUBLIC_CODE_ALPHABET,
    PUBLIC_CODE_LENGTH,
    allocate_public_code,
    generate_public_code,
    next_branch_no,
    normalize_public_code,
)
from app.modules.workshop.contracts import Branch, Workshop
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_platform_user, seed_workshop_with_owner


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _client_token(
    db: AsyncSession,
    *,
    phone: str = "+998900000001",
    preferred_branch_id: uuid.UUID | None = None,
) -> tuple[Client, str]:
    row = Client(phone=phone, name="Client", preferred_branch_id=preferred_branch_id)
    db.add(row)
    await db.flush()
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.CLIENT,
        principal_id=row.id,
    )
    return row, tokens.access_token


async def _add_branch(
    db: AsyncSession,
    *,
    workshop: Workshop,
    name: str,
    status: BranchStatus = BranchStatus.ACTIVE,
    closed_reason: str | None = None,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
) -> Branch:
    branch = Branch(
        workshop_id=workshop.id,
        branch_no=await next_branch_no(db),
        name=name,
        address=f"Tashkent, {name}",
        phone="+998901111111",
        status=status,
        closed_reason=closed_reason,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(branch)
    await db.flush()
    return branch


def _aware(moment: datetime) -> datetime:
    """SQLite hands timestamps back without their zone; Postgres keeps it."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def _entries(db: AsyncSession, *, client_id: uuid.UUID) -> list[ClientWorkshopEntry]:
    rows = await db.scalars(
        select(ClientWorkshopEntry)
        .where(ClientWorkshopEntry.client_id == client_id)
        .order_by(ClientWorkshopEntry.last_entered_at)
    )
    return list(rows.all())


async def _seed_order(db: AsyncSession, *, client_row: Client, branch: Branch) -> Order:
    order = Order(
        order_number=f"ORD-{uuid.uuid4().hex[:10]}",
        client_id=client_row.id,
        workshop_id=branch.workshop_id,
        branch_id=branch.id,
        cutting_result_id=uuid.uuid4(),
        contact_name="Client",
        contact_phone=client_row.phone,
    )
    db.add(order)
    await db.flush()
    return order


# --- The code itself -------------------------------------------------------


def test_generated_codes_have_the_crockford_shape() -> None:
    codes = [generate_public_code() for _ in range(500)]

    for code in codes:
        assert len(code) == PUBLIC_CODE_LENGTH == 8
        assert set(code) <= set(PUBLIC_CODE_ALPHABET)
        # The four characters Crockford drops so a printed code survives being
        # read back by a person.
        assert not set(code) & set("ILOU")
    # 32^8 of space: 500 draws colliding would mean the draw is not random.
    assert len(set(codes)) == 500


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("abcd1234", "ABCD1234"),
        ("  abcd-1234 ", "ABCD1234"),
        ("ABCD_1234", "ABCD1234"),
        # Lookalikes a person types off a printed sheet fold to the character
        # the alphabet actually holds.
        ("IL0O2345", "11002345"),
        ("UUUU2345", "VVVV2345"),
    ],
)
def test_normalize_accepts_what_a_person_types(typed: str, expected: str) -> None:
    assert normalize_public_code(typed) == expected


@pytest.mark.parametrize("junk", ["", "ABC", "ABCD12345", "ABCD-12$4", "ABCD 12 3"])
def test_normalize_rejects_what_can_never_be_a_code(junk: str) -> None:
    assert normalize_public_code(junk) is None


async def test_workshops_are_born_with_distinct_codes(db_session: AsyncSession) -> None:
    first, _, _ = await seed_workshop_with_owner(db_session, login="code_a")
    second, _, _ = await seed_workshop_with_owner(db_session, login="code_b")

    assert first.public_code != second.public_code
    assert len(first.public_code) == PUBLIC_CODE_LENGTH


async def test_allocate_skips_a_code_another_workshop_already_holds(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workshop, _, _ = await seed_workshop_with_owner(db_session, login="code_c")
    draws = iter([workshop.public_code, "FREECODE"])
    monkeypatch.setattr(
        "app.modules.workshop.public_code.generate_public_code",
        lambda: next(draws),
    )

    assert await allocate_public_code(db_session) == "FREECODE"


async def test_provisioning_assigns_a_code(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_platform_user(
        db_session,
        login="provisioner",
        password="Admin123",
        password_reset_required=False,
    )
    login = await client.post(
        "/api/v1/auth/platform/login",
        json={"login": "provisioner", "password": "Admin123"},
    )

    provisioned = await client.post(
        "/api/v1/platform/workshops",
        headers=_auth(login.json()["access_token"]),
        json={
            "workshop": {"name": "Atlas Mebel"},
            "branch": {"name": "Main", "address": "Tashkent", "phone": "+998902020202"},
            "owner": {"login": "atlas-owner"},
        },
    )

    assert provisioned.status_code == 201
    code = await db_session.scalar(
        select(Workshop.public_code).where(
            Workshop.id == uuid.UUID(provisioned.json()["workshop"]["id"])
        )
    )
    assert code is not None
    assert len(code) == PUBLIC_CODE_LENGTH
    assert set(code) <= set(PUBLIC_CODE_ALPHABET)


# --- Public resolve --------------------------------------------------------

RESOLVE_KEYS = {
    "code",
    "workshop_name",
    "workshop_logo_file_id",
    "branches",
    "requested_branch_id",
    "branch_no_fallback",
}
RESOLVE_BRANCH_KEYS = {
    "id",
    "branch_no",
    "name",
    "address",
    "phone",
    "status",
    "closed_reason",
}


async def test_resolve_carries_identity_and_pickup_information_only(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    workshop, branch, _ = await seed_workshop_with_owner(db_session, login="resolve_owner")
    closed = await _add_branch(
        db_session,
        workshop=workshop,
        name="Chilonzor",
        status=BranchStatus.TEMPORARILY_CLOSED,
        closed_reason="Ta'mirlash",
    )
    await _add_branch(
        db_session,
        workshop=workshop,
        name="Sergeli",
        status=BranchStatus.INACTIVE,
    )

    # Unauthenticated on purpose: the landing runs before any login.
    response = await client.get(f"/api/v1/public/workshop-links/{workshop.public_code}")

    assert response.status_code == 200
    body = response.json()
    # The payload is a trust cue, not a storefront: asserting the exact key set
    # is what keeps a price, a catalog preview or a staff count from drifting in.
    assert set(body) == RESOLVE_KEYS
    assert body["workshop_name"] == "Demo Workshop"
    assert body["requested_branch_id"] is None
    assert body["branch_no_fallback"] is False
    assert [row["name"] for row in body["branches"]] == [closed.name, branch.name]
    for row in body["branches"]:
        assert set(row) == RESOLVE_BRANCH_KEYS
    # An `inactive` branch is not a counter a client can walk into.
    assert all(row["status"] != "inactive" for row in body["branches"])
    assert body["branches"][0]["closed_reason"] == "Ta'mirlash"


async def test_resolve_accepts_a_typed_code_in_any_case(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    workshop, _, _ = await seed_workshop_with_owner(db_session, login="typed_owner")

    response = await client.get(
        f"/api/v1/public/workshop-links/{workshop.public_code.lower()}",
    )

    assert response.status_code == 200
    assert response.json()["code"] == workshop.public_code


async def test_branch_link_resolves_straight_to_its_branch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    workshop, branch, _ = await seed_workshop_with_owner(db_session, login="branch_link_owner")
    other = await _add_branch(db_session, workshop=workshop, name="Chilonzor")

    response = await client.get(
        f"/api/v1/public/workshop-links/{workshop.public_code}",
        params={"branch_no": other.branch_no},
    )

    assert response.status_code == 200
    assert response.json()["requested_branch_id"] == str(other.id)
    assert response.json()["branch_no_fallback"] is False
    assert {row["id"] for row in response.json()["branches"]} == {str(branch.id), str(other.id)}


@pytest.mark.parametrize("branch_no", [4242, 0])
async def test_a_branch_link_that_no_longer_resolves_falls_back_to_the_workshop(
    client: AsyncClient,
    db_session: AsyncSession,
    branch_no: int,
) -> None:
    # A printed QR outlives branch reshuffles: a `branch_no` that is gone,
    # renumbered or now invisible must not turn the link into a dead one.
    workshop, branch, _ = await seed_workshop_with_owner(db_session, login=f"gone_{branch_no}")

    response = await client.get(
        f"/api/v1/public/workshop-links/{workshop.public_code}",
        params={"branch_no": branch_no},
    )

    assert response.status_code == 200
    assert response.json()["requested_branch_id"] is None
    # The flag is how the landing knows to show the choice step it was about
    # to skip rather than silently pinning something else.
    assert response.json()["branch_no_fallback"] is True
    assert [row["id"] for row in response.json()["branches"]] == [str(branch.id)]


async def test_a_branch_link_pointing_at_an_invisible_branch_falls_back(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    workshop, branch, _ = await seed_workshop_with_owner(db_session, login="retired_branch_owner")
    retired = await _add_branch(
        db_session,
        workshop=workshop,
        name="Sergeli",
        status=BranchStatus.INACTIVE,
    )

    response = await client.get(
        f"/api/v1/public/workshop-links/{workshop.public_code}",
        params={"branch_no": retired.branch_no},
    )

    assert response.status_code == 200
    assert response.json()["branch_no_fallback"] is True
    assert [row["id"] for row in response.json()["branches"]] == [str(branch.id)]


async def test_every_dead_link_cause_answers_the_same_404(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    blocked, _, _ = await seed_workshop_with_owner(db_session, login="blocked_owner")
    blocked.status = WorkshopStatus.BLOCKED
    branchless, only_branch, _ = await seed_workshop_with_owner(db_session, login="empty_owner")
    only_branch.status = BranchStatus.INACTIVE
    await db_session.flush()

    never_existed = await client.get("/api/v1/public/workshop-links/ZZZZZZZZ")
    malformed = await client.get("/api/v1/public/workshop-links/nope")
    blocked_link = await client.get(f"/api/v1/public/workshop-links/{blocked.public_code}")
    no_branches = await client.get(f"/api/v1/public/workshop-links/{branchless.public_code}")

    # One dead-link screen, one answer: which cause it was is not the client's
    # business, and telling a scraper apart from a scanner is not possible.
    for response in (never_existed, malformed, blocked_link, no_branches):
        assert response.status_code == 404
        assert response.json()["code"] == "workshop_link_not_found"


async def test_resolve_is_rate_limited_per_ip(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workshop, _, _ = await seed_workshop_with_owner(db_session, login="throttled_owner")
    monkeypatch.setattr("app.core.config.settings.PUBLIC_LINK_LOOKUPS_PER_IP", 2)

    first = await client.get(f"/api/v1/public/workshop-links/{workshop.public_code}")
    second = await client.get(f"/api/v1/public/workshop-links/{workshop.public_code}")
    third = await client.get(f"/api/v1/public/workshop-links/{workshop.public_code}")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["code"] == "workshop_link_rate_limited"


# --- The public logo -------------------------------------------------------


async def _attach_logo(
    db: AsyncSession,
    *,
    workshop: Workshop,
    storage: InMemoryFileStorage,
    content: bytes = b"logo-bytes",
) -> File:
    row = File(
        storage_key=f"uploads/{uuid.uuid4().hex}/logo.png",
        original_name="logo.png",
        content_type="image/png",
        size_bytes=len(content),
        storage_status=FileStorageStatus.STORED,
        entity_type="workshop",
        entity_id=workshop.id,
        uploaded_by_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        uploaded_by_id=workshop.owner_user_id,
    )
    db.add(row)
    await db.flush()
    workshop.logo_file_id = row.id
    await db.flush()
    storage.put(row.storage_key, content, "image/png")
    return row


def _use_storage() -> InMemoryFileStorage:
    from app.main import app

    storage = InMemoryFileStorage()
    app.dependency_overrides[file_storage] = lambda: storage
    return storage


async def test_public_logo_is_served_to_a_signed_out_scan(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The landing's trust cue works before there is a session."""
    storage = _use_storage()
    workshop, _, _ = await seed_workshop_with_owner(db_session, login="logo_owner")
    await _attach_logo(db_session, workshop=workshop, storage=storage)

    response = await client.get(f"/api/v1/public/workshop-links/{workshop.public_code}/logo")

    assert response.status_code == 200
    assert response.content == b"logo-bytes"
    assert response.headers["content-type"].startswith("image/png")
    # Same mechanics as the authenticated file route — a scanned QR should not
    # re-download the logo on every hop through the login round-trip.
    assert response.headers["cache-control"] == FILE_CACHE_CONTROL
    revalidated = await client.get(
        f"/api/v1/public/workshop-links/{workshop.public_code}/logo",
        headers={"If-None-Match": response.headers["etag"]},
    )
    assert revalidated.status_code == 304
    assert revalidated.content == b""


async def test_public_logo_answers_the_same_404_as_a_dead_link(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    storage = _use_storage()
    blocked, _, _ = await seed_workshop_with_owner(db_session, login="logo_blocked")
    await _attach_logo(db_session, workshop=blocked, storage=storage)
    blocked.status = WorkshopStatus.BLOCKED
    branchless, only_branch, _ = await seed_workshop_with_owner(db_session, login="logo_branchless")
    await _attach_logo(db_session, workshop=branchless, storage=storage)
    only_branch.status = BranchStatus.INACTIVE
    logoless, _, _ = await seed_workshop_with_owner(db_session, login="logo_none")
    await db_session.flush()

    responses = [
        await client.get("/api/v1/public/workshop-links/ZZZZZZZZ/logo"),
        await client.get("/api/v1/public/workshop-links/nope/logo"),
        await client.get(f"/api/v1/public/workshop-links/{blocked.public_code}/logo"),
        await client.get(f"/api/v1/public/workshop-links/{branchless.public_code}/logo"),
        # No logo is a dead end like any other: the landing falls back to the
        # monogram, and the answer says nothing about which cause it was.
        await client.get(f"/api/v1/public/workshop-links/{logoless.public_code}/logo"),
    ]

    for response in responses:
        assert response.status_code == 404
        assert response.json()["code"] == "workshop_link_not_found"


async def test_public_logo_shares_the_resolve_budget(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One landing, one budget — a scan makes both calls."""
    storage = _use_storage()
    workshop, _, _ = await seed_workshop_with_owner(db_session, login="logo_throttled")
    await _attach_logo(db_session, workshop=workshop, storage=storage)
    monkeypatch.setattr("app.core.config.settings.PUBLIC_LINK_LOOKUPS_PER_IP", 2)

    resolved = await client.get(f"/api/v1/public/workshop-links/{workshop.public_code}")
    logo = await client.get(f"/api/v1/public/workshop-links/{workshop.public_code}/logo")
    third = await client.get(f"/api/v1/public/workshop-links/{workshop.public_code}/logo")

    assert resolved.status_code == 200
    assert logo.status_code == 200
    # Two buckets would double what a walk of the code space is allowed.
    assert third.status_code == 429
    assert third.json()["code"] == "workshop_link_rate_limited"


async def test_public_logo_can_never_address_another_file(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The code is the capability; no other file is reachable through it.

    The route takes no file id at all, so the only thing it can serve is the
    workshop the code names — not another workshop's logo, and not a receipt
    that happens to live in the same bucket.
    """
    storage = _use_storage()
    workshop, _, owner = await seed_workshop_with_owner(db_session, login="logo_scoped")
    await _attach_logo(db_session, workshop=workshop, storage=storage, content=b"ours")
    other, _, _ = await seed_workshop_with_owner(db_session, login="logo_other")
    theirs = await _attach_logo(db_session, workshop=other, storage=storage, content=b"theirs")
    receipt = File(
        storage_key=f"uploads/{uuid.uuid4().hex}/receipt.pdf",
        original_name="receipt.pdf",
        content_type="application/pdf",
        size_bytes=7,
        storage_status=FileStorageStatus.STORED,
        entity_type="expense",
        entity_id=uuid.uuid4(),
        uploaded_by_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        uploaded_by_id=owner.id,
    )
    db_session.add(receipt)
    await db_session.flush()
    storage.put(receipt.storage_key, b"secret.", "application/pdf")

    ours = await client.get(f"/api/v1/public/workshop-links/{workshop.public_code}/logo")
    # A file id in the code slot is not a code, so it can never resolve.
    by_receipt_id = await client.get(f"/api/v1/public/workshop-links/{receipt.id}/logo")
    by_logo_id = await client.get(f"/api/v1/public/workshop-links/{theirs.id}/logo")

    assert ours.content == b"ours"
    assert by_receipt_id.status_code == 404
    assert by_receipt_id.json()["code"] == "workshop_link_not_found"
    assert by_logo_id.status_code == 404
    # And the unauthenticated surface stays exactly one route wide: the general
    # file route still refuses a caller with no session.
    unauthenticated = await client.get(f"/api/v1/files/{receipt.id}")
    assert unauthenticated.status_code == 401


# --- Applying the entry ----------------------------------------------------


async def test_entry_pins_the_branch_the_link_named(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    workshop, branch, _ = await seed_workshop_with_owner(db_session, login="entry_owner")
    client_row, token = await _client_token(db_session)

    response = await client.post(
        "/api/v1/client/entry",
        headers=_auth(token),
        json={"code": workshop.public_code.lower(), "branch_id": str(branch.id)},
    )

    assert response.status_code == 200
    assert response.json() == {
        "workshop_id": str(workshop.id),
        "workshop_name": workshop.name,
        "branch_id": str(branch.id),
        "branch_name": branch.name,
    }
    assert client_row.preferred_branch_id == branch.id
    audited = await db_session.scalar(
        select(func.count()).select_from(ActionLog).where(ActionLog.action == "client.entry.apply")
    )
    assert audited == 1
    # The relationship is stored, not only pinned — this is what keeps the
    # workshop on Ustaxonalarim after the pin moves elsewhere.
    entries = await _entries(db_session, client_id=client_row.id)
    assert [row.workshop_id for row in entries] == [workshop.id]


async def test_a_one_branch_workshop_link_pins_its_only_branch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """`/w/{code}` with nothing to choose between is as certain as a branch QR."""
    workshop, branch, _ = await seed_workshop_with_owner(db_session, login="single_branch")
    client_row, token = await _client_token(db_session)

    response = await client.post(
        "/api/v1/client/entry",
        headers=_auth(token),
        json={"code": workshop.public_code},
    )

    assert response.status_code == 200, response.text
    assert response.json()["branch_id"] == str(branch.id)
    assert client_row.preferred_branch_id == branch.id


async def test_a_multi_branch_workshop_link_records_the_entry_without_pinning(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Nothing may guess which counter the client stood at.

    The workshop still joins Ustaxonalarim — that is what the entry row is for
    — and the client is asked there which branch is theirs.
    """
    workshop, _, _ = await seed_workshop_with_owner(db_session, login="multi_branch")
    await _add_branch(db_session, workshop=workshop, name="Chilonzor")
    other, other_branch, _ = await seed_workshop_with_owner(db_session, login="multi_other")
    client_row, token = await _client_token(db_session, preferred_branch_id=other_branch.id)

    response = await client.post(
        "/api/v1/client/entry",
        headers=_auth(token),
        json={"code": workshop.public_code},
    )

    assert response.status_code == 200, response.text
    assert response.json()["branch_id"] is None
    assert response.json()["branch_name"] is None
    assert response.json()["workshop_id"] == str(workshop.id)
    # An existing pin is left exactly where it was, not cleared.
    assert client_row.preferred_branch_id == other_branch.id
    listed = await client.get("/api/v1/client/my-workshops", headers=_auth(token))
    assert {row["workshop_id"] for row in listed.json()} == {str(workshop.id), str(other.id)}


async def test_re_entering_stamps_the_same_row_instead_of_adding_one(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """One row per client per workshop — the table records relationships."""
    workshop, branch, _ = await seed_workshop_with_owner(db_session, login="restamp_owner")
    client_row, token = await _client_token(db_session)
    payload = {"code": workshop.public_code, "branch_id": str(branch.id)}

    first = await client.post("/api/v1/client/entry", headers=_auth(token), json=payload)
    assert first.status_code == 200
    (before,) = await _entries(db_session, client_id=client_row.id)
    # Age the row so "the stamp moved" is an assertion, not a coin flip on the
    # clock's resolution.
    before.last_entered_at = datetime.now(UTC) - timedelta(days=10)
    await db_session.flush()

    second = await client.post("/api/v1/client/entry", headers=_auth(token), json=payload)
    assert second.status_code == 200

    entries = await _entries(db_session, client_id=client_row.id)
    assert len(entries) == 1
    assert _aware(entries[0].last_entered_at) > datetime.now(UTC) - timedelta(minutes=1)


async def test_entry_is_idempotent_and_last_write_wins(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    first_workshop, first_branch, _ = await seed_workshop_with_owner(db_session, login="switch_a")
    second_workshop, second_branch, _ = await seed_workshop_with_owner(db_session, login="switch_b")
    client_row, token = await _client_token(db_session)

    again = None
    for _ in range(2):
        again = await client.post(
            "/api/v1/client/entry",
            headers=_auth(token),
            json={"code": first_workshop.public_code, "branch_id": str(first_branch.id)},
        )
    assert again is not None and again.status_code == 200
    assert client_row.preferred_branch_id == first_branch.id

    # Entering another workshop's door means walking through it — no confirm step.
    switched = await client.post(
        "/api/v1/client/entry",
        headers=_auth(token),
        json={"code": second_workshop.public_code, "branch_id": str(second_branch.id)},
    )

    assert switched.status_code == 200
    assert switched.json()["workshop_id"] == str(second_workshop.id)
    assert client_row.preferred_branch_id == second_branch.id


async def test_entry_refuses_a_branch_the_code_does_not_name(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    workshop, branch, _ = await seed_workshop_with_owner(db_session, login="cross_a")
    _, foreign_branch, _ = await seed_workshop_with_owner(db_session, login="cross_b")
    client_row, token = await _client_token(db_session, preferred_branch_id=branch.id)

    response = await client.post(
        "/api/v1/client/entry",
        headers=_auth(token),
        json={"code": workshop.public_code, "branch_id": str(foreign_branch.id)},
    )

    # The bare branch id is never trusted: the code is the capability that
    # names the workshop, so a branch outside it is simply not there.
    assert response.status_code == 404
    assert response.json()["code"] == "branch_not_found"
    assert client_row.preferred_branch_id == branch.id


async def test_entry_refuses_an_invisible_branch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    workshop, _, _ = await seed_workshop_with_owner(db_session, login="invisible_owner")
    retired = await _add_branch(
        db_session,
        workshop=workshop,
        name="Sergeli",
        status=BranchStatus.INACTIVE,
    )
    client_row, token = await _client_token(db_session)

    response = await client.post(
        "/api/v1/client/entry",
        headers=_auth(token),
        json={"code": workshop.public_code, "branch_id": str(retired.id)},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "branch_not_found"
    assert client_row.preferred_branch_id is None


async def test_entry_refuses_a_dead_code(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, branch, _ = await seed_workshop_with_owner(db_session, login="dead_code_owner")
    _, token = await _client_token(db_session)

    response = await client.post(
        "/api/v1/client/entry",
        headers=_auth(token),
        json={"code": "ZZZZZZZZ", "branch_id": str(branch.id)},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "workshop_link_not_found"


async def test_entry_requires_a_client_session(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    workshop, branch, owner = await seed_workshop_with_owner(db_session, login="staff_entry")
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )

    anonymous = await client.post(
        "/api/v1/client/entry",
        json={"code": workshop.public_code, "branch_id": str(branch.id)},
    )
    staff = await client.post(
        "/api/v1/client/entry",
        headers=_auth(tokens.access_token),
        json={"code": workshop.public_code, "branch_id": str(branch.id)},
    )

    assert anonymous.status_code == 401
    assert staff.status_code == 403


# --- Ustaxonalarim (my workshops) ------------------------------------------


async def test_my_workshops_is_empty_without_a_pin_or_history(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await seed_workshop_with_owner(db_session, login="unrelated_owner")
    _, token = await _client_token(db_session)

    response = await client.get("/api/v1/client/my-workshops", headers=_auth(token))

    # The platform-wide directory is gone: a client who never entered a door
    # sees no workshops at all, not every workshop on the platform.
    assert response.status_code == 200
    assert response.json() == []


async def test_my_workshops_lists_the_pinned_workshop_with_its_visible_branches(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    workshop, branch, _ = await seed_workshop_with_owner(db_session, login="pinned_owner")
    closed = await _add_branch(
        db_session,
        workshop=workshop,
        name="Chilonzor",
        status=BranchStatus.TEMPORARILY_CLOSED,
        closed_reason="Ta'mirlash",
    )
    await _add_branch(db_session, workshop=workshop, name="Sergeli", status=BranchStatus.INACTIVE)
    _, token = await _client_token(db_session, preferred_branch_id=branch.id)

    response = await client.get("/api/v1/client/my-workshops", headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["workshop_id"] == str(workshop.id)
    assert body[0]["is_pinned"] is True
    # The code travels so "Asosiy qilish" can re-pin through the same entry
    # endpoint a fresh scan uses.
    assert body[0]["public_code"] == workshop.public_code
    assert [row["name"] for row in body[0]["branches"]] == [closed.name, branch.name]
    assert [row["is_pinned"] for row in body[0]["branches"]] == [False, True]
    assert body[0]["branches"][0]["closed_reason"] == "Ta'mirlash"


async def test_my_workshops_derives_history_from_orders_and_drafts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    ordered, order_branch, _ = await seed_workshop_with_owner(db_session, login="history_order")
    drafted, draft_branch, _ = await seed_workshop_with_owner(db_session, login="history_draft")
    client_row, token = await _client_token(db_session)
    await _seed_order(db_session, client_row=client_row, branch=order_branch)
    db_session.add(
        CuttingDraft(
            client_id=client_row.id,
            preferred_branch_id=draft_branch.id,
            parts_snapshot=[],
        )
    )
    await db_session.flush()

    response = await client.get("/api/v1/client/my-workshops", headers=_auth(token))

    assert response.status_code == 200
    assert {row["workshop_id"] for row in response.json()} == {str(ordered.id), str(drafted.id)}
    # Nothing is pinned — history alone is a relationship, not a choice.
    assert all(row["is_pinned"] is False for row in response.json())


async def test_my_workshops_puts_the_pinned_workshop_first(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Names chosen so alphabetical order would put the pinned one last.
    history, history_branch, _ = await seed_workshop_with_owner(db_session, login="union_a")
    history.name = "Alfa Mebel"
    pinned, pinned_branch, _ = await seed_workshop_with_owner(db_session, login="union_b")
    pinned.name = "Zulfiya Mebel"
    await db_session.flush()
    client_row, token = await _client_token(db_session, preferred_branch_id=pinned_branch.id)
    await _seed_order(db_session, client_row=client_row, branch=history_branch)

    response = await client.get("/api/v1/client/my-workshops", headers=_auth(token))

    assert response.status_code == 200
    assert [row["name"] for row in response.json()] == ["Zulfiya Mebel", "Alfa Mebel"]
    assert [row["is_pinned"] for row in response.json()] == [True, False]


async def test_my_workshops_keeps_a_workshop_the_client_only_entered(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A scan with no drawing after it used to leave no trace at all.

    The entry row is the relationship: the workshop stays on the page with no
    pin and no history behind it.
    """
    workshop, _, _ = await seed_workshop_with_owner(db_session, login="entered_only")
    await _add_branch(db_session, workshop=workshop, name="Chilonzor")
    _, token = await _client_token(db_session)

    entered = await client.post(
        "/api/v1/client/entry",
        headers=_auth(token),
        json={"code": workshop.public_code},
    )
    assert entered.status_code == 200, entered.text
    listed = await client.get("/api/v1/client/my-workshops", headers=_auth(token))

    assert listed.status_code == 200
    body = listed.json()
    assert [row["workshop_id"] for row in body] == [str(workshop.id)]
    assert body[0]["is_pinned"] is False


async def test_my_workshops_orders_the_unpinned_by_most_recent_dealing(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Entry stamp, order and drawing answer one question between them: how
    recently did these two deal with each other. Newest first."""
    stale, _, _ = await seed_workshop_with_owner(db_session, login="rank_stale")
    stale.name = "Alfa Mebel"
    ordered, ordered_branch, _ = await seed_workshop_with_owner(db_session, login="rank_ordered")
    ordered.name = "Beta Mebel"
    recent, _, _ = await seed_workshop_with_owner(db_session, login="rank_recent")
    recent.name = "Gamma Mebel"
    await db_session.flush()
    client_row, token = await _client_token(db_session)

    now = datetime.now(UTC)
    order = await _seed_order(db_session, client_row=client_row, branch=ordered_branch)
    order.created_at = now - timedelta(days=2)
    db_session.add_all(
        [
            ClientWorkshopEntry(
                client_id=client_row.id,
                workshop_id=stale.id,
                last_entered_at=now - timedelta(days=30),
            ),
            ClientWorkshopEntry(
                client_id=client_row.id,
                workshop_id=recent.id,
                last_entered_at=now - timedelta(hours=1),
            ),
        ]
    )
    await db_session.flush()

    response = await client.get("/api/v1/client/my-workshops", headers=_auth(token))

    assert response.status_code == 200
    # Alphabetical order would be exactly the reverse, so this can only pass on
    # the activity key.
    assert [row["name"] for row in response.json()] == [
        "Gamma Mebel",
        "Beta Mebel",
        "Alfa Mebel",
    ]


async def test_my_workshops_carries_branch_coordinates_for_the_map_link(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """«Xaritada ko'rish» renders only where a branch has been placed."""
    workshop, plotted, _ = await seed_workshop_with_owner(db_session, login="coords_owner")
    plotted.latitude = Decimal("41.31150000")
    plotted.longitude = Decimal("69.27970000")
    unplotted = await _add_branch(db_session, workshop=workshop, name="Zangiota")
    await db_session.flush()
    _, token = await _client_token(db_session, preferred_branch_id=plotted.id)

    response = await client.get("/api/v1/client/my-workshops", headers=_auth(token))

    assert response.status_code == 200
    branches = {row["id"]: row for row in response.json()[0]["branches"]}
    assert float(branches[str(plotted.id)]["latitude"]) == pytest.approx(41.3115)
    assert float(branches[str(plotted.id)]["longitude"]) == pytest.approx(69.2797)
    assert branches[str(unplotted.id)]["latitude"] is None
    assert branches[str(unplotted.id)]["longitude"] is None


async def test_making_another_branch_primary_repins_without_a_fresh_scan(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The star on a branch row — the only re-pin that is not a link entry."""
    workshop, first, _ = await seed_workshop_with_owner(db_session, login="star_owner")
    second = await _add_branch(db_session, workshop=workshop, name="Yunusobod")
    client_row, token = await _client_token(db_session, preferred_branch_id=first.id)

    response = await client.patch(
        "/api/v1/client/profile",
        headers=_auth(token),
        json={"preferred_branch_id": str(second.id)},
    )

    assert response.status_code == 200, response.text
    assert response.json()["preferred_branch_id"] == str(second.id)
    assert client_row.preferred_branch_id == second.id
    listed = await client.get("/api/v1/client/my-workshops", headers=_auth(token))
    pinned = [row["id"] for row in listed.json()[0]["branches"] if row["is_pinned"]]
    assert pinned == [str(second.id)]


async def test_my_workshops_excludes_a_blocked_workshop(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    blocked, blocked_branch, _ = await seed_workshop_with_owner(db_session, login="blocked_history")
    live, live_branch, _ = await seed_workshop_with_owner(db_session, login="live_history")
    client_row, token = await _client_token(db_session, preferred_branch_id=blocked_branch.id)
    await _seed_order(db_session, client_row=client_row, branch=live_branch)
    blocked.status = WorkshopStatus.BLOCKED
    await db_session.flush()

    response = await client.get("/api/v1/client/my-workshops", headers=_auth(token))

    assert response.status_code == 200
    assert [row["workshop_id"] for row in response.json()] == [str(live.id)]


async def test_my_workshops_keeps_a_workshop_whose_branches_all_went_inactive(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # The pin is never cleared when its branch goes away (identity.md), and the
    # page still has to explain where the client's history lives.
    workshop, branch, _ = await seed_workshop_with_owner(db_session, login="all_retired")
    branch.status = BranchStatus.INACTIVE
    await db_session.flush()
    _, token = await _client_token(db_session, preferred_branch_id=branch.id)

    response = await client.get("/api/v1/client/my-workshops", headers=_auth(token))

    assert response.status_code == 200
    assert [row["workshop_id"] for row in response.json()] == [str(workshop.id)]
    assert response.json()[0]["is_pinned"] is True
    assert response.json()[0]["branches"] == []


# --- The surfaces that read the pin and the code ---------------------------


async def test_client_home_read_names_the_pinned_context(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    workshop, branch, _ = await seed_workshop_with_owner(db_session, login="subtitle_owner")
    _, pinned_token = await _client_token(db_session, preferred_branch_id=branch.id)
    _, unpinned_token = await _client_token(db_session, phone="+998900000002")

    pinned = await client.get("/api/v1/auth/me", headers=_auth(pinned_token))
    unpinned = await client.get("/api/v1/auth/me", headers=_auth(unpinned_token))

    assert pinned.json()["pinned_workshop_name"] == workshop.name
    assert pinned.json()["pinned_branch_name"] == branch.name
    # No pin → the header subtitle stays as it was.
    assert unpinned.json()["pinned_workshop_name"] is None
    assert unpinned.json()["pinned_branch_name"] is None


async def test_owner_surfaces_carry_the_public_code(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    workshop, branch, owner = await seed_workshop_with_owner(db_session, login="card_owner")
    owner.password_reset_required = False
    await db_session.flush()
    login = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "card_owner", "password": "Owner123"},
    )
    token = login.json()["access_token"]

    settings_response = await client.get("/api/v1/workshop/settings", headers=_auth(token))
    branch_response = await client.get(
        f"/api/v1/workshop/branches/{branch.id}", headers=_auth(token)
    )
    branches_response = await client.get("/api/v1/workshop/branches", headers=_auth(token))

    # Both halves of `/w/{code}/{branch_no}` reach the "Mijoz havolasi" card
    # without a second request.
    assert settings_response.json()["public_code"] == workshop.public_code
    assert branch_response.json()["workshop_public_code"] == workshop.public_code
    assert branch_response.json()["branch_no"] == branch.branch_no
    assert branches_response.json()[0]["workshop_public_code"] == workshop.public_code


async def test_the_public_code_has_no_write_path(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    workshop, _, owner = await seed_workshop_with_owner(db_session, login="rewrite_owner")
    owner.password_reset_required = False
    await db_session.flush()
    login = await client.post(
        "/api/v1/auth/workshop/login",
        json={"login": "rewrite_owner", "password": "Owner123"},
    )
    original = workshop.public_code

    response = await client.patch(
        "/api/v1/workshop/settings",
        headers=_auth(login.json()["access_token"]),
        json={"public_code": "AAAAAAAA"},
    )

    # A printed QR must never rot, so the settings form refuses the field
    # outright rather than quietly ignoring it.
    assert response.status_code == 422
    assert workshop.public_code == original
