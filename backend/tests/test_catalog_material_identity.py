"""Catalog identity after the dekor reshape.

Identity (who makes it, what it is, what it is called) is platform-owned and
lives on `dekorlar`; format (thickness, sheet/tape size) is branch-owned and
lives on `branch_materials`. There is no stored name on either — every display
string is composed by `app/core/material_label.py`, so these tests assert the
composed `label` rather than a `name` column.
"""

import uuid
from decimal import Decimal

import pytest
from app.models.enums import AuthenticatedPrincipalType, DekorType
from app.modules.access.api import create_session
from app.modules.catalog.contracts import BranchMaterial, Dekor, Manufacturer
from httpx import AsyncClient
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_dekor, seed_platform_user, seed_workshop_with_owner

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


async def test_dekor_create_composes_its_label_from_identity_alone(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A dekor has no format, so its label carries no dimensions.

    This is the identity slot of the same formatter the branch material and the
    frozen order snapshot use — the dimensions arrive only once a branch says
    what format it sells.
    """
    access = await _platform_access(db_session)
    manufacturer_id = await _manufacturer(client, access)

    kromka = await client.post(
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(access),
        json={
            "manufacturer_id": manufacturer_id,
            "tur": "kromka",
            "kod": "H1145",
            "nomi": "Sonoma eman",
        },
    )
    panel = await client.post(
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(access),
        json={
            "manufacturer_id": manufacturer_id,
            "tur": "ldsp",
            "kod": "H1334 ST9",
            "nomi": "Sonoma eman",
            "tolali": True,
        },
    )
    unnamed_code = await client.post(
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(access),
        json={"manufacturer_id": manufacturer_id, "tur": "mdf", "nomi": "Oq"},
    )
    missing_name = await client.post(
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(access),
        json={"manufacturer_id": manufacturer_id, "tur": "ldsp", "kod": "X1", "nomi": "   "},
    )

    assert kromka.status_code == 201, kromka.text
    assert kromka.json()["label"] == "Egger H1145 · Sonoma eman"
    assert panel.status_code == 201
    assert panel.json()["label"] == "LDSP Egger H1334 ST9 · Sonoma eman"
    assert panel.json()["tolali"] is True
    # No kod: the name fills the identity slot and must not repeat as a detail.
    assert unnamed_code.status_code == 201
    assert unnamed_code.json()["label"] == "MDF Egger Oq"
    assert missing_name.status_code == 400
    assert missing_name.json()["code"] == "dekor_nomi_required"
    # The platform surface carries no format and no price at all.
    for key in ("qalinlik_mm", "uzunlik_mm", "eni_mm", "kromka_eni_mm", "price_tiyin"):
        assert key not in panel.json()


async def test_dekor_uniqueness_is_by_code_then_by_name(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Two decors of one maker are the same decor when their codes match.

    When neither has a code the name is the identity instead. Both rules are
    per `tur`: a kromka H1334 and an LDSP H1334 are different things.
    """
    access = await _platform_access(db_session)
    egger = await _manufacturer(client, access, "Egger Unique")
    kronospan = await _manufacturer(client, access, "Kronospan Unique")

    async def create(manufacturer_id: str, tur: str, kod: str | None, nomi: str) -> int:
        response = await client.post(
            "/api/v1/platform/catalog/dekorlar",
            headers=_auth(access),
            json={"manufacturer_id": manufacturer_id, "tur": tur, "kod": kod, "nomi": nomi},
        )
        return response.status_code

    assert await create(egger, "ldsp", "H1334", "Sonoma") == 201
    # Same maker, same tur, same code (case-insensitively) — a duplicate.
    assert await create(egger, "ldsp", "h1334", "Boshqa nom") == 409
    # A different tur is a different dekor.
    assert await create(egger, "kromka", "H1334", "Sonoma") == 201
    # A different maker is a different dekor.
    assert await create(kronospan, "ldsp", "H1334", "Sonoma") == 201
    # Code-less rows fall back to the name.
    assert await create(egger, "mdf", None, "Oq") == 201
    assert await create(egger, "mdf", None, "oq") == 409
    assert await create(egger, "mdf", None, "Qora") == 201


async def test_dekor_patch_updates_identity_and_refreshes_the_search_key(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access = await _platform_access(db_session)
    egger = await _manufacturer(client, access, "Egger Patch")
    kronospan = await _manufacturer(client, access, "Kronospan Patch")
    created = await client.post(
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(access),
        json={"manufacturer_id": egger, "tur": "kromka", "kod": "H1334", "nomi": "Oak"},
    )
    assert created.status_code == 201
    dekor_id = created.json()["id"]

    patched = await client.patch(
        f"/api/v1/platform/catalog/dekorlar/{dekor_id}",
        headers=_auth(access),
        json={"manufacturer_id": kronospan, "nomi": "White"},
    )
    assert patched.status_code == 200
    assert patched.json()["label"] == "Kronospan Patch H1334 · White"

    # The search key is rebuilt on every write, so the new maker and name are
    # both findable straight away.
    by_new_name = await client.get(
        "/api/v1/platform/catalog/dekorlar?search=white", headers=_auth(access)
    )
    by_new_manufacturer = await client.get(
        "/api/v1/platform/catalog/dekorlar?search=kronospan", headers=_auth(access)
    )
    by_old_name = await client.get(
        "/api/v1/platform/catalog/dekorlar?search=oak", headers=_auth(access)
    )
    assert [row["id"] for row in by_new_name.json()] == [dekor_id]
    assert [row["id"] for row in by_new_manufacturer.json()] == [dekor_id]
    assert by_old_name.json() == []


async def test_renaming_a_manufacturer_rebuilds_its_dekorlar_search_keys(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The maker name is folded into every dekor's search key.

    Renaming the manufacturer without a backfill would leave every one of its
    decors findable only under the old name — silently, with no error.
    """
    access = await _platform_access(db_session)
    manufacturer_id = await _manufacturer(client, access, "Oldname")
    created = await client.post(
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(access),
        json={"manufacturer_id": manufacturer_id, "tur": "ldsp", "kod": "H1", "nomi": "Sonoma"},
    )
    assert created.status_code == 201

    renamed = await client.patch(
        f"/api/v1/platform/catalog/manufacturers/{manufacturer_id}",
        headers=_auth(access),
        json={"name": "Newname"},
    )
    assert renamed.status_code == 200

    by_new = await client.get(
        "/api/v1/platform/catalog/dekorlar?search=newname", headers=_auth(access)
    )
    by_old = await client.get(
        "/api/v1/platform/catalog/dekorlar?search=oldname", headers=_auth(access)
    )
    assert [row["id"] for row in by_new.json()] == [created.json()["id"]]
    assert by_old.json() == []


async def test_dekor_search_is_script_and_apostrophe_insensitive(
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
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(access),
        json={
            "manufacturer_id": manufacturer_id,
            "tur": "ldsp",
            "kod": "H1334",
            "nomi": "Yong'oq",
        },
    )
    assert created.status_code == 201
    dekor_id = created.json()["id"]

    for query in ["yong'oq", "yongoq", "yongok", "ёнғоқ", "H1334", "h1334", "эггер ёнғоқ"]:
        found = await client.get(
            "/api/v1/platform/catalog/dekorlar", headers=_auth(access), params={"search": query}
        )
        assert found.status_code == 200
        assert [row["id"] for row in found.json()] == [dekor_id], query

    missing = await client.get(
        "/api/v1/platform/catalog/dekorlar", headers=_auth(access), params={"search": "sonoma"}
    )
    assert missing.json() == []


async def test_branch_material_label_adds_the_format_the_branch_carries(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The dimensions in a label come from the branch row, not the dekor.

    Byte-for-byte the format the old `Material.name` column stored — the label
    module's own unit tests are the lock on that; this asserts the two halves
    are wired together correctly.
    """
    platform_access = await _platform_access(db_session)
    owner_access, branch_id = await _owner_access(db_session)
    manufacturer_id = await _manufacturer(client, platform_access, "Egger Format")
    panel = await client.post(
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(platform_access),
        json={
            "manufacturer_id": manufacturer_id,
            "tur": "ldsp",
            "kod": "H1334 ST9",
            "nomi": "Sonoma eman",
        },
    )
    kromka = await client.post(
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(platform_access),
        json={"manufacturer_id": manufacturer_id, "tur": "kromka", "kod": None, "nomi": "Oq"},
    )

    panel_row = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={
            "dekor_id": panel.json()["id"],
            "formats": [{"qalinlik_mm": "18", "uzunlik_mm": 2750, "eni_mm": 1830}],
        },
    )
    kromka_row = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={
            "dekor_id": kromka.json()["id"],
            "formats": [{"qalinlik_mm": "2", "kromka_eni_mm": 36}],
        },
    )

    assert panel_row.status_code == 201, panel_row.text
    assert (
        panel_row.json()["created"][0]["label"]
        == f"LDSP Egger Format H1334 ST9 · Sonoma eman · 2750{SEP}1830{SEP}18 mm"
    )
    assert kromka_row.status_code == 201
    # No kod: `Oq` fills the identity slot and is suppressed from the detail.
    assert kromka_row.json()["created"][0]["label"] == f"Egger Format Oq · 2{SEP}36 mm"


async def test_one_dekor_fans_out_to_many_branch_formats(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The whole point of the split: one identity, many formats per branch.

    A 16 mm and an 18 mm sheet of one decor are different things to cut, stock
    and price, so each is its own row — but they share one dekor and one photo.
    """
    platform_access = await _platform_access(db_session)
    owner_access, branch_id = await _owner_access(db_session)
    manufacturer_id = await _manufacturer(client, platform_access, "Egger Fanout")
    dekor = await client.post(
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(platform_access),
        json={"manufacturer_id": manufacturer_id, "tur": "ldsp", "kod": "H1", "nomi": "Sonoma"},
    )
    attached = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={
            "dekor_id": dekor.json()["id"],
            "formats": [
                {"qalinlik_mm": "18", "uzunlik_mm": 2750, "eni_mm": 1830, "price_tiyin": 250_000},
                {"qalinlik_mm": "16", "uzunlik_mm": 2750, "eni_mm": 1830, "price_tiyin": 220_000},
                {"qalinlik_mm": "18", "uzunlik_mm": 2800, "eni_mm": 2070, "price_tiyin": 260_000},
            ],
        },
    )

    assert attached.status_code == 201, attached.text
    rows = attached.json()["created"]
    assert len(rows) == 3
    assert {row["dekor_id"] for row in rows} == {dekor.json()["id"]}
    # Every row renders its own dimensions, so the operator can tell them apart.
    assert len({row["label"] for row in rows}) == 3

    by_dekor = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/materials?dekor_id={dekor.json()['id']}",
        headers=_auth(owner_access),
    )
    assert len(by_dekor.json()) == 3


async def test_branch_material_patch_revalidates_the_merged_format(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Stock, panels and order items FK this row.

    Delete-and-reattach is therefore not a fix path for a mistyped sheet size,
    so PATCH accepts the format fields — and must re-check the shape rule
    against the *merged* result, not just the fields that were sent.
    """
    platform_access = await _platform_access(db_session)
    owner_access, branch_id = await _owner_access(db_session)
    manufacturer_id = await _manufacturer(client, platform_access, "Egger Patchfmt")
    dekor = await client.post(
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(platform_access),
        json={"manufacturer_id": manufacturer_id, "tur": "ldsp", "kod": "H1", "nomi": "Sonoma"},
    )
    attached = await client.post(
        f"/api/v1/workshop/branches/{branch_id}/materials",
        headers=_auth(owner_access),
        json={
            "dekor_id": dekor.json()["id"],
            "formats": [
                {"qalinlik_mm": "18", "uzunlik_mm": 2750, "eni_mm": 1830},
                {"qalinlik_mm": "16", "uzunlik_mm": 2750, "eni_mm": 1830},
            ],
        },
    )
    rows = attached.json()["created"]
    first = next(row for row in rows if row["qalinlik_mm"] == "18")
    second = next(row for row in rows if row["qalinlik_mm"] == "16")

    resized = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}/materials/{first['id']}",
        headers=_auth(owner_access),
        json={"uzunlik_mm": 2800, "eni_mm": 2070},
    )
    # A panel cannot grow a tape width, even one field at a time.
    bad_shape = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}/materials/{first['id']}",
        headers=_auth(owner_access),
        json={"kromka_eni_mm": 19},
    )
    # Patching onto a format the branch already carries is a conflict.
    collision = await client.patch(
        f"/api/v1/workshop/branches/{branch_id}/materials/{second['id']}",
        headers=_auth(owner_access),
        json={"qalinlik_mm": "18", "uzunlik_mm": 2800, "eni_mm": 2070},
    )

    assert resized.status_code == 200, resized.text
    assert resized.json()["uzunlik_mm"] == 2800
    assert resized.json()["eni_mm"] == 2070
    assert resized.json()["id"] == first["id"]
    assert bad_shape.status_code == 400
    assert bad_shape.json()["code"] == "invalid_panel_format"
    assert collision.status_code == 409
    assert collision.json()["code"] == "branch_material_exists"


async def test_branch_material_column_checks_hold_at_the_db(
    db_session: AsyncSession,
) -> None:
    """The column-local half of the shape rule is enforced by the database.

    `tur` lives on `dekorlar` and a table CHECK cannot reach it, so the DB only
    guards what it can see: a positive thickness, a positive tape width, and
    length >= width. The rest is the service layer's (see the PATCH test above).
    """
    manufacturer = Manufacturer(name=f"Constraint Maker {uuid.uuid4().hex[:6]}")
    db_session.add(manufacturer)
    await db_session.flush()
    dekor = await seed_dekor(db_session, manufacturer=manufacturer, tur=DekorType.LDSP, kod="C1")
    _, branch, _ = await seed_workshop_with_owner(db_session, login=f"c-{uuid.uuid4().hex[:6]}")

    def row(**overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "branch_id": branch.id,
            "dekor_id": dekor.id,
            "qalinlik_mm": Decimal("18"),
            "uzunlik_mm": 2750,
            "eni_mm": 1830,
        }
        return base | overrides

    for invalid in (
        row(qalinlik_mm=Decimal("0")),
        row(kromka_eni_mm=0, uzunlik_mm=None, eni_mm=None),
        row(uzunlik_mm=1830, eni_mm=2750),
        row(price_tiyin=-1),
        row(min_stock=-1),
    ):
        with pytest.raises(IntegrityError):
            await db_session.execute(insert(BranchMaterial).values(**invalid))
            await db_session.flush()
        await db_session.rollback()


async def test_dekor_deactivation_hides_it_from_the_branch_picker(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    platform_access = await _platform_access(db_session)
    owner_access, branch_id = await _owner_access(db_session)
    manufacturer_id = await _manufacturer(client, platform_access, "Egger Status")
    dekor = await client.post(
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(platform_access),
        json={"manufacturer_id": manufacturer_id, "tur": "ldsp", "kod": "H1", "nomi": "Sonoma"},
    )
    dekor_id = dekor.json()["id"]

    visible = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/dekorlar", headers=_auth(owner_access)
    )
    deactivated = await client.post(
        f"/api/v1/platform/catalog/dekorlar/{dekor_id}/deactivate",
        headers=_auth(platform_access),
    )
    hidden = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/dekorlar", headers=_auth(owner_access)
    )
    reactivated = await client.post(
        f"/api/v1/platform/catalog/dekorlar/{dekor_id}/activate",
        headers=_auth(platform_access),
    )
    visible_again = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/dekorlar", headers=_auth(owner_access)
    )

    assert [row["dekor"]["id"] for row in visible.json()["items"]] == [dekor_id]
    assert deactivated.status_code == 200
    assert deactivated.json()["holat"] == "inactive"
    assert hidden.json() == {"items": [], "total": 0}
    assert reactivated.status_code == 200
    assert [row["dekor"]["id"] for row in visible_again.json()["items"]] == [dekor_id]


async def test_dekor_writes_are_platform_only(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_access, _ = await _owner_access(db_session)
    manufacturer = Manufacturer(name=f"Locked {uuid.uuid4().hex[:6]}")
    db_session.add(manufacturer)
    await db_session.flush()

    listed = await client.get("/api/v1/platform/catalog/dekorlar", headers=_auth(owner_access))
    created = await client.post(
        "/api/v1/platform/catalog/dekorlar",
        headers=_auth(owner_access),
        json={"manufacturer_id": str(manufacturer.id), "tur": "ldsp", "nomi": "Nope"},
    )

    assert listed.status_code == 403
    assert created.status_code == 403
    assert await db_session.scalar(select(func.count()).select_from(Dekor)) == 0
