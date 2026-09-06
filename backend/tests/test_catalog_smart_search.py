"""The catalog search, driven through every surface that exposes it.

One fixture catalog — the four decors the spec's canonical table is written
against — seeded once and then queried through the six real endpoints. The point
of the shape is that the *same* table of queries runs against all of them: the
whole change was collapsing six near-copies of an `ilike` into one matcher, and
the only way that stays true is a test that would fail the moment one surface
drifts.

Tier 3 (typo tolerance) needs `pg_trgm` and lives in
`test_catalog_search_postgres_trgm.py`; on SQLite it must degrade to "no rows",
which is asserted here.
"""

# ruff: noqa: RUF001 -- Cyrillic queries against Latin catalog entries are the
# entire subject.
import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal

import pytest
from app.models.enums import AuthenticatedPrincipalType, DecorType
from app.modules.access.api import create_session
from app.modules.access.contracts import Client
from app.modules.catalog.contracts import Decor, Manufacturer
from app.modules.inventory.api import ensure_stock_item_for_branch_material
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    seed_branch_material,
    seed_decor,
    seed_decor_format,
    seed_manufacturer,
    seed_platform_user,
    seed_workshop_with_owner,
)


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


class Catalog:
    """The seeded fixture, plus the tokens each surface is queried with."""

    def __init__(
        self,
        *,
        branch_id: uuid.UUID,
        platform_access: str,
        owner_access: str,
        client_access: str,
        names: dict[str, str],
    ) -> None:
        self.branch_id = branch_id
        self.platform_access = platform_access
        self.owner_access = owner_access
        self.client_access = client_access
        # branch-material id -> the decor name it belongs to, so an assertion
        # can name what it expected instead of comparing uuids.
        self.names = names

    def label(self, row_id: str) -> str:
        return self.names.get(row_id, row_id)


async def _seed_catalog(db: AsyncSession) -> Catalog:
    """Four decors from two makers — the spec's canonical table, as rows.

    Sonoma is deliberately the only one with a second format (16 mm) and the
    only one carrying a kromka, so the dimension and tape assertions have
    something to discriminate against.
    """

    platform = await seed_platform_user(
        db, login=f"p-{uuid.uuid4().hex[:8]}", password_reset_required=False
    )
    platform_tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        principal_id=platform.id,
    )
    _, branch, owner = await seed_workshop_with_owner(db)
    owner.password_reset_required = False
    owner_tokens = await create_session(
        db,
        principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        principal_id=owner.id,
    )
    browser = Client(phone=f"+99890{uuid.uuid4().int % 10**7:07d}", name="Browser")
    db.add(browser)
    await db.flush()
    client_tokens = await create_session(
        db, principal_type=AuthenticatedPrincipalType.CLIENT, principal_id=browser.id
    )

    egger = await seed_manufacturer(db, name="Egger")
    kronospan = await seed_manufacturer(db, name="Kronospan")
    names: dict[str, str] = {}

    async def carry(
        decor_name: str,
        code: str | None,
        manufacturer: Manufacturer,
        *,
        type_: DecorType = DecorType.LDSP,
        thickness: str = "18",
        length: int | None = 2800,
        width: int | None = 2070,
        tape_width: int | None = None,
        decor: Decor | None = None,
    ) -> str:
        row = decor or await seed_decor(db, manufacturer=manufacturer, code=code, name=decor_name)
        decor_format = await seed_decor_format(
            db,
            decor=row,
            type=type_,
            thickness_mm=Decimal(thickness),
            length_mm=length,
            width_mm=width,
            tape_width_mm=tape_width,
        )
        material = await seed_branch_material(
            db, branch_id=branch.id, decor_format=decor_format, price_tiyin=500_000
        )
        # Inventory lists balances, not catalog rows — without one, the stock
        # surface has nothing to search.
        await ensure_stock_item_for_branch_material(
            db, branch_id=branch.id, branch_material_id=material.id
        )
        names[str(material.id)] = decor_name
        return str(material.id)

    sonoma = await seed_decor(db, manufacturer=egger, code="H1145", name="Sonoma eman")
    await carry("Sonoma eman", "H1145", egger, decor=sonoma)
    await carry(
        "Sonoma eman",
        "H1145",
        egger,
        decor=sonoma,
        thickness="16",
        length=2750,
        width=1830,
    )
    await carry(
        "Sonoma eman",
        "H1145",
        egger,
        decor=sonoma,
        type_=DecorType.KROMKA,
        thickness="2",
        length=None,
        width=None,
        tape_width=19,
    )
    await carry("Yong'oq", "H3734", egger)
    await carry("Kulrang eman", "H1137", egger)
    await carry("Oq", "W980", kronospan)
    # The trap both ranking cases need: a name that *contains* `son` mid-word and
    # carries somebody else's code as one of its own words.
    await carry("Mason H1145 nusxa", None, kronospan)
    await db.flush()

    return Catalog(
        branch_id=branch.id,
        platform_access=platform_tokens.access_token,
        owner_access=owner_tokens.access_token,
        client_access=client_tokens.access_token,
        names=names,
    )


# --------------------------------------------------------------------------- #
# The six surfaces, as "search this and tell me which decors came back"
# --------------------------------------------------------------------------- #

Surface = Callable[[AsyncClient, Catalog, str], Awaitable[list[str]]]


async def _platform_decors(client: AsyncClient, catalog: Catalog, query: str) -> list[str]:
    response = await client.get(
        "/api/v1/platform/catalog/decors",
        headers=_auth(catalog.platform_access),
        params={"search": query},
    )
    assert response.status_code == 200, response.text
    return [str(row["name"]) for row in response.json()]


async def _branch_materials(client: AsyncClient, catalog: Catalog, query: str) -> list[str]:
    response = await client.get(
        f"/api/v1/workshop/branches/{catalog.branch_id}/materials",
        headers=_auth(catalog.owner_access),
        params={"search": query},
    )
    assert response.status_code == 200, response.text
    return [catalog.label(str(row["id"])) for row in response.json()]


async def _attach_picker(client: AsyncClient, catalog: Catalog, query: str) -> list[str]:
    response = await client.get(
        f"/api/v1/workshop/branches/{catalog.branch_id}/catalog/decors",
        headers=_auth(catalog.owner_access),
        params={"search": query},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == len(body["items"]), "the total must describe the tier it returned"
    return [str(row["decor"]["name"]) for row in body["items"]]


async def _inventory(client: AsyncClient, catalog: Catalog, query: str) -> list[str]:
    response = await client.get(
        f"/api/v1/workshop/branches/{catalog.branch_id}/stock",
        headers=_auth(catalog.owner_access),
        params={"search": query},
    )
    assert response.status_code == 200, response.text
    return [catalog.label(str(row["branch_material_id"])) for row in response.json()]


async def _client_materials(client: AsyncClient, catalog: Catalog, query: str) -> list[str]:
    response = await client.get(
        "/api/v1/client/catalog/materials",
        headers=_auth(catalog.client_access),
        params={"branch_id": str(catalog.branch_id), "search": query},
    )
    assert response.status_code == 200, response.text
    return [str(row["name"]) for row in response.json()]


async def _client_tapes(client: AsyncClient, catalog: Catalog, query: str) -> list[str]:
    response = await client.get(
        "/api/v1/client/catalog/materials",
        headers=_auth(catalog.client_access),
        params={"branch_id": str(catalog.branch_id), "tape": "true", "search": query},
    )
    assert response.status_code == 200, response.text
    return [str(row["name"]) for row in response.json()]


DECOR_SURFACES: dict[str, Surface] = {
    "platform decor list": _platform_decors,
    "attach picker": _attach_picker,
}
FORMAT_SURFACES: dict[str, Surface] = {
    "branch materials": _branch_materials,
    "inventory": _inventory,
    "client material options": _client_materials,
}
ALL_SURFACES: dict[str, Surface] = {**DECOR_SURFACES, **FORMAT_SURFACES}


# --------------------------------------------------------------------------- #
# The canonical table
# --------------------------------------------------------------------------- #

# Every spelling of the spec's §3 table, and the decor each must reach.
CANONICAL_CASES = [
    ("sonoma", "Sonoma eman"),
    ("сонома", "Sonoma eman"),
    ("SONOMA", "Sonoma eman"),
    ("egger sonoma", "Sonoma eman"),
    ("sonoma egger", "Sonoma eman"),
    ("h1145", "Sonoma eman"),
    ("H 1145", "Sonoma eman"),
    ("h-1145", "Sonoma eman"),
    ("sonom", "Sonoma eman"),
    ("yongoq", "Yong'oq"),
    ("yong'oq", "Yong'oq"),
    ("yongok", "Yong'oq"),
    ("ёнғоқ", "Yong'oq"),
    ("yonģoq", "Yong'oq"),
    ("kulrang", "Kulrang eman"),
    ("кулранг", "Kulrang eman"),
    ("qulrang", "Kulrang eman"),
    ("oq", "Oq"),
    ("ok", "Oq"),
    ("оқ", "Oq"),
    ("w980", "Oq"),
    ("krono", "Oq"),
    # Tier 2: `Sonoma` typed with the Russian layout still on.
    ("Ыщтщьф", "Sonoma eman"),
]


@pytest.mark.parametrize("surface_name", list(ALL_SURFACES))
@pytest.mark.parametrize(("query", "expected"), CANONICAL_CASES)
async def test_the_canonical_queries_reach_their_decor_on_every_surface(
    client: AsyncClient,
    db_session: AsyncSession,
    surface_name: str,
    query: str,
    expected: str,
) -> None:
    catalog = await _seed_catalog(db_session)
    found = await ALL_SURFACES[surface_name](client, catalog, query)
    assert expected in found, f"{surface_name}: «{query}» found {found}"


@pytest.mark.parametrize("surface_name", list(ALL_SURFACES))
async def test_the_manufacturer_reaches_only_its_own_decors(
    client: AsyncClient, db_session: AsyncSession, surface_name: str
) -> None:
    """«эггер» is a query, and it is not a query for everything."""

    catalog = await _seed_catalog(db_session)
    found = await ALL_SURFACES[surface_name](client, catalog, "эггер")
    assert "Sonoma eman" in found
    assert "Oq" not in found


@pytest.mark.parametrize("surface_name", list(ALL_SURFACES))
async def test_tokens_are_anded_not_ored(
    client: AsyncClient, db_session: AsyncSession, surface_name: str
) -> None:
    """A query that names two makers names no decor."""

    catalog = await _seed_catalog(db_session)
    assert await ALL_SURFACES[surface_name](client, catalog, "egger kronospan") == []
    assert await ALL_SURFACES[surface_name](client, catalog, "sonoma kronospan") == []


@pytest.mark.parametrize("surface_name", list(ALL_SURFACES))
async def test_the_substrate_word_is_searchable(
    client: AsyncClient, db_session: AsyncSession, surface_name: str
) -> None:
    """«лдсп» works because the decor's active format types are in its key."""

    catalog = await _seed_catalog(db_session)
    assert "Sonoma eman" in await ALL_SURFACES[surface_name](client, catalog, "лдсп")
    assert "Sonoma eman" in await ALL_SURFACES[surface_name](client, catalog, "ldsp sonoma")


# --------------------------------------------------------------------------- #
# Dimensions by value
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("surface_name", list(FORMAT_SURFACES))
async def test_a_number_matches_the_dimension_it_is_not_a_substring_of_it(
    client: AsyncClient, db_session: AsyncSession, surface_name: str
) -> None:
    catalog = await _seed_catalog(db_session)
    surface = FORMAT_SURFACES[surface_name]

    # `18` finds the 18 mm rows — every decor carries one — and never the 1830
    # mm width, which a `LIKE '%18%'` could not tell apart.
    eighteen = await surface(client, catalog, "18")
    assert sorted(eighteen) == [
        "Kulrang eman",
        "Mason H1145 nusxa",
        "Oq",
        "Sonoma eman",
        "Yong'oq",
    ]

    # `1830` is a width only the 16 mm Sonoma sheet has.
    assert await surface(client, catalog, "1830") == ["Sonoma eman"]

    # A pair is a sheet size, in either orientation.
    assert await surface(client, catalog, "2750x1830") == ["Sonoma eman"]
    assert await surface(client, catalog, "1830×2750") == ["Sonoma eman"]
    assert await surface(client, catalog, "2750*1830") == ["Sonoma eman"]

    # And it narrows with a word, which is the whole reason tokens are ANDed.
    assert await surface(client, catalog, "sonoma 16") == ["Sonoma eman"]
    assert await surface(client, catalog, "yongoq 16") == []


async def test_a_decor_list_matches_a_number_through_its_formats(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """One table up, `18` means "sells an 18 mm format"."""

    catalog = await _seed_catalog(db_session)
    assert sorted(await _attach_picker(client, catalog, "18")) == [
        "Kulrang eman",
        "Mason H1145 nusxa",
        "Oq",
        "Sonoma eman",
        "Yong'oq",
    ]
    assert await _attach_picker(client, catalog, "2800x2070 sonoma") == ["Sonoma eman"]


# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #


async def test_a_word_start_outranks_a_match_in_the_middle(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The spec's «son» case: `Sonoma` starts with it, `Mason` merely contains it."""

    catalog = await _seed_catalog(db_session)
    assert await _platform_decors(client, catalog, "son") == [
        "Sonoma eman",
        "Mason H1145 nusxa",
    ]


async def test_the_code_row_outranks_a_name_that_merely_contains_the_digits(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The spec's «h1145» case: the row the code *is* beats the row that quotes it."""

    catalog = await _seed_catalog(db_session)
    assert await _platform_decors(client, catalog, "h1145") == [
        "Sonoma eman",
        "Mason H1145 nusxa",
    ]


async def test_an_empty_search_keeps_the_surface_s_own_ordering(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Relevance is constant with no query, so maker-then-name stands."""

    catalog = await _seed_catalog(db_session)
    assert await _platform_decors(client, catalog, "") == [
        # Egger's three, alphabetically, then Kronospan's two.
        "Kulrang eman",
        "Sonoma eman",
        "Yong'oq",
        "Mason H1145 nusxa",
        "Oq",
    ]


# --------------------------------------------------------------------------- #
# Tape picker and the tiers
# --------------------------------------------------------------------------- #


async def test_the_tape_picker_searches_by_the_same_rules(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The client's kromka list is the same matcher, narrowed to tape formats."""

    catalog = await _seed_catalog(db_session)
    assert await _client_tapes(client, catalog, "сонома") == ["Sonoma eman"]
    assert await _client_tapes(client, catalog, "h1145") == ["Sonoma eman"]
    assert await _client_tapes(client, catalog, "kromka") == ["Sonoma eman"]
    # A decor with no tape format is not in this list whatever you type.
    assert await _client_tapes(client, catalog, "yongoq") == []
    # 19 mm is the tape's width; 18 is a board thickness no tape has.
    assert await _client_tapes(client, catalog, "19") == ["Sonoma eman"]
    assert await _client_tapes(client, catalog, "18") == []


@pytest.mark.parametrize("surface_name", list(ALL_SURFACES))
async def test_a_typo_finds_nothing_where_the_extension_is_absent(
    client: AsyncClient, db_session: AsyncSession, surface_name: str
) -> None:
    """SQLite cannot run `pg_trgm`, so tier 3 must be skipped, not attempted.

    Degrading to "no rows found" is the contract; the Postgres suite proves the
    tier actually works where the extension exists.
    """

    catalog = await _seed_catalog(db_session)
    assert await ALL_SURFACES[surface_name](client, catalog, "sanoma") == []


async def test_the_layout_tier_only_runs_when_the_first_found_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """«oq» is a real decor *and* maps to «щ» — the real hit has to win.

    `Yong'oq` folds to `yongok` and legitimately contains the query, so it comes
    along as a weaker (mid-word) match. What must not happen is the swapped
    query replacing both.
    """

    catalog = await _seed_catalog(db_session)
    assert await _platform_decors(client, catalog, "oq") == ["Oq", "Yong'oq"]


# --------------------------------------------------------------------------- #
# The key is a fact that has to be maintained
# --------------------------------------------------------------------------- #


async def test_a_new_format_makes_its_substrate_searchable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    catalog = await _seed_catalog(db_session)
    assert await _platform_decors(client, catalog, "mdf") == []

    kulrang = next(
        row["id"]
        for row in (
            await client.get(
                "/api/v1/platform/catalog/decors",
                headers=_auth(catalog.platform_access),
                params={"search": "kulrang"},
            )
        ).json()
    )
    created = await client.post(
        f"/api/v1/platform/catalog/decors/{kulrang}/formats",
        headers=_auth(catalog.platform_access),
        json={
            "type": "mdf",
            "thickness_mm": "16",
            "length_mm": 2800,
            "width_mm": 2070,
            "finished_sides": 2,
        },
    )
    assert created.status_code == 201, created.text

    assert await _platform_decors(client, catalog, "mdf") == ["Kulrang eman"]

    # And retiring it takes the word back out.
    retired = await client.post(
        f"/api/v1/platform/catalog/decors/{kulrang}/formats/{created.json()['id']}/deactivate",
        headers=_auth(catalog.platform_access),
    )
    assert retired.status_code == 200, retired.text
    assert await _platform_decors(client, catalog, "mdf") == []
