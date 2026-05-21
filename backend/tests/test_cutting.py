"""Integration tests for the cutting module — draft CRUD, optimise, branches, PDF."""

import uuid
from collections.abc import Awaitable, Callable

import pytest
from app.core.security import hash_password
from app.models.catalog import BranchMaterial, Material
from app.models.cutting import CuttingDraft
from app.models.enums import (
    BranchStatus,
    CatalogStatus,
    CuttingResultStatus,
    MaterialKind,
    MaterialType,
    PrincipalType,
)
from app.models.identity import Client, WorkshopUser
from app.models.workshop import Branch, Workshop
from app.services import cutting as service
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

API = "/api/v1/c/cutting"

AuthFactory = Callable[[PrincipalType, uuid.UUID], Awaitable[dict[str, str]]]


async def _client_auth(db: AsyncSession, auth_headers: AuthFactory) -> tuple[Client, dict]:
    c = Client(telegram_id=int(uuid.uuid4().int % 10**12), phone="+998900000000", first_name="C")
    db.add(c)
    await db.commit()
    headers = await auth_headers(PrincipalType.CLIENT, c.id)
    return c, headers


async def _material(
    db: AsyncSession, *, grain: bool = False, name: str = "DSP 18", active: bool = True
) -> Material:
    m = Material(
        kind=MaterialKind.SHEET,
        type=MaterialType.DSP,
        name=name,
        thickness_mm=18,
        color="white",
        sheet_length_mm=2800,
        sheet_width_mm=2070,
        grain_direction=grain,
        status=CatalogStatus.ACTIVE if active else CatalogStatus.INACTIVE,
    )
    db.add(m)
    await db.commit()
    return m


def _part_payload(material_id: uuid.UUID, **over: object) -> dict:
    base: dict = {
        "material_id": str(material_id),
        "material_source": "shop",
        "length_mm": 600,
        "width_mm": 400,
        "quantity": 4,
    }
    base.update(over)
    return base


# --- draft CRUD -------------------------------------------------------------


async def test_create_list_get_delete_draft(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    _, headers = await _client_auth(db_session, auth_headers)

    r = await client.post(API, headers=headers)
    assert r.status_code == 201
    draft_id = r.json()["id"]

    r = await client.get(API, headers=headers)
    assert r.status_code == 200 and len(r.json()) == 1

    r = await client.get(f"{API}/{draft_id}", headers=headers)
    assert r.status_code == 200

    r = await client.delete(f"{API}/{draft_id}", headers=headers)
    assert r.status_code == 204

    r = await client.get(API, headers=headers)
    assert r.json() == []


async def test_draft_private_to_client(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    _, headers_a = await _client_auth(db_session, auth_headers)
    _, headers_b = await _client_auth(db_session, auth_headers)
    r = await client.post(API, headers=headers_a)
    draft_id = r.json()["id"]
    r = await client.get(f"{API}/{draft_id}", headers=headers_b)
    assert r.status_code == 403


async def test_replace_parts_validates_material(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    _, headers = await _client_auth(db_session, auth_headers)
    r = await client.post(API, headers=headers)
    draft_id = r.json()["id"]

    # unknown material -> material_not_found
    r = await client.put(
        f"{API}/{draft_id}",
        headers=headers,
        json={"parts": [_part_payload(uuid.uuid4())]},
    )
    assert r.status_code == 422 and r.json()["code"] == "material_not_found"


async def test_draft_cap(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    c, _ = await _client_auth(db_session, auth_headers)
    # seed 50 drafts directly, then the 51st must fail
    for _ in range(service.MAX_OPEN_DRAFTS):
        db_session.add(CuttingDraft(client_id=c.id, parts_snapshot=[]))
    await db_session.commit()
    headers = await auth_headers(PrincipalType.CLIENT, c.id)
    r = await client.post(API, headers=headers)
    assert r.status_code == 409 and r.json()["code"] == "draft_limit_exceeded"


# --- optimise / choose ------------------------------------------------------


async def test_optimise_and_choose(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    _, headers = await _client_auth(db_session, auth_headers)
    m = await _material(db_session)
    r = await client.post(API, headers=headers)
    draft_id = r.json()["id"]
    await client.put(
        f"{API}/{draft_id}",
        headers=headers,
        json={"parts": [_part_payload(m.id, quantity=6)]},
    )

    r = await client.post(f"{API}/{draft_id}/optimise", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["results"]) == 2
    assert body["chosen_result_id"] is not None
    chosen = body["chosen_result_id"]
    # each result has sheets + placements covering all 6 instances
    for result in body["results"]:
        placed = sum(len(s["placements"]) for s in result["sheets"])
        assert placed == 6
        assert 0.0 <= result["waste_percentage"] <= 1.0

    # choose the other result
    other = next(r["id"] for r in body["results"] if r["id"] != chosen)
    r = await client.post(f"{API}/{draft_id}/choose/{other}", headers=headers)
    assert r.status_code == 200 and r.json()["chosen_result_id"] == other


async def test_optimise_replaces_previous_candidates(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    _, headers = await _client_auth(db_session, auth_headers)
    m = await _material(db_session)
    r = await client.post(API, headers=headers)
    draft_id = r.json()["id"]
    await client.put(f"{API}/{draft_id}", headers=headers, json={"parts": [_part_payload(m.id)]})
    r1 = await client.post(f"{API}/{draft_id}/optimise", headers=headers)
    first_ids = {res["id"] for res in r1.json()["results"]}
    r2 = await client.post(f"{API}/{draft_id}/optimise", headers=headers)
    second_ids = {res["id"] for res in r2.json()["results"]}
    assert first_ids.isdisjoint(second_ids)  # old candidates replaced


async def test_optimise_too_many_parts(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    _, headers = await _client_auth(db_session, auth_headers)
    m = await _material(db_session)
    r = await client.post(API, headers=headers)
    draft_id = r.json()["id"]
    await client.put(
        f"{API}/{draft_id}",
        headers=headers,
        json={"parts": [_part_payload(m.id, quantity=101)]},
    )
    r = await client.post(f"{API}/{draft_id}/optimise", headers=headers)
    assert r.status_code == 422 and r.json()["code"] == "too_many_parts"


# --- branches indicator -----------------------------------------------------


async def test_branches_indicator_covers(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    _, headers = await _client_auth(db_session, auth_headers)
    m = await _material(db_session)
    ws = Workshop(name="WS", phone="+998900000001")
    db_session.add(ws)
    await db_session.flush()
    branch = Branch(
        workshop_id=ws.id,
        name="Chilonzor",
        address="A",
        phone="+998900000002",
        status=BranchStatus.ACTIVE,
    )
    db_session.add(branch)
    await db_session.flush()
    db_session.add(
        BranchMaterial(
            branch_id=branch.id, material_id=m.id, price_tiyin=100, status=CatalogStatus.ACTIVE
        )
    )
    await db_session.commit()

    r = await client.post(API, headers=headers)
    draft_id = r.json()["id"]
    await client.put(f"{API}/{draft_id}", headers=headers, json={"parts": [_part_payload(m.id)]})

    r = await client.get(f"{API}/{draft_id}/branches", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "branches"
    assert any(b["name"] == "Chilonzor" for b in body["branches"])


async def test_branches_indicator_all_own(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    _, headers = await _client_auth(db_session, auth_headers)
    m = await _material(db_session)
    ws = Workshop(name="WS", phone="+998900000001")
    db_session.add(ws)
    await db_session.flush()
    db_session.add(Branch(workshop_id=ws.id, name="Any", address="A", phone="+998900000002"))
    await db_session.commit()

    r = await client.post(API, headers=headers)
    draft_id = r.json()["id"]
    await client.put(
        f"{API}/{draft_id}",
        headers=headers,
        json={"parts": [_part_payload(m.id, material_source="own")]},
    )
    r = await client.get(f"{API}/{draft_id}/branches", headers=headers)
    assert r.json()["mode"] == "any"


async def test_branches_indicator_none(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    _, headers = await _client_auth(db_session, auth_headers)
    m = await _material(db_session)
    r = await client.post(API, headers=headers)
    draft_id = r.json()["id"]
    await client.put(f"{API}/{draft_id}", headers=headers, json={"parts": [_part_payload(m.id)]})
    r = await client.get(f"{API}/{draft_id}/branches", headers=headers)
    body = r.json()
    assert body["mode"] == "none"
    assert str(m.id) in body["uncovered_material_ids"]


# --- PDF --------------------------------------------------------------------


async def test_pdf_returns_application_pdf(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    _, headers = await _client_auth(db_session, auth_headers)
    m = await _material(db_session)
    r = await client.post(API, headers=headers)
    draft_id = r.json()["id"]
    await client.put(f"{API}/{draft_id}", headers=headers, json={"parts": [_part_payload(m.id)]})
    await client.post(f"{API}/{draft_id}/optimise", headers=headers)

    r = await client.get(f"{API}/{draft_id}/pdf", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


# --- order-facing service functions -----------------------------------------


async def test_confirm_and_invalidate_lifecycle(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    c, headers = await _client_auth(db_session, auth_headers)
    m = await _material(db_session)
    r = await client.post(API, headers=headers)
    draft_id = uuid.UUID(r.json()["id"])
    await client.put(f"{API}/{draft_id}", headers=headers, json={"parts": [_part_payload(m.id)]})
    await client.post(f"{API}/{draft_id}/optimise", headers=headers)

    draft = await service.get_owned_draft(db_session, c.id, draft_id)
    chosen = await service.get_chosen_result(db_session, draft)
    assert chosen is not None

    order_id = uuid.uuid4()
    confirmed = await service.confirm_result_for_order(db_session, draft, order_id)
    await db_session.commit()
    assert confirmed.status is CuttingResultStatus.CONFIRMED
    assert confirmed.order_id == order_id
    assert confirmed.draft_id is None
    # draft + other candidates gone
    assert await db_session.get(CuttingDraft, draft_id) is None

    invalidated = await service.invalidate_result(db_session, confirmed)
    assert invalidated.status is CuttingResultStatus.INVALIDATED


async def test_workshop_reads_confirmed_result(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory
) -> None:
    c, headers = await _client_auth(db_session, auth_headers)
    m = await _material(db_session)
    r = await client.post(API, headers=headers)
    draft_id = uuid.UUID(r.json()["id"])
    await client.put(f"{API}/{draft_id}", headers=headers, json={"parts": [_part_payload(m.id)]})
    await client.post(f"{API}/{draft_id}/optimise", headers=headers)
    draft = await service.get_owned_draft(db_session, c.id, draft_id)
    confirmed = await service.confirm_result_for_order(db_session, draft, uuid.uuid4())

    ws = Workshop(name="WS", phone="+998900000009")
    db_session.add(ws)
    await db_session.flush()
    staff = WorkshopUser(
        workshop_id=ws.id,
        login="cutter",
        password_hash=hash_password("Passw0rd!"),
        full_name="Cutter",
        phone="+998900000010",
        force_password_change=False,
    )
    db_session.add(staff)
    await db_session.commit()

    ws_headers = await auth_headers(PrincipalType.WORKSHOP_USER, staff.id)
    r = await client.get(f"/api/v1/workshop/cutting-results/{confirmed.id}", headers=ws_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"


@pytest.mark.parametrize("kind", ["sheet"])
async def test_client_material_picker(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthFactory, kind: str
) -> None:
    _, headers = await _client_auth(db_session, auth_headers)
    await _material(db_session, name="Active DSP")
    await _material(db_session, name="Inactive", active=False)
    r = await client.get("/api/v1/c/materials", headers=headers)
    assert r.status_code == 200
    names = [m["name"] for m in r.json()]
    assert "Active DSP" in names and "Inactive" not in names
