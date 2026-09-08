"""The workshop writes what the library lacks — and only it can see what it wrote.

The platform catalog stopped being an authority on 2026-09-07 and became a
library: a pre-filled list so a workshop does not type Egger's 300 decors by
hand. A workshop may add a manufacturer, a decor or a format the library lacks,
and the row is stamped with its `workshop_id`.

Four rules carry the whole design, and every one of them is a data-leak or a
data-loss bug if it slips:

1. **Isolation.** `visible_to(ws) := workshop_id IS NULL OR workshop_id = ws`, on
   the manufacturer, the decor *and* the format, in every workshop-facing read.
   Another workshop's row does not exist for this one — not listed, not
   attachable, and **404** rather than 403 by id, so the id cannot confirm that
   something is there.
2. **The library is untouched.** The admin app lists library rows only, and a
   workshop's own «Egger · H1145» must not stop the platform entering the real
   one later: the unique indexes split into ownership arms.
3. **The twin rule.** A shape the library already offers *actively* is attached,
   not duplicated (409 naming the row to tick). A shape the library has retired
   is the workshop's to write — the platform discontinued it, the workshop still
   buys it.
4. **One transaction.** A bad third format leaves no decor, no manufacturer and
   no audit rows: the operator retypes one size, not the whole form.
"""

import uuid
from typing import Any

from app.models.enums import AuthenticatedPrincipalType
from app.modules.access.api import create_session
from app.modules.access.contracts import Client
from app.modules.catalog.contracts import Decor, DecorFormat, Manufacturer
from app.modules.support.contracts import ActionLog
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_platform_user, seed_workshop_with_owner

BOARD: dict[str, Any] = {
    "type": "ldsp",
    "thickness_mm": "18",
    "length_mm": 2800,
    "width_mm": 2070,
    "finished_sides": 2,
}
THIN_BOARD: dict[str, Any] = {**BOARD, "thickness_mm": "16"}
TAPE: dict[str, Any] = {"type": "kromka", "thickness_mm": "0.4", "tape_width_mm": 22}


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _platform_access(db: AsyncSession) -> str:
    platform = await seed_platform_user(
        db, login=f"platform-{uuid.uuid4().hex[:8]}", password_reset_required=False
    )
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        principal_id=platform.id,
    )
    return tokens.access_token


async def _owner_access(db: AsyncSession, *, login: str) -> tuple[str, uuid.UUID]:
    """One workshop's owner token and the branch every call below is scoped to."""

    _, branch, owner = await seed_workshop_with_owner(db, login=login)
    owner.password_reset_required = False
    tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    return tokens.access_token, branch.id


async def _client_access(db: AsyncSession) -> str:
    row = Client(phone=f"+99890{uuid.uuid4().int % 10**7:07d}", name="Browser")
    db.add(row)
    await db.flush()
    tokens = await create_session(
        db, principal_type=AuthenticatedPrincipalType.CLIENT, principal_id=row.id
    )
    return tokens.access_token


async def _library_decor(
    client: AsyncClient,
    access: str,
    *,
    manufacturer: str | None = None,
    code: str = "H1145",
    name: str = "Sonoma eman",
    formats: list[dict[str, Any]] | None = None,
) -> tuple[str, str, list[str]]:
    """A platform-written decor. Returns (manufacturer_id, decor_id, format_ids)."""

    maker = await client.post(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(access),
        json={"name": manufacturer or f"Egger {uuid.uuid4().hex[:6]}", "country": "AT"},
    )
    assert maker.status_code == 201, maker.text
    decor = await client.post(
        "/api/v1/platform/catalog/decors",
        headers=_auth(access),
        json={"manufacturer_id": maker.json()["id"], "code": code, "name": name},
    )
    assert decor.status_code == 201, decor.text
    format_ids = []
    for body in formats if formats is not None else [BOARD]:
        created = await client.post(
            f"/api/v1/platform/catalog/decors/{decor.json()['id']}/formats",
            headers=_auth(access),
            json=body,
        )
        assert created.status_code == 201, created.text
        format_ids.append(str(created.json()["id"]))
    return str(maker.json()["id"]), str(decor.json()["id"]), format_ids


async def _create_own_decor(
    client: AsyncClient,
    access: str,
    branch_id: uuid.UUID,
    *,
    manufacturer_name: str | None = None,
    manufacturer_id: str | None = None,
    name: str = "Oq yog'och",
    code: str | None = "K100",
    has_grain: bool = False,
    formats: list[dict[str, Any]] | None = None,
) -> Response:
    body: dict[str, Any] = {
        "name": name,
        "code": code,
        "has_grain": has_grain,
        "formats": formats if formats is not None else [BOARD],
    }
    if manufacturer_name is not None:
        body["manufacturer_name"] = manufacturer_name
    if manufacturer_id is not None:
        body["manufacturer_id"] = manufacturer_id
    return await client.post(
        f"/api/v1/workshop/branches/{branch_id}/catalog/decors",
        headers=_auth(access),
        json=body,
    )


async def _own_decor(
    client: AsyncClient, access: str, branch_id: uuid.UUID, **kwargs: Any
) -> dict[str, Any]:
    response = await _create_own_decor(client, access, branch_id, **kwargs)
    assert response.status_code == 201, response.text
    payload: dict[str, Any] = response.json()
    return payload


async def _picker_decor_ids(
    client: AsyncClient, access: str, branch_id: uuid.UUID, query: str = ""
) -> list[str]:
    response = await client.get(
        f"/api/v1/workshop/branches/{branch_id}/catalog/decors{query}", headers=_auth(access)
    )
    assert response.status_code == 200, response.text
    return [str(row["decor"]["id"]) for row in response.json()["items"]]


# --------------------------------------------------------------------------- #
# 1. Isolation
# --------------------------------------------------------------------------- #


async def test_two_workshops_never_see_each_others_catalog_rows(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The rule the whole feature rests on, across every surface that reads a decor.

    One workshop's private decor leaking into another's picker is the failure
    that turns "add what the library lacks" into a shared marketplace nobody
    asked for — so this walks the picker, its facets, the manufacturer combobox,
    the format list, the attach call and the edit call, all six.
    """

    a_access, a_branch = await _owner_access(db_session, login="owner-a")
    b_access, b_branch = await _owner_access(db_session, login="owner-b")
    created = await _own_decor(
        client, a_access, a_branch, manufacturer_name="Kastamonu", name="Oq yog'och"
    )
    decor_id = str(created["decor"]["id"])
    format_id = str(created["formats"][0]["id"])

    assert created["decor"]["own"] is True
    assert created["formats"][0]["own"] is True
    assert decor_id in await _picker_decor_ids(client, a_access, a_branch)

    # B's every read.
    assert await _picker_decor_ids(client, b_access, b_branch) == []
    b_formats = await client.get(
        f"/api/v1/workshop/branches/{b_branch}/catalog/decors/{decor_id}/formats",
        headers=_auth(b_access),
    )
    b_facets = await client.get(
        f"/api/v1/workshop/branches/{b_branch}/catalog/filters", headers=_auth(b_access)
    )
    b_makers = await client.get(
        f"/api/v1/workshop/branches/{b_branch}/catalog/manufacturers", headers=_auth(b_access)
    )
    b_attach = await client.post(
        f"/api/v1/workshop/branches/{b_branch}/materials",
        headers=_auth(b_access),
        json={"items": [{"decor_format_id": format_id, "price_tiyin": 500_000}]},
    )
    b_patch = await client.patch(
        f"/api/v1/workshop/branches/{b_branch}/catalog/decors/{decor_id}",
        headers=_auth(b_access),
        json={"name": "Stolen"},
    )

    assert b_formats.status_code == 404
    assert b_formats.json()["code"] == "decor_not_found"
    assert b_facets.json()["manufacturers"] == []
    assert [row["name"] for row in b_makers.json()] == []
    # 404, not 403: a 403 would confirm the id resolves to somebody's row.
    assert b_attach.status_code == 404, b_attach.text
    assert b_attach.json()["code"] == "decor_format_not_found"
    assert b_patch.status_code == 404
    assert b_patch.json()["code"] == "decor_not_found"


async def test_a_workshop_format_on_a_library_decor_is_invisible_to_the_other_workshop(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The common case — "Egger H1145 exists, the 16 mm does not" — and its leak.

    The decor is shared, so only the *format* predicate keeps A's 16 mm out of
    B's step two. Its available-format count has to agree, or B's picker offers a
    decor whose second step is shorter than the number beside it.
    """

    platform_access = await _platform_access(db_session)
    a_access, a_branch = await _owner_access(db_session, login="owner-a")
    b_access, b_branch = await _owner_access(db_session, login="owner-b")
    _, decor_id, [library_format] = await _library_decor(client, platform_access)

    added = await client.post(
        f"/api/v1/workshop/branches/{a_branch}/catalog/decors/{decor_id}/formats",
        headers=_auth(a_access),
        json=THIN_BOARD,
    )
    assert added.status_code == 201, added.text
    own_format = str(added.json()["id"])

    a_formats = await client.get(
        f"/api/v1/workshop/branches/{a_branch}/catalog/decors/{decor_id}/formats",
        headers=_auth(a_access),
    )
    b_formats = await client.get(
        f"/api/v1/workshop/branches/{b_branch}/catalog/decors/{decor_id}/formats",
        headers=_auth(b_access),
    )
    b_options = await client.get(
        f"/api/v1/workshop/branches/{b_branch}/catalog/decors", headers=_auth(b_access)
    )

    assert added.json()["own"] is True
    assert {str(row["decor_format"]["id"]) for row in a_formats.json()} == {
        library_format,
        own_format,
    }
    assert {str(row["decor_format"]["id"]) for row in b_formats.json()} == {library_format}
    assert b_options.json()["items"][0]["available_format_count"] == 1


# --------------------------------------------------------------------------- #
# 2. The library is untouched
# --------------------------------------------------------------------------- #


async def test_the_admin_app_lists_the_library_only_and_can_still_add_the_real_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Own rows never surface in the admin app, and never block a library write.

    A workshop typing «Kastamonu · Oq yog'och» before the platform gets round to
    it must not make that decor unenterable forever — which is exactly what one
    global unique index would do.
    """

    platform_access = await _platform_access(db_session)
    a_access, a_branch = await _owner_access(db_session, login="owner-a")
    own = await _own_decor(
        client, a_access, a_branch, manufacturer_name="Kastamonu", name="Oq yog'och", code="K100"
    )

    decors = await client.get("/api/v1/platform/catalog/decors", headers=_auth(platform_access))
    makers = await client.get(
        "/api/v1/platform/catalog/manufacturers", headers=_auth(platform_access)
    )
    fetched = await client.get(
        f"/api/v1/platform/catalog/decors/{own['decor']['id']}", headers=_auth(platform_access)
    )
    # The platform enters the same manufacturer and the same decor for real.
    library_maker, library_decor, _ = await _library_decor(
        client, platform_access, manufacturer="Kastamonu", code="K100", name="Oq yog'och"
    )

    assert [str(row["id"]) for row in decors.json()] == []
    assert [row["name"] for row in makers.json()] == []
    assert fetched.status_code == 404
    assert library_decor != str(own["decor"]["id"])
    assert library_maker != str(own["decor"]["manufacturer_id"])
    # And the library row is a library row: `own` is a fact about the reader.
    library_rows = await client.get(
        "/api/v1/platform/catalog/decors", headers=_auth(platform_access)
    )
    assert [row["own"] for row in library_rows.json()] == [False]


async def test_the_platform_cannot_deactivate_or_list_a_workshops_own_format(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """An own format hangs off a library decor the admin *can* open — so the
    format list and the deactivate button are the two doors that must still
    refuse it. Otherwise the platform silently retires a size it never wrote."""

    platform_access = await _platform_access(db_session)
    a_access, a_branch = await _owner_access(db_session, login="owner-a")
    _, decor_id, [library_format] = await _library_decor(client, platform_access)
    added = await client.post(
        f"/api/v1/workshop/branches/{a_branch}/catalog/decors/{decor_id}/formats",
        headers=_auth(a_access),
        json=THIN_BOARD,
    )
    assert added.status_code == 201, added.text

    listed = await client.get(
        f"/api/v1/platform/catalog/decors/{decor_id}/formats", headers=_auth(platform_access)
    )
    deactivate = await client.post(
        f"/api/v1/platform/catalog/decors/{decor_id}/formats/{added.json()['id']}/deactivate",
        headers=_auth(platform_access),
    )

    assert [str(row["id"]) for row in listed.json()] == [library_format]
    assert deactivate.status_code == 404
    assert deactivate.json()["code"] == "decor_format_not_found"


# --------------------------------------------------------------------------- #
# 3. The twin rule
# --------------------------------------------------------------------------- #


async def test_an_active_library_twin_is_ticked_and_a_retired_one_is_rewritten(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The whole twin ladder, in the order an operator meets it.

    Duplicating a size the library actively offers would give one physical
    product two ids in one branch's picker, so the answer is the id to tick. A
    size the library *retired* is a different fact — the platform stopped
    transcribing it, the workshop still buys it — so the workshop writes its own.
    And its own is then its own twin.
    """

    platform_access = await _platform_access(db_session)
    a_access, a_branch = await _owner_access(db_session, login="owner-a")
    _, decor_id, [library_format] = await _library_decor(client, platform_access)
    url = f"/api/v1/workshop/branches/{a_branch}/catalog/decors/{decor_id}/formats"

    active_twin = await client.post(url, headers=_auth(a_access), json=BOARD)
    assert active_twin.status_code == 409, active_twin.text
    assert active_twin.json()["code"] == "decor_format_exists"
    assert active_twin.json()["details"]["decor_format_id"] == library_format

    retired = await client.post(
        f"/api/v1/platform/catalog/decors/{decor_id}/formats/{library_format}/deactivate",
        headers=_auth(platform_access),
    )
    assert retired.status_code == 200, retired.text

    rewritten = await client.post(url, headers=_auth(a_access), json=BOARD)
    own_twin = await client.post(url, headers=_auth(a_access), json=BOARD)

    assert rewritten.status_code == 201, rewritten.text
    assert rewritten.json()["own"] is True
    assert own_twin.status_code == 409
    assert own_twin.json()["details"]["decor_format_id"] == str(rewritten.json()["id"])


async def test_one_workshops_own_format_does_not_block_another_workshops(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A 409 naming a row B cannot see would be both useless and a leak."""

    platform_access = await _platform_access(db_session)
    a_access, a_branch = await _owner_access(db_session, login="owner-a")
    b_access, b_branch = await _owner_access(db_session, login="owner-b")
    _, decor_id, _ = await _library_decor(client, platform_access)

    a_added = await client.post(
        f"/api/v1/workshop/branches/{a_branch}/catalog/decors/{decor_id}/formats",
        headers=_auth(a_access),
        json=THIN_BOARD,
    )
    b_added = await client.post(
        f"/api/v1/workshop/branches/{b_branch}/catalog/decors/{decor_id}/formats",
        headers=_auth(b_access),
        json=THIN_BOARD,
    )

    assert a_added.status_code == 201, a_added.text
    assert b_added.status_code == 201, b_added.text
    assert a_added.json()["id"] != b_added.json()["id"]


# --------------------------------------------------------------------------- #
# 4. One transaction
# --------------------------------------------------------------------------- #


async def test_a_bad_third_format_leaves_no_decor_no_manufacturer_no_audit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Everything is validated before anything is written.

    The operator typed a maker, a name and three sizes; one size is malformed.
    Writing the first two and failing would leave a half-decor they cannot see,
    cannot fix and would enter again — so the refusal has to leave the database
    exactly as it found it.
    """

    a_access, a_branch = await _owner_access(db_session, login="owner-a")

    refused = await _create_own_decor(
        client,
        a_access,
        a_branch,
        manufacturer_name="Kastamonu",
        formats=[BOARD, THIN_BOARD, {**BOARD, "length_mm": None}],
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "decor_format_shape_mismatch"
    assert await db_session.scalar(select(func.count()).select_from(Decor)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Manufacturer)) == 0
    assert await db_session.scalar(select(func.count()).select_from(DecorFormat)) == 0
    assert (
        await db_session.scalar(
            select(func.count()).select_from(ActionLog).where(ActionLog.action.like("catalog.%"))
        )
        == 0
    )


async def test_a_size_listed_twice_in_one_form_is_refused_rather_than_collapsed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Silently keeping one would show fewer rows on the price step than the
    operator typed, and they would spend the next minute looking for the third."""

    a_access, a_branch = await _owner_access(db_session, login="owner-a")

    duplicate = await _create_own_decor(
        client,
        a_access,
        a_branch,
        manufacturer_name="Kastamonu",
        # Same sheet, typed the other way round — the shape is normalized before
        # the comparison, so the orientation must not hide the duplicate.
        formats=[BOARD, {**BOARD, "length_mm": 2070, "width_mm": 2800}],
    )
    empty = await _create_own_decor(client, a_access, a_branch, formats=[])

    assert duplicate.status_code == 400, duplicate.text
    assert duplicate.json()["code"] == "decor_format_duplicate_in_request"
    assert empty.status_code == 400
    assert empty.json()["code"] == "decor_formats_required"


async def test_a_clashing_identity_names_the_decor_that_is_in_the_way(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """`decor_exists` carries the row it refused for, on both write paths.

    A bare 409 sends the operator back to the picker to work out which of 300
    rows they collided with. The label the form prints — «Bunday dekor bor:
    Kastamonu K100 · Oq yog'och» — is the whole difference between a refusal
    they can act on and one they retype their way around.
    """

    platform_access = await _platform_access(db_session)
    a_access, a_branch = await _owner_access(db_session, login="owner-a")

    first = await _own_decor(client, a_access, a_branch, manufacturer_name="Kastamonu")
    clash = await _create_own_decor(
        client,
        a_access,
        a_branch,
        manufacturer_id=str(first["decor"]["manufacturer_id"]),
        # Same maker and code, a different name: the code is the identity, so
        # this is the same decor typed twice.
        name="Oq yogoch (2)",
    )
    library_maker, library_decor, _ = await _library_decor(
        client, platform_access, manufacturer="Egger", code="H1145", name="Sonoma eman"
    )
    library_clash = await client.post(
        "/api/v1/platform/catalog/decors",
        headers=_auth(platform_access),
        json={"manufacturer_id": library_maker, "code": "h1145", "name": "Sonoma"},
    )

    assert clash.status_code == 409, clash.text
    assert clash.json()["code"] == "decor_exists"
    assert clash.json()["details"] == {
        "decor_id": str(first["decor"]["id"]),
        "decor_label": first["decor"]["label"],
    }
    # The platform operator writing into the library gets the same detail from
    # the same helper — one refusal, not two shapes of it.
    assert library_clash.status_code == 409, library_clash.text
    assert library_clash.json()["details"]["decor_id"] == library_decor
    assert library_clash.json()["details"]["decor_label"] == "Egger H1145 · Sonoma eman"


async def test_the_create_writes_one_audit_row_per_entity_and_marks_them_workshop_owned(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Every mutating use case leaves a trail; these three rows are it."""

    a_access, a_branch = await _owner_access(db_session, login="owner-a")

    await _own_decor(
        client,
        a_access,
        a_branch,
        manufacturer_name="Kastamonu",
        formats=[BOARD, TAPE],
    )

    rows = (
        await db_session.scalars(
            select(ActionLog).where(ActionLog.action.like("catalog.%")).order_by(ActionLog.action)
        )
    ).all()

    assert [row.action for row in rows] == [
        "catalog.decor_format.create",
        "catalog.decor_format.create",
        "catalog.dekor.create",
        "catalog.manufacturer.create",
    ]
    assert all((row.details or {}).get("workshop_owned") is True for row in rows)


# --------------------------------------------------------------------------- #
# 5. The inline manufacturer
# --------------------------------------------------------------------------- #


async def test_a_typed_manufacturer_reuses_the_library_row_before_minting_an_own_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """«kastamonu», «Kastamonu» and «Қастамону» are one maker, not three.

    Matching on the folded key rather than `lower()` is what stops one workshop's
    catalog forking by keyboard layout — and reaching for the library first is
    what stops the first typist shadowing a row the platform already maintains.
    """

    platform_access = await _platform_access(db_session)
    a_access, a_branch = await _owner_access(db_session, login="owner-a")
    library_maker, _, _ = await _library_decor(
        client, platform_access, manufacturer="Kastamonu", code="LIB1", name="Library decor"
    )

    reused = await _own_decor(
        client, a_access, a_branch, manufacturer_name="кастамону", name="Oq", code="K1"
    )
    minted = await _own_decor(
        client, a_access, a_branch, manufacturer_name="Shturm", name="Kul rang", code="K2"
    )
    reused_again = await _own_decor(
        client, a_access, a_branch, manufacturer_name="SHTURM", name="Qora", code="K3"
    )
    makers = await client.get(
        f"/api/v1/workshop/branches/{a_branch}/catalog/manufacturers", headers=_auth(a_access)
    )

    assert str(reused["decor"]["manufacturer_id"]) == library_maker
    assert str(minted["decor"]["manufacturer_id"]) != library_maker
    assert str(reused_again["decor"]["manufacturer_id"]) == str(minted["decor"]["manufacturer_id"])
    # Library first, then own — and the badge tells them apart.
    assert [(row["name"], row["own"]) for row in makers.json()] == [
        ("Kastamonu", False),
        ("Shturm", True),
    ]


async def test_naming_both_a_manufacturer_and_an_id_is_refused_and_so_is_naming_neither(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Honouring one half of what the operator said is worse than asking again."""

    platform_access = await _platform_access(db_session)
    a_access, a_branch = await _owner_access(db_session, login="owner-a")
    library_maker, _, _ = await _library_decor(client, platform_access)

    both = await _create_own_decor(
        client,
        a_access,
        a_branch,
        manufacturer_id=library_maker,
        manufacturer_name="Kastamonu",
    )
    neither = await _create_own_decor(client, a_access, a_branch)
    unknown = await _create_own_decor(client, a_access, a_branch, manufacturer_id=str(uuid.uuid4()))

    assert both.status_code == 400
    assert both.json()["code"] == "manufacturer_required"
    assert neither.status_code == 400
    assert neither.json()["code"] == "manufacturer_required"
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "manufacturer_not_found"


# --------------------------------------------------------------------------- #
# 6. Search, editing, and what the client sees
# --------------------------------------------------------------------------- #


async def test_an_own_decor_is_findable_by_maker_code_script_and_dimension(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The search key is built by the same formula for an own row as a library one.

    A decor nobody can find is a decor nobody attached — and the operator who
    just typed «Kastamonu» will type it again to look for it.
    """

    a_access, a_branch = await _owner_access(db_session, login="owner-a")
    created = await _own_decor(
        client,
        a_access,
        a_branch,
        manufacturer_name="Kastamonu",
        name="Oq yog'och",
        code="K100",
    )
    decor_id = str(created["decor"]["id"])

    for query in ("kastamonu", "K100", "ёғоч", "18", "ldsp"):
        assert await _picker_decor_ids(client, a_access, a_branch, f"?search={query}") == [
            decor_id
        ], query


async def test_editing_an_own_decor_rewrites_the_search_key_and_leaves_its_formats(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Formats are immutable, own or not — the edit is identity only.

    Recomputing the key is the half that rots silently: a renamed decor stays
    findable only under the name nobody types any more.
    """

    a_access, a_branch = await _owner_access(db_session, login="owner-a")
    created = await _own_decor(
        client,
        a_access,
        a_branch,
        manufacturer_name="Kastamonu",
        name="Oq yog'och",
        code="K100",
        formats=[BOARD, TAPE],
    )
    decor_id = str(created["decor"]["id"])
    format_ids = {str(row["id"]) for row in created["formats"]}

    patched = await client.patch(
        f"/api/v1/workshop/branches/{a_branch}/catalog/decors/{decor_id}",
        headers=_auth(a_access),
        json={"name": "Ko'k dengiz", "code": "K200", "has_grain": True},
    )
    formats_after = await client.get(
        f"/api/v1/workshop/branches/{a_branch}/catalog/decors/{decor_id}/formats",
        headers=_auth(a_access),
    )

    assert patched.status_code == 200, patched.text
    assert (patched.json()["name"], patched.json()["code"]) == ("Ko'k dengiz", "K200")
    assert patched.json()["has_grain"] is True
    assert patched.json()["own"] is True
    assert {str(row["decor_format"]["id"]) for row in formats_after.json()} == format_ids
    assert await _picker_decor_ids(client, a_access, a_branch, "?search=dengiz") == [decor_id]
    assert await _picker_decor_ids(client, a_access, a_branch, "?search=yogoch") == []


async def test_a_library_decor_refuses_the_workshop_edit_with_not_owned(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """403, not 404: the operator can see this row, so "not yours" is the honest
    answer — unlike another workshop's decor, whose existence must stay hidden."""

    platform_access = await _platform_access(db_session)
    a_access, a_branch = await _owner_access(db_session, login="owner-a")
    _, decor_id, _ = await _library_decor(client, platform_access, name="Sonoma eman")

    refused = await client.patch(
        f"/api/v1/workshop/branches/{a_branch}/catalog/decors/{decor_id}",
        headers=_auth(a_access),
        json={"name": "Mine now"},
    )

    assert refused.status_code == 403
    assert refused.json()["code"] == "decor_not_owned"
    stored = await db_session.scalar(select(Decor).where(Decor.id == uuid.UUID(decor_id)))
    assert stored is not None and stored.name == "Sonoma eman"


async def test_a_client_browsing_the_branch_sees_its_own_material_and_no_other_branchs(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The client portal reads through `branch_materials`, so an own row arrives
    on the shelf with no extra plumbing — and stays on that shelf only."""

    a_access, a_branch = await _owner_access(db_session, login="owner-a")
    _, b_branch = await _owner_access(db_session, login="owner-b")
    created = await _own_decor(
        client, a_access, a_branch, manufacturer_name="Kastamonu", name="Oq yog'och"
    )
    attached = await client.post(
        f"/api/v1/workshop/branches/{a_branch}/materials",
        headers=_auth(a_access),
        json={
            "items": [{"decor_format_id": str(created["formats"][0]["id"]), "price_tiyin": 500_000}]
        },
    )
    assert attached.status_code == 201, attached.text

    client_access = await _client_access(db_session)
    on_a = await client.get(
        f"/api/v1/client/branches/{a_branch}/materials", headers=_auth(client_access)
    )
    on_b = await client.get(
        f"/api/v1/client/branches/{b_branch}/materials", headers=_auth(client_access)
    )

    assert on_a.status_code == 200, on_a.text
    assert [row["name"] for row in on_a.json()] == ["Oq yog'och"]
    assert on_b.json() == []
    # The workshop's own table flags the row so it can wear the «Sizniki» chip.
    assert attached.json()["created"][0]["decor_own"] is True


async def test_an_own_material_prints_the_same_label_as_the_identical_library_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """`material_label.py` reads a snapshot, and a snapshot has no author field.

    Two rows with the same maker, code, name and dimensions must print the same
    string, or an order placed on an own material reads differently in the PDF
    from one placed on the library's.
    """

    platform_access = await _platform_access(db_session)
    a_access, a_branch = await _owner_access(db_session, login="owner-a")
    _, _, [library_format] = await _library_decor(
        client, platform_access, manufacturer="Egger", code="H1145", name="Sonoma eman"
    )
    own = await _own_decor(
        client,
        a_access,
        a_branch,
        manufacturer_name="Egger",
        code="H1145",
        name="Sonoma eman",
        formats=[THIN_BOARD],
    )

    library_label = ""
    own_label = ""
    attached = await client.post(
        f"/api/v1/workshop/branches/{a_branch}/materials",
        headers=_auth(a_access),
        json={
            "items": [
                {"decor_format_id": library_format},
                {"decor_format_id": str(own["formats"][0]["id"])},
            ]
        },
    )
    assert attached.status_code == 201, attached.text
    for row in attached.json()["created"]:
        if row["decor_format"]["thickness_mm"] == "18":
            library_label = row["label"]
        else:
            own_label = row["label"]

    assert library_label and own_label
    # Identical but for the one fact that actually differs — the thickness.
    assert own_label == library_label.replace("18 mm", "16 mm")
