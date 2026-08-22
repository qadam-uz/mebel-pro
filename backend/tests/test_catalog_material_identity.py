"""Catalog identity after the decor-format reshape.

Three owners, three tables. Identity (who makes it, what it is called, what it
looks like) is platform-owned and lives on `decors`. The concrete product
(substrate, thickness, sheet or tape size, finished faces) is *also* platform-
owned and lives on `decor_formats` — it is the manufacturer's fact, not the
branch's. The branch owns only the commercial decision: `branch_materials` is
"we carry this format, at this price, with this threshold, on/off".

There is no stored name on any of the three — every display string is composed
by `app/core/material_label.py`, so these tests assert the composed `label`
rather than a `name` column.
"""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from app.models.enums import AuthenticatedPrincipalType, DecorType, MaterialStatus
from app.modules.access.api import create_session
from app.modules.catalog.contracts import BranchMaterial, Decor, DecorFormat, Manufacturer
from httpx import AsyncClient
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_decor, seed_platform_user, seed_workshop_with_owner

SEP = "\N{MULTIPLICATION SIGN}"


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _platform_access(db_session: AsyncSession) -> str:
    platform = await seed_platform_user(db_session, password_reset_required=False)
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        principal_id=platform.id,
    )
    return tokens.access_token


async def _owner_access(db_session: AsyncSession) -> tuple[str, uuid.UUID]:
    _, branch, owner = await seed_workshop_with_owner(db_session)
    owner.password_reset_required = False
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token, branch.id


async def _manufacturer(client: AsyncClient, access: str, name: str = "Egger") -> str:
    response = await client.post(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(access),
        json={"name": name, "country": "AT"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _decor(
    client: AsyncClient,
    access: str,
    manufacturer_id: str,
    *,
    code: str | None = None,
    name: str = "Sonoma eman",
    has_grain: bool = False,
) -> str:
    """One platform decor. No `type` — a pattern is not a substrate any more."""

    response = await client.post(
        "/api/v1/platform/catalog/decors",
        headers=_auth(access),
        json={
            "manufacturer_id": manufacturer_id,
            "code": code,
            "name": name,
            "has_grain": has_grain,
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _format(
    client: AsyncClient,
    access: str,
    decor_id: str,
    **fields: Any,
) -> dict[str, Any]:
    """One platform format of that decor. Only the platform may write these."""

    response = await client.post(
        f"/api/v1/platform/catalog/decors/{decor_id}/formats",
        headers=_auth(access),
        json=fields,
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_decor_create_composes_its_label_from_identity_alone(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A decor has no substrate and no format, so its label carries neither.

    This is the identity slot of the same formatter the branch material and the
    frozen order snapshot use — the substrate and the dimensions arrive only
    once the platform says which formats the pattern is made in.
    """
    access = await _platform_access(db_session)
    manufacturer_id = await _manufacturer(client, access)

    coded = await client.post(
        "/api/v1/platform/catalog/decors",
        headers=_auth(access),
        json={
            "manufacturer_id": manufacturer_id,
            "code": "H1145",
            "name": "Sonoma eman",
        },
    )
    grained = await client.post(
        "/api/v1/platform/catalog/decors",
        headers=_auth(access),
        json={
            "manufacturer_id": manufacturer_id,
            "code": "H1334 ST9",
            "name": "Sonoma eman",
            "has_grain": True,
        },
    )
    uncoded = await client.post(
        "/api/v1/platform/catalog/decors",
        headers=_auth(access),
        json={"manufacturer_id": manufacturer_id, "name": "Oq"},
    )
    missing_name = await client.post(
        "/api/v1/platform/catalog/decors",
        headers=_auth(access),
        json={"manufacturer_id": manufacturer_id, "code": "X1", "name": "   "},
    )

    assert coded.status_code == 201, coded.text
    assert coded.json()["label"] == "Egger H1145 · Sonoma eman"
    assert grained.status_code == 201
    assert grained.json()["label"] == "Egger H1334 ST9 · Sonoma eman"
    assert grained.json()["has_grain"] is True
    # No code: the name fills the identity slot and must not repeat as a detail.
    assert uncoded.status_code == 201
    assert uncoded.json()["label"] == "Egger Oq"
    assert missing_name.status_code == 400
    assert missing_name.json()["code"] == "decor_name_required"
    # The decor surface carries no substrate, no format and no price at all.
    for key in ("type", "thickness_mm", "length_mm", "width_mm", "tape_width_mm", "price_tiyin"):
        assert key not in grained.json()
    # A brand-new pattern has no products yet — the admin table says so.
    assert grained.json()["format_count"] == 0


async def test_decor_uniqueness_is_by_code_then_by_name(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Two decors of one maker are the same decor when their codes match.

    When neither has a code the name is the identity instead. Neither rule is
    per substrate any more, and that is the whole point of the reshape: the
    kromka H1334 and the LDSP H1334 of one maker are the SAME pattern in two
    formats, not two decors. Making `type` part of identity is exactly what
    produced the board/kromka twin rows the migration merged away.
    """
    access = await _platform_access(db_session)
    egger = await _manufacturer(client, access, "Egger Unique")
    kronospan = await _manufacturer(client, access, "Kronospan Unique")

    async def create(manufacturer_id: str, code: str | None, name: str) -> int:
        response = await client.post(
            "/api/v1/platform/catalog/decors",
            headers=_auth(access),
            json={"manufacturer_id": manufacturer_id, "code": code, "name": name},
        )
        return response.status_code

    assert await create(egger, "H1334", "Sonoma") == 201
    # Same maker, same code (case-insensitively) — a duplicate.
    assert await create(egger, "h1334", "Boshqa nom") == 409
    # And so is the row that used to be allowed through as "the kromka one".
    assert await create(egger, "H1334", "Sonoma") == 409
    # A different maker is a different decor.
    assert await create(kronospan, "H1334", "Sonoma") == 201
    # Code-less rows fall back to the name.
    assert await create(egger, None, "Oq") == 201
    assert await create(egger, None, "oq") == 409
    assert await create(egger, None, "Qora") == 201


async def test_decor_patch_updates_identity_and_refreshes_the_search_key(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access = await _platform_access(db_session)
    egger = await _manufacturer(client, access, "Egger Patch")
    kronospan = await _manufacturer(client, access, "Kronospan Patch")
    created = await client.post(
        "/api/v1/platform/catalog/decors",
        headers=_auth(access),
        json={"manufacturer_id": egger, "code": "H1334", "name": "Oak"},
    )
    assert created.status_code == 201
    decor_id = created.json()["id"]

    patched = await client.patch(
        f"/api/v1/platform/catalog/decors/{decor_id}",
        headers=_auth(access),
        json={"manufacturer_id": kronospan, "name": "White"},
    )
    assert patched.status_code == 200
    assert patched.json()["label"] == "Kronospan Patch H1334 · White"

    # The search key is rebuilt on every write, so the new maker and name are
    # both findable straight away.
    by_new_name = await client.get(
        "/api/v1/platform/catalog/decors?search=white", headers=_auth(access)
    )
    by_new_manufacturer = await client.get(
        "/api/v1/platform/catalog/decors?search=kronospan", headers=_auth(access)
    )
    by_old_name = await client.get(
        "/api/v1/platform/catalog/decors?search=oak", headers=_auth(access)
    )
    assert [row["id"] for row in by_new_name.json()] == [decor_id]
    assert [row["id"] for row in by_new_manufacturer.json()] == [decor_id]
    assert by_old_name.json() == []


async def test_renaming_a_manufacturer_rebuilds_its_decors_search_keys(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The maker name is folded into every decor's search key.

    Renaming the manufacturer without a backfill would leave every one of its
    decors findable only under the old name — silently, with no error.
    """
    access = await _platform_access(db_session)
    manufacturer_id = await _manufacturer(client, access, "Oldname")
    created = await client.post(
        "/api/v1/platform/catalog/decors",
        headers=_auth(access),
        json={"manufacturer_id": manufacturer_id, "code": "H1", "name": "Sonoma"},
    )
    assert created.status_code == 201

    renamed = await client.patch(
        f"/api/v1/platform/catalog/manufacturers/{manufacturer_id}",
        headers=_auth(access),
        json={"name": "Newname"},
    )
    assert renamed.status_code == 200

    by_new = await client.get(
        "/api/v1/platform/catalog/decors?search=newname", headers=_auth(access)
    )
    by_old = await client.get(
        "/api/v1/platform/catalog/decors?search=oldname", headers=_auth(access)
    )
    assert [row["id"] for row in by_new.json()] == [created.json()["id"]]
    assert by_old.json() == []


async def test_decor_search_is_script_and_apostrophe_insensitive(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Uzbek is written in two scripts; the same decor is typed four ways.

    The stored key and the query are folded through the same function, and the
    query side splits on whitespace so a multi-word search still matches a key
    that has no word boundaries in it.
    """
    access = await _platform_access(db_session)
    manufacturer_id = await _manufacturer(client, access, "Egger Search")
    created = await client.post(
        "/api/v1/platform/catalog/decors",
        headers=_auth(access),
        json={
            "manufacturer_id": manufacturer_id,
            "code": "H1334",
            "name": "Yong'oq",
        },
    )
    assert created.status_code == 201
    decor_id = created.json()["id"]

    for query in ["yong'oq", "yongoq", "yongok", "ёнғоқ", "H1334", "h1334", "эггер ёнғоқ"]:
        found = await client.get(
            "/api/v1/platform/catalog/decors", headers=_auth(access), params={"search": query}
        )
        assert found.status_code == 200
        assert [row["id"] for row in found.json()] == [decor_id], query

    missing = await client.get(
        "/api/v1/platform/catalog/decors", headers=_auth(access), params={"search": "sonoma"}
    )
    assert missing.json() == []


async def test_branch_material_label_adds_the_format_it_carries(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The dimensions in a label come from the platform format, not the branch.

    Byte-for-byte the format the old `Material.name` column stored — the label
    module's own unit tests are the lock on that; this asserts the halves are
    wired together correctly across all three tables.
    """
    platform_access = await _platform_access(db_session)
    owner_access, branch_id = await _owner_access(db_session)
    manufacturer_id = await _manufacturer(client, platform_access, "Egger Format")
    panel_decor = await _decor(
        client, platform_access, manufacturer_id, code="H1334 ST9", name="Sonoma eman"
    )
    uncoded_decor = await _decor(client, platform_access, manufacturer_id, code=None, name="Oq")
    panel_format = await _format(
        client,
        platform_access,
        panel_decor,
        type="ldsp",
        thickness_mm="18",
        length_mm=2750,
        width_mm=1830,
        finished_sides=2,
    )
    kromka_format = await _format(
        client,
        platform_access,
        uncoded_decor,
        type="kromka",
        thickness_mm="2",
        tape_width_mm=36,
    )

    attached = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={
            "items": [
                {"decor_format_id": panel_format["id"], "price_tiyin": 250_000},
                {"decor_format_id": kromka_format["id"], "price_tiyin": 1_000},
            ],
        },
    )

    assert attached.status_code == 201, attached.text
    rows = {row["decor_format_id"]: row for row in attached.json()["created"]}
    assert (
        rows[panel_format["id"]]["label"]
        == f"LDSP Egger Format H1334 ST9 · Sonoma eman · 2750{SEP}1830{SEP}18 mm"
    )
    # No code: `Oq` fills the identity slot and is suppressed from the detail.
    assert rows[kromka_format["id"]]["label"] == f"Egger Format Oq · 2{SEP}36 mm"
    # Dimensions are read one level down, through `decor_format` — the branch row
    # itself carries nothing but the commercial decision.
    assert rows[panel_format["id"]]["decor_format"]["length_mm"] == 2750
    for key in ("thickness_mm", "length_mm", "width_mm", "tape_width_mm", "type"):
        assert key not in rows[panel_format["id"]]


async def test_one_decor_fans_out_to_many_formats(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The whole point of the split: one identity, many formats.

    A 16 mm and an 18 mm sheet of one decor are different things to cut, stock
    and price, so each is its own format and its own branch row — but they share
    one decor, one name and one photo. A one-sided board of the same size is a
    different product again, and the natural key says so.
    """
    platform_access = await _platform_access(db_session)
    owner_access, branch_id = await _owner_access(db_session)
    manufacturer_id = await _manufacturer(client, platform_access, "Egger Fanout")
    decor_id = await _decor(client, platform_access, manufacturer_id, code="H1", name="Sonoma")

    formats = [
        await _format(
            client,
            platform_access,
            decor_id,
            type="ldsp",
            thickness_mm="18",
            length_mm=2750,
            width_mm=1830,
            finished_sides=2,
        ),
        await _format(
            client,
            platform_access,
            decor_id,
            type="ldsp",
            thickness_mm="16",
            length_mm=2750,
            width_mm=1830,
            finished_sides=2,
        ),
        await _format(
            client,
            platform_access,
            decor_id,
            type="ldsp",
            thickness_mm="18",
            length_mm=2800,
            width_mm=2070,
            finished_sides=2,
        ),
        # Same sheet, one finished face — a cheaper product, not a variant.
        await _format(
            client,
            platform_access,
            decor_id,
            type="ldsp",
            thickness_mm="18",
            length_mm=2750,
            width_mm=1830,
            finished_sides=1,
        ),
        # And the tape of the same pattern, which used to need its own decor.
        await _format(
            client,
            platform_access,
            decor_id,
            type="kromka",
            thickness_mm="0.4",
            tape_width_mm=22,
        ),
    ]
    attached = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={
            "items": [
                {"decor_format_id": row["id"], "price_tiyin": 100_000 + index}
                for index, row in enumerate(formats)
            ],
        },
    )

    assert attached.status_code == 201, attached.text
    rows = attached.json()["created"]
    assert len(rows) == 5
    assert {row["decor"]["id"] for row in rows} == {decor_id}
    # Every row renders its own product, so the operator can tell them apart.
    assert len({row["label"] for row in rows}) == 5
    assert sum(1 for row in rows if row["label"].endswith("1 tomonlama")) == 1

    by_decor = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials?decor_id={decor_id}",
        headers=_auth(owner_access),
    )
    assert len(by_decor.json()) == 5
    # Filtering the branch's own shelf by substrate reads the format, not the
    # decor: one decor, four boards and one tape.
    tapes = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials?decor_id={decor_id}&type=kromka",
        headers=_auth(owner_access),
    )
    assert len(tapes.json()) == 1


async def test_branch_material_patch_touches_price_and_threshold_only(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The format is this row's identity, so PATCH cannot move it.

    Stock, cutting panels and order items all FK this row. Re-dimensioning it in
    place would silently rewrite what every one of them refers to — so "change
    the format" means attaching the other format, and the platform (not the
    branch) is the only writer of a format in the first place. What is left to
    patch is exactly the branch's own two numbers.
    """
    platform_access = await _platform_access(db_session)
    owner_access, branch_id = await _owner_access(db_session)
    manufacturer_id = await _manufacturer(client, platform_access, "Egger Patchfmt")
    decor_id = await _decor(client, platform_access, manufacturer_id, code="H1", name="Sonoma")
    thick = await _format(
        client,
        platform_access,
        decor_id,
        type="ldsp",
        thickness_mm="18",
        length_mm=2750,
        width_mm=1830,
        finished_sides=2,
    )
    attached = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={"items": [{"decor_format_id": thick["id"], "price_tiyin": 250_000}]},
    )
    assert attached.status_code == 201, attached.text
    row_id = attached.json()["created"][0]["id"]

    repriced = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}/materials/{row_id}",
        headers=_auth(owner_access),
        json={"price_tiyin": 260_000, "min_stock": 4},
    )
    # Format fields are not part of the patch schema: they are ignored, and the
    # row still points at the format it was attached with.
    ignored = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}/materials/{row_id}",
        headers=_auth(owner_access),
        json={"thickness_mm": "16", "length_mm": 2800, "width_mm": 2070, "decor_format_id": None},
    )
    negative = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}/materials/{row_id}",
        headers=_auth(owner_access),
        json={"price_tiyin": -1},
    )

    assert repriced.status_code == 200, repriced.text
    assert repriced.json()["price_tiyin"] == 260_000
    assert repriced.json()["min_stock"] == 4
    assert repriced.json()["price_unset"] is False
    assert ignored.status_code == 200, ignored.text
    assert ignored.json()["decor_format_id"] == thick["id"]
    assert ignored.json()["decor_format"]["thickness_mm"] == "18"
    assert ignored.json()["decor_format"]["length_mm"] == 2750
    assert negative.status_code == 400
    assert negative.json()["code"] == "invalid_price"


async def test_catalog_column_checks_hold_at_the_db(
    db_session: AsyncSession,
) -> None:
    """The shape rule is a real table CHECK now — it could not be before.

    `type` used to live on `decors`, out of reach of any constraint on the table
    that carried the dimensions, so the DB could only guard a positive thickness
    and length >= width and the rest was the service layer's word. Now that the
    substrate sits on the same row as the dimensions, the whole rule is
    `ck_decor_formats_shape` and the service's `decor_format_shape_mismatch` is
    only there to turn it into a message instead of an IntegrityError.
    """
    manufacturer = Manufacturer(name=f"Constraint Maker {uuid.uuid4().hex[:6]}")
    db_session.add(manufacturer)
    await db_session.flush()
    decor = await seed_decor(db_session, manufacturer=manufacturer, code="C1")

    def board(**overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "decor_id": decor.id,
            "type": DecorType.LDSP,
            "thickness_mm": Decimal("18"),
            "length_mm": 2750,
            "width_mm": 1830,
            "finished_sides": 2,
            "status": MaterialStatus.ACTIVE,
        }
        return base | overrides

    for invalid in (
        # Thickness must be a real measurement.
        board(thickness_mm=Decimal("0")),
        # A board without a size, and a board wearing a tape width.
        board(length_mm=None, width_mm=None),
        board(tape_width_mm=19),
        # Orientation is normalised on write, so an un-normalised row is a bug.
        board(length_mm=1830, width_mm=2750),
        # A board type's finished-face count may only be 1 or 2.
        #
        # `board(finished_sides=None)` is deliberately NOT in this list: a SQL
        # CHECK passes whenever it evaluates to NULL rather than FALSE, and
        # `NULL IN (1, 2)` is NULL, so the shape CHECK cannot catch a *missing*
        # finished-face count on a board type in either dialect. That branch of
        # the rule is the service's alone — see the format-create tests in
        # tests/test_catalog_decor_formats.py, which pin
        # `decor_format_shape_mismatch` on exactly this input.
        board(finished_sides=0),
        board(finished_sides=3),
        # A non-board type must not.
        board(type=DecorType.FANERA, finished_sides=2),
        # A tape carries a tape width and nothing else.
        board(type=DecorType.KROMKA, finished_sides=None),
        board(
            type=DecorType.KROMKA,
            length_mm=None,
            width_mm=None,
            finished_sides=None,
            tape_width_mm=0,
        ),
        board(
            type=DecorType.KROMKA,
            finished_sides=None,
            tape_width_mm=19,
        ),
    ):
        with pytest.raises(IntegrityError):
            await db_session.execute(insert(DecorFormat).values(**invalid))
            await db_session.flush()
        await db_session.rollback()

    # And the branch row's own two numbers, which are all it has left to guard.
    manufacturer = Manufacturer(name=f"Constraint Maker {uuid.uuid4().hex[:6]}")
    db_session.add(manufacturer)
    await db_session.flush()
    decor = await seed_decor(db_session, manufacturer=manufacturer, code="C2")
    decor_format = DecorFormat(
        decor_id=decor.id,
        type=DecorType.LDSP,
        thickness_mm=Decimal("18"),
        length_mm=2750,
        width_mm=1830,
        finished_sides=2,
    )
    db_session.add(decor_format)
    await db_session.flush()
    _, branch, _ = await seed_workshop_with_owner(db_session, login=f"c-{uuid.uuid4().hex[:6]}")

    for invalid in (
        {"branch_id": branch.id, "decor_format_id": decor_format.id, "price_tiyin": -1},
        {"branch_id": branch.id, "decor_format_id": decor_format.id, "min_stock": -1},
    ):
        with pytest.raises(IntegrityError):
            await db_session.execute(insert(BranchMaterial).values(**invalid))
            await db_session.flush()
        await db_session.rollback()


async def test_decor_deactivation_hides_it_from_the_branch_picker(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, branch_id = await _owner_access(db_session)
    manufacturer_id = await _manufacturer(client, platform_access, "Egger Status")
    decor_id = await _decor(client, platform_access, manufacturer_id, code="H1", name="Sonoma")
    # A decor with no format is a name nobody can attach anything of, so the
    # picker only starts offering it once it has a product.
    await _format(
        client,
        platform_access,
        decor_id,
        type="ldsp",
        thickness_mm="18",
        length_mm=2750,
        width_mm=1830,
        finished_sides=2,
    )

    visible = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/decors", headers=_auth(owner_access)
    )
    deactivated = await client.post(
        f"/api/v1/platform/catalog/decors/{decor_id}/deactivate",
        headers=_auth(platform_access),
    )
    hidden = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/decors", headers=_auth(owner_access)
    )
    reactivated = await client.post(
        f"/api/v1/platform/catalog/decors/{decor_id}/activate",
        headers=_auth(platform_access),
    )
    visible_again = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/decors", headers=_auth(owner_access)
    )

    assert [row["decor"]["id"] for row in visible.json()["items"]] == [decor_id]
    assert visible.json()["items"][0]["available_format_count"] == 1
    assert visible.json()["items"][0]["carried_format_count"] == 0
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "inactive"
    assert hidden.json() == {"items": [], "total": 0}
    assert reactivated.status_code == 200
    assert [row["decor"]["id"] for row in visible_again.json()["items"]] == [decor_id]


async def test_decor_writes_are_platform_only(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, _ = await _owner_access(db_session)
    manufacturer = Manufacturer(name=f"Locked {uuid.uuid4().hex[:6]}")
    db_session.add(manufacturer)
    await db_session.flush()

    listed = await client.get("/api/v1/platform/catalog/decors", headers=_auth(owner_access))
    created = await client.post(
        "/api/v1/platform/catalog/decors",
        headers=_auth(owner_access),
        json={"manufacturer_id": str(manufacturer.id), "name": "Nope"},
    )

    assert listed.status_code == 403
    assert created.status_code == 403
    assert await db_session.scalar(select(func.count()).select_from(Decor)) == 0
