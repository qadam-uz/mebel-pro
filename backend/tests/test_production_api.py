"""Production terminal API — the assign/start split and worker-scoped payloads.

Assignment is pure metadata (the order stays `confirmed`); the assigned worker's
start triggers `confirmed → cutting`; revert clears a phase's start stamp but
keeps the assignment. The production queue/job payloads are money-free by
construction — the leak test locks that boundary.
"""

import json
import uuid

from app.models.enums import AuthenticatedPrincipalType
from app.modules.access.api import create_session
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_sales_api import (
    _auth,
    _client_access,
    _materials,
    _optimized_draft,
    _placed_order,
    _staff,
    _workshop_setup,
)


async def _worker_access(db: AsyncSession, worker_id: uuid.UUID) -> str:
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=worker_id,
    )
    return tokens.access_token


async def test_start_cutting_requires_cutter_and_edger_assignments(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, _, owner_access, workshop_id, branch_id, _ = await _placed_order(client, db_session)
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    order_id = order["id"]

    approved = await client.post(
        f"/api/v1/workshop/orders/{order_id}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    assert approved.status_code == 200

    unassigned_start = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(owner_access),
        json={"version": approved.json()["version"]},
    )
    assert unassigned_start.status_code == 400
    assert unassigned_start.json()["code"] == "cutter_required"

    # A banded order accepts a cutter-only assignment (metadata) …
    cutter_only = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={"version": approved.json()["version"], "cutter_user_id": str(worker.id)},
    )
    assert cutter_only.status_code == 200
    assert cutter_only.json()["status"] == "confirmed"

    # … but cannot start until the edger is also assigned.
    no_edger_start = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(owner_access),
        json={"version": cutter_only.json()["version"]},
    )
    assert no_edger_start.status_code == 400
    assert no_edger_start.json()["code"] == "edger_required"

    assigned = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={"version": cutter_only.json()["version"], "edger_user_id": str(worker.id)},
    )
    started = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(owner_access),
        json={"version": assigned.json()["version"]},
    )
    assert started.status_code == 200
    assert started.json()["status"] == "cutting"


async def test_start_banding_stamps_once_within_edge_banding(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, _, owner_access, workshop_id, branch_id, _ = await _placed_order(client, db_session)
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    order_id = order["id"]

    approved = await client.post(
        f"/api/v1/workshop/orders/{order_id}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    assigned = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={
            "version": approved.json()["version"],
            "cutter_user_id": str(worker.id),
            "edger_user_id": str(worker.id),
        },
    )
    premature = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-banding",
        headers=_auth(owner_access),
        json={"version": assigned.json()["version"]},
    )
    assert premature.status_code == 400
    assert premature.json()["code"] == "invalid_order_status"

    started = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(owner_access),
        json={"version": assigned.json()["version"]},
    )
    cut_done = await client.post(
        f"/api/v1/workshop/orders/{order_id}/cutting-done",
        headers=_auth(owner_access),
        json={"version": started.json()["version"], "completed_by_user_id": str(worker.id)},
    )
    assert cut_done.json()["status"] == "edge_banding"
    assert cut_done.json()["banding_started_at"] is None

    band_start = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-banding",
        headers=_auth(owner_access),
        json={"version": cut_done.json()["version"]},
    )
    assert band_start.status_code == 200
    assert band_start.json()["status"] == "edge_banding"
    assert band_start.json()["banding_started_at"] is not None

    double_start = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-banding",
        headers=_auth(owner_access),
        json={"version": band_start.json()["version"]},
    )
    assert double_start.status_code == 400
    assert double_start.json()["code"] == "banding_already_started"


async def test_revert_clears_start_stamps_but_keeps_assignment(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, _, owner_access, workshop_id, branch_id, _ = await _placed_order(client, db_session)
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    order_id = order["id"]

    approved = await client.post(
        f"/api/v1/workshop/orders/{order_id}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    assigned = await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={
            "version": approved.json()["version"],
            "cutter_user_id": str(worker.id),
            "edger_user_id": str(worker.id),
        },
    )
    started = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(owner_access),
        json={"version": assigned.json()["version"]},
    )

    # cutting → confirmed: the start stamp clears, the assignment survives —
    # the job returns to the cutter's queue instead of vanishing.
    back_to_queue = await client.post(
        f"/api/v1/workshop/orders/{order_id}/revert",
        headers=_auth(owner_access),
        json={"version": started.json()["version"], "reason": "Wrong panel loaded"},
    )
    assert back_to_queue.status_code == 200
    body = back_to_queue.json()
    assert body["status"] == "confirmed"
    assert body["cutting_started_at"] is None
    assert body["assigned_cutter_user_id"] == str(worker.id)
    assert body["cutter_assigned_at"] is not None

    restarted = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-cutting",
        headers=_auth(owner_access),
        json={"version": body["version"]},
    )
    cut_done = await client.post(
        f"/api/v1/workshop/orders/{order_id}/cutting-done",
        headers=_auth(owner_access),
        json={"version": restarted.json()["version"], "completed_by_user_id": str(worker.id)},
    )
    band_start = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-banding",
        headers=_auth(owner_access),
        json={"version": cut_done.json()["version"]},
    )

    # edge_banding → cutting: the banding start clears, cutting's stays.
    back_to_cutting = await client.post(
        f"/api/v1/workshop/orders/{order_id}/revert",
        headers=_auth(owner_access),
        json={"version": band_start.json()["version"], "reason": "Cut list wrong"},
    )
    assert back_to_cutting.status_code == 200
    assert back_to_cutting.json()["status"] == "cutting"
    assert back_to_cutting.json()["banding_started_at"] is None
    assert back_to_cutting.json()["cutting_started_at"] is not None

    cut_done_again = await client.post(
        f"/api/v1/workshop/orders/{order_id}/cutting-done",
        headers=_auth(owner_access),
        json={
            "version": back_to_cutting.json()["version"],
            "completed_by_user_id": str(worker.id),
        },
    )
    band_start_again = await client.post(
        f"/api/v1/workshop/orders/{order_id}/start-banding",
        headers=_auth(owner_access),
        json={"version": cut_done_again.json()["version"]},
    )
    band_done = await client.post(
        f"/api/v1/workshop/orders/{order_id}/banding-done",
        headers=_auth(owner_access),
        json={
            "version": band_start_again.json()["version"],
            "completed_by_user_id": str(worker.id),
        },
    )
    assert band_done.json()["status"] == "ready"

    # ready → edge_banding: banding genuinely started, so its stamp survives.
    back_to_banding = await client.post(
        f"/api/v1/workshop/orders/{order_id}/revert",
        headers=_auth(owner_access),
        json={"version": band_done.json()["version"], "reason": "One edge missed"},
    )
    assert back_to_banding.status_code == 200
    assert back_to_banding.json()["status"] == "edge_banding"
    assert back_to_banding.json()["banding_started_at"] is not None


async def test_production_queue_scopes_partitions_and_stays_money_free(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, workshop_id, branch_id, _ = await _workshop_setup(db_session)
    panel, edge = await _materials(db_session, branch_id=branch_id)
    client_access, _ = await _client_access(
        db_session, phone=f"+99890{uuid.uuid4().int % 10**7:07d}"
    )
    worker_a = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    worker_b = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    access_a = await _worker_access(db_session, worker_a.id)

    order_ids: list[str] = []
    for assignee in (worker_a, worker_b):
        draft = await _optimized_draft(
            client, client_access, branch_id=branch_id, panel=panel, edge=edge
        )
        placed = await client.post(
            "/api/v1/client/orders",
            headers=_auth(client_access),
            json={
                "draft_id": draft["id"],
                "branch_id": str(branch_id),
                "contact_name": "Dilshod Karimov",
                "contact_phone": "+998901555222",
            },
        )
        assert placed.status_code == 201
        order = placed.json()
        approved = await client.post(
            f"/api/v1/workshop/orders/{order['id']}/approve",
            headers=_auth(owner_access),
            json={"version": order["version"]},
        )
        assigned = await client.post(
            f"/api/v1/workshop/orders/{order['id']}/assign",
            headers=_auth(owner_access),
            json={
                "version": approved.json()["version"],
                "cutter_user_id": str(assignee.id),
                "edger_user_id": str(assignee.id),
            },
        )
        assert assigned.status_code == 200
        order_ids.append(order["id"])

    # The station queue is personal for everyone: worker A sees only their own
    # jobs, and even the owner sees no one else's work (on-behalf management
    # lives on the office order page).
    queue_a = await client.get(
        "/api/v1/workshop/production/queue?station=cutting", headers=_auth(access_a)
    )
    assert queue_a.status_code == 200
    assert [job["id"] for job in queue_a.json()["jobs"]] == [order_ids[0]]
    assert queue_a.json()["jobs"][0]["assigned_cutter"]["full_name"] == worker_a.full_name
    assert queue_a.json()["jobs"][0]["client_first_name"] == "Dilshod"

    owner_queue = await client.get(
        "/api/v1/workshop/production/queue?station=cutting", headers=_auth(owner_access)
    )
    assert owner_queue.status_code == 200
    assert owner_queue.json()["jobs"] == []
    assert owner_queue.json()["completed_today"] == []

    # The payload is money-free by construction — no tiyin, no client phone.
    leakable = json.dumps(queue_a.json())
    assert "tiyin" not in leakable
    assert "998901555222" not in leakable
    assert "client_phone" not in leakable

    # Worker A drives their job through cutting; it leaves the cutting queue,
    # shows up in the banding queue, and lands in cutting's completed list.
    started = await client.post(
        f"/api/v1/workshop/orders/{order_ids[0]}/start-cutting",
        headers=_auth(access_a),
        json={"version": queue_a.json()["jobs"][0]["version"]},
    )
    assert started.status_code == 200
    cut_done = await client.post(
        f"/api/v1/workshop/orders/{order_ids[0]}/cutting-done",
        headers=_auth(access_a),
        json={"version": started.json()["version"]},
    )
    assert cut_done.status_code == 200

    queue_after = await client.get(
        "/api/v1/workshop/production/queue?station=cutting", headers=_auth(access_a)
    )
    assert queue_after.json()["jobs"] == []
    assert [job["id"] for job in queue_after.json()["completed_today"]] == [order_ids[0]]

    banding_queue = await client.get(
        "/api/v1/workshop/production/queue?station=banding", headers=_auth(access_a)
    )
    assert [job["id"] for job in banding_queue.json()["jobs"]] == [order_ids[0]]

    bad_station = await client.get(
        "/api/v1/workshop/production/queue?station=painting", headers=_auth(access_a)
    )
    assert bad_station.status_code == 400
    assert bad_station.json()["code"] == "invalid_station"


async def test_production_job_sheet_is_sanitized_and_assignment_gated(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    order, _, owner_access, workshop_id, branch_id, _ = await _placed_order(client, db_session)
    worker = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    bystander = await _staff(db_session, workshop_id=workshop_id, branch_id=branch_id)
    worker_token = await _worker_access(db_session, worker.id)
    bystander_token = await _worker_access(db_session, bystander.id)
    order_id = order["id"]

    approved = await client.post(
        f"/api/v1/workshop/orders/{order_id}/approve",
        headers=_auth(owner_access),
        json={"version": order["version"]},
    )
    await client.post(
        f"/api/v1/workshop/orders/{order_id}/assign",
        headers=_auth(owner_access),
        json={
            "version": approved.json()["version"],
            "cutter_user_id": str(worker.id),
            "edger_user_id": str(worker.id),
        },
    )

    job = await client.get(
        f"/api/v1/workshop/production/jobs/{order_id}", headers=_auth(worker_token)
    )
    assert job.status_code == 200
    body = job.json()
    assert body["order_number"] == order["order_number"]
    assert body["client_first_name"] == "Checkout"
    assert body["assigned_cutter"]["full_name"] == worker.full_name
    assert body["items"], "job sheet must carry the parts list"
    banded_sides = [
        side
        for item in body["items"]
        for side in (item["edge_top"], item["edge_bottom"], item["edge_left"], item["edge_right"])
        if side is not None
    ]
    assert banded_sides, "seeded order has banded sides"
    assert body["cutting_result"] is not None

    # No prices anywhere — including inside the per-side edge snapshots, which
    # carry price_tiyin in the office payload.
    leakable = json.dumps(body)
    assert "tiyin" not in leakable
    assert "client_phone" not in leakable

    # A production user the job is not assigned to cannot open it.
    denied = await client.get(
        f"/api/v1/workshop/production/jobs/{order_id}", headers=_auth(bystander_token)
    )
    assert denied.status_code == 404
