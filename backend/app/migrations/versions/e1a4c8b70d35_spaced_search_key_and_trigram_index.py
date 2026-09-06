"""Rebuild `decors.search_key` as spaced tokens, and index it for trigrams.

Two changes that only make sense together.

**The key changes shape.** It used to be `fold(name + code + manufacturer)` — one
run-on string with every separator folded away — which can answer "does this
substring occur" and nothing else. It becomes `" " + folded words + " "`, so a
word start is `LIKE '% son%'` and the relevance ranking the smart search orders
by becomes expressible in SQL. The words of the decor's **active format types**
(`ldsp`, `kromka`, …) join the key here too, which is what makes «лдсп» a query.
Every row is recomputed; the step is idempotent and can be re-run.

**`pg_trgm` arrives.** The last fallback tier of the search is typo tolerance —
`word_similarity(token, search_key)` — which needs the extension and a GIN
trigram index to run on more than a toy table. Nothing else in the schema uses
it; `app/core/search_query.py` degrades to "no rows found" where it is absent,
so a database that cannot create the extension still works, just without tier 3.

Hand-written: autogenerate sees neither a data rewrite nor an extension, and the
`gin_trgm_ops` opclass is not something it emits.

The `app.core.search_fold` import is the same coupling the earlier catalog
revisions took on deliberately: the key is rebuilt with the exact function the
service layer writes it with, so a row written here and a row written by the API
agree. Nothing from `app.modules` is imported — the model registry is not usable
from a migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from app.core.search_fold import build_search_key, fold

# revision identifiers, used by Alembic.
revision: str = "e1a4c8b70d35"
down_revision: str | None = "c4a1f70b93d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRIGRAM_INDEX = "ix_decors_search_key_trgm"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # IF NOT EXISTS so a database that already carries the extension (or a
        # re-run) is a no-op. On a managed Postgres without the extension
        # available this is the one statement that can fail — and it fails loudly
        # here rather than silently at query time.
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    rebuild_search_keys(bind)
    if bind.dialect.name == "postgresql":
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {TRIGRAM_INDEX} "
            "ON decors USING gin (search_key gin_trgm_ops)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(f"DROP INDEX IF EXISTS {TRIGRAM_INDEX}")
    # The extension is left installed: dropping it would break any other object
    # that came to depend on it, and an unused extension costs nothing.
    rebuild_search_keys(bind, spaced=False)


def rebuild_search_keys(bind: sa.engine.Connection, *, spaced: bool = True) -> None:
    """Recompute every decor's `search_key` from its own columns.

    Module-level and taking its connection so the data step can be driven
    directly in a test — the same shape the format reshape's data moves use.

    `spaced=False` writes the legacy run-on key back, which is what makes the
    downgrade a real downgrade rather than a no-op.
    """

    decors = bind.execute(sa.text("SELECT id, name, code, manufacturer_id FROM decors")).mappings()
    manufacturers = {
        row["id"]: row["name"]
        for row in bind.execute(sa.text("SELECT id, name FROM manufacturers")).mappings()
    }
    type_words: dict[object, list[str]] = {}
    for row in bind.execute(
        sa.text("SELECT DISTINCT decor_id, type FROM decor_formats WHERE status = 'active'")
    ).mappings():
        type_words.setdefault(row["decor_id"], []).append(str(row["type"]))

    updates = []
    for decor in decors:
        manufacturer_name = manufacturers.get(decor["manufacturer_id"], "")
        if spaced:
            key = build_search_key(
                decor["name"],
                decor["code"],
                manufacturer_name,
                *sorted(type_words.get(decor["id"], [])),
            )
        else:
            key = _legacy_key(decor["name"], decor["code"], manufacturer_name)
        updates.append({"decor_id": decor["id"], "search_key": key})

    if not updates:
        return
    bind.execute(
        sa.text("UPDATE decors SET search_key = :search_key WHERE id = :decor_id"),
        updates,
    )


def _legacy_key(name: str, code: str | None, manufacturer_name: str) -> str:
    """The pre-revision formula, kept here so the downgrade can restore it."""

    return fold(f"{name} {code or ''} {manufacturer_name}")
