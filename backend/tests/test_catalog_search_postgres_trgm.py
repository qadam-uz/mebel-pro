"""The catalog search against a real Postgres.

Two things SQLite cannot prove.

**Tier 3.** `word_similarity` comes from `pg_trgm`; SQLite has neither, so the
default suite can only prove the tier *degrades* (it does, in
`test_catalog_smart_search.py`). What has to be proven here is the other half:
that a typo finds the row, that it does so only after the exact tiers came up
empty, and that a query close to nothing still returns nothing.

**The SQL shapes.** SQLite accepts things Postgres rejects — an ORDER BY over
columns a GROUP BY does not cover, an ORDER BY left on a rewritten COUNT query.
The platform decor list and the attach picker do both, so every surface runs one
real search here.

Gated like the other infra suites — `POSTGRES_CONCURRENCY=1` plus a throwaway
`DATABASE_URL`; the test drops and recreates all tables. CI runs it in the
"Infra-gated tests" step.
"""

import os
import uuid
from decimal import Decimal

import pytest
from app.core.principal import AuthenticatedPrincipal
from app.core.search_query import trigram_available
from app.models import Base, import_all_models
from app.models.enums import AuthenticatedPrincipalType, DecorType
from app.modules.catalog.api import (
    list_branch_catalog_options,
    list_branch_materials,
    list_decors,
)
from app.modules.cutting.api import workshop_catalog_materials
from app.modules.inventory.api import (
    ensure_stock_item_for_branch_material,
    list_stock,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.factories import (
    seed_branch_material,
    seed_decor,
    seed_decor_format,
    seed_manufacturer,
    seed_platform_user,
    seed_workshop_with_owner,
)

import_all_models()

pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_CONCURRENCY") != "1"
    or not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="set POSTGRES_CONCURRENCY=1 with a throwaway Postgres DATABASE_URL",
)


async def test_postgres_typo_tier_finds_the_row_the_exact_tiers_missed() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        # `pg_trgm` is installed by the `before_create` listener on
        # `Base.metadata` (app/models/base.py) — every `create_all` on Postgres
        # brings its own extension, so no suite has to remember to.
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with maker() as db:
            assert await trigram_available(db) is True

            platform = await seed_platform_user(
                db, login=f"p-{uuid.uuid4().hex[:8]}", password_reset_required=False
            )
            principal = AuthenticatedPrincipal(
                principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
                principal_id=platform.id,
                session_id=uuid.uuid4(),
                trace_id=uuid.uuid4().hex,
            )
            egger = await seed_manufacturer(db, name="Egger")
            sonoma = await seed_decor(db, manufacturer=egger, code="H1145", name="Sonoma eman")
            await seed_decor_format(
                db,
                decor=sonoma,
                type=DecorType.LDSP,
                thickness_mm=Decimal("18"),
                length_mm=2800,
                width_mm=2070,
            )
            await seed_decor(db, manufacturer=egger, code="H3734", name="Yong'oq")
            await db.flush()

            async def search(query: str) -> list[str]:
                rows = await list_decors(db, principal=principal, search=query)
                return [row.decor.name for row in rows]

            # The spec's `sanoma`: one letter wrong, no exact match anywhere, and
            # the typo tier is what turns it into a result.
            assert await search("sanoma") == ["Sonoma eman"]
            # The typo tier is per token, so a query that is one good word plus
            # one misspelled one still narrows rather than widens. (Trigrams need
            # letters to work with: a wrong letter in a four-letter word is below
            # any threshold worth setting, and no tier saves it.)
            assert await search("egger sanoma") == ["Sonoma eman"]
            # An exact hit never falls through to the fuzzy tier, so it is not
            # joined by the near-misses the fuzzy tier would have admitted.
            assert await search("sonoma") == ["Sonoma eman"]
            # And a query close to nothing still finds nothing — the tier is a
            # fallback, not a "show me everything".
            assert await search("qwertyuiop") == []
            # Two real words that name no single row stay an honest empty
            # result. This is why the tier scores whole words of the key rather
            # than any extent of it: `kronospan` scored exactly at the threshold
            # against every Egger key under the looser operator.
            assert await search("egger kronospan") == []
    finally:
        await engine.dispose()


async def test_postgres_every_surface_runs_its_search_sql() -> None:
    """One real search per surface, on the dialect that actually enforces SQL.

    The assertions are deliberately thin — the *behaviour* is pinned on SQLite in
    `test_catalog_smart_search.py`. What this catches is a statement Postgres
    refuses to plan: the decor list's ranking ORDER BY over a GROUP BY, and the
    attach picker's total, which counts a query the ranking has already ordered.
    """

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with maker() as db:
            platform = await seed_platform_user(
                db, login=f"p-{uuid.uuid4().hex[:8]}", password_reset_required=False
            )
            platform_principal = AuthenticatedPrincipal(
                principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
                principal_id=platform.id,
                session_id=uuid.uuid4(),
                trace_id=uuid.uuid4().hex,
            )
            workshop, branch, owner = await seed_workshop_with_owner(db)
            owner_principal = AuthenticatedPrincipal(
                principal_type=AuthenticatedPrincipalType.WORKSHOP_USER,
                principal_id=owner.id,
                session_id=uuid.uuid4(),
                trace_id=uuid.uuid4().hex,
                workshop_id=workshop.id,
                is_owner=True,
            )
            egger = await seed_manufacturer(db, name="Egger")
            sonoma = await seed_decor(db, manufacturer=egger, code="H1145", name="Sonoma eman")
            decor_format = await seed_decor_format(
                db,
                decor=sonoma,
                type=DecorType.LDSP,
                thickness_mm=Decimal("18"),
                length_mm=2800,
                width_mm=2070,
            )
            material = await seed_branch_material(
                db, branch_id=branch.id, decor_format=decor_format, price_tiyin=500_000
            )
            await ensure_stock_item_for_branch_material(
                db, branch_id=branch.id, branch_material_id=material.id
            )
            await db.flush()

            # Ranked ORDER BY over the decor list's GROUP BY.
            decors = await list_decors(db, principal=platform_principal, search="egger sonoma")
            assert [row.decor.name for row in decors] == ["Sonoma eman"]

            # Ranked ORDER BY, then the same query rewritten as a COUNT.
            page = await list_branch_catalog_options(
                db, principal=owner_principal, branch_id=branch.id, search="sonoma 18"
            )
            assert [row.decor.name for row in page.items] == ["Sonoma eman"]
            assert page.total == 1

            materials = await list_branch_materials(
                db, principal=owner_principal, branch_id=branch.id, search="h-1145"
            )
            assert [row.decor.name for row in materials] == ["Sonoma eman"]

            stock = await list_stock(
                db,
                principal=owner_principal,
                branch_id=branch.id,
                search="\u0441\u043e\u043d\u043e\u043c\u0430",
            )
            assert [row.decor.name for row in stock] == ["Sonoma eman"]

            options = await workshop_catalog_materials(
                db,
                principal=owner_principal,
                tape=False,
                branch_id=branch.id,
                search="2800x2070",
            )
            assert [row.name for row in options] == ["Sonoma eman"]
    finally:
        await engine.dispose()
