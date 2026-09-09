"""add the lmdf decor type and narrow finished_sides to the faced boards

Two halves of one owner decision (2026-09-08, SPEC_CATALOG_ATTACH_ONE_DECOR §1):
«Yangi tur LMDF qo'shamiz. 1/2 tomonlama esa faqat LDSP va LMDF da bo'ladi.»

1. **`decor_type` gains `lmdf`** — laminated MDF, a product of its own next to
   the bare `mdf` a facade is milled and painted from. Added `AFTER 'ldsp'` so
   the Postgres type's own order matches the order the chips, filters and
   `ORDER BY decor_formats.type` put on screen: LDSP · LMDF · DSP · MDF · …
   Autogenerate never emits an enum value, so this is written by hand; and
   Postgres refuses to *use* a value added in the open transaction, so the ALTER
   runs in an `autocommit_block()` — the new CHECK below names `'lmdf'` and
   would fail with "unsafe use of new value of enum type" otherwise.

2. **`finished_sides` narrows from (ldsp, dsp, mdf) to (ldsp, lmdf).** Only a
   faced board has faces to count. A bare DSP or MDF sheet never had an answer,
   so every such row carries the meaningless «2» the format backfill wrote in
   `c4e91a7b52d0` — the value was invented, not observed. `ck_decor_formats_shape`
   is rewritten to require the count for the two faced types and forbid it for
   every other one.

**Data change** (the reason this revision is not shape-only): every `dsp` / `mdf`
format row has its `finished_sides` set to NULL. Nothing downstream reads it on
those rows — the label prints «1 tomonlama» only for a 1, and every one of these
is a 2 — and the new CHECK could not be created over them. Frozen history is NOT
touched: `order_items.material_snapshot` and `cutting_results.material_snapshots`
keep whatever they printed, which is what protects old orders and documents.

**Not fully reversible.** `downgrade()` restores the old CHECK, which means
putting the invented «2» back on the dsp/mdf rows and dropping it from the lmdf
ones — the true count of a bare sheet is not recoverable because it never
existed. Postgres cannot drop an enum value, so `lmdf` stays in the type,
unused; same asymmetry, and same reason, as b3c9f7d21a48.

Revision ID: c8e2a1f60b47
Revises: f2b7d41c908e
Create Date: 2026-09-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision: str = "c8e2a1f60b47"
down_revision: str | None = "f2b7d41c908e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SHAPE_CHECK = "ck_decor_formats_shape"

# The shape rule as this revision leaves it. Copied rather than imported: a
# frozen revision must not import code that can move under it.
NEW_SHAPE_CHECK = (
    "(type = 'kromka' AND tape_width_mm IS NOT NULL "
    "AND length_mm IS NULL AND width_mm IS NULL AND finished_sides IS NULL) "
    "OR (type <> 'kromka' AND tape_width_mm IS NULL "
    "AND length_mm IS NOT NULL AND width_mm IS NOT NULL "
    "AND length_mm >= width_mm "
    "AND ((type IN ('ldsp', 'lmdf') AND finished_sides IN (1, 2)) "
    "OR (type NOT IN ('ldsp', 'lmdf') AND finished_sides IS NULL)))"
)

# The rule as c4e91a7b52d0 wrote it, restored by `downgrade()`.
OLD_SHAPE_CHECK = (
    "(type = 'kromka' AND tape_width_mm IS NOT NULL "
    "AND length_mm IS NULL AND width_mm IS NULL AND finished_sides IS NULL) "
    "OR (type <> 'kromka' AND tape_width_mm IS NULL "
    "AND length_mm IS NOT NULL AND width_mm IS NOT NULL "
    "AND length_mm >= width_mm "
    "AND ((type IN ('ldsp', 'dsp', 'mdf') AND finished_sides IN (1, 2)) "
    "OR (type NOT IN ('ldsp', 'dsp', 'mdf') AND finished_sides IS NULL)))"
)

# The two-sided norm `c4e91a7b52d0` backfilled with, and the only value
# `downgrade()` can put back.
BACKFILL_FINISHED_SIDES = 2


# --------------------------------------------------------------------------- #
# The data step — a module-level function so a test can drive it on SQLite
# --------------------------------------------------------------------------- #


def clear_finished_sides_on_bare_boards(bind: Connection) -> int:
    """NULL `finished_sides` on every format whose type no longer carries one.

    Returns the number of rows changed, which is what the test asserts on.
    Written over the wire values rather than over the enum members: this revision
    is the moment the two disagree, and a frozen revision must not import a
    Python enum that keeps moving.
    """

    result = bind.execute(
        sa.text(
            "UPDATE decor_formats SET finished_sides = NULL "
            "WHERE finished_sides IS NOT NULL "
            "AND type IN ('dsp', 'mdf')"
        )
    )
    return result.rowcount or 0


def restore_finished_sides_for_old_rule(bind: Connection) -> None:
    """Put the pre-2026-09-08 shape back on the data, as far as it can go.

    Bare boards get the invented two-sided norm again; `lmdf` — a type the old
    rule does not know — loses its count, because the old CHECK forbids one for
    anything outside (ldsp, dsp, mdf).
    """

    bind.execute(
        sa.text(
            "UPDATE decor_formats SET finished_sides = :sides "
            "WHERE type IN ('dsp', 'mdf') AND finished_sides IS NULL"
        ),
        {"sides": BACKFILL_FINISHED_SIDES},
    )
    bind.execute(
        sa.text(
            "UPDATE decor_formats SET finished_sides = NULL "
            "WHERE type = 'lmdf' AND finished_sides IS NOT NULL"
        )
    )


# --------------------------------------------------------------------------- #
# Revision
# --------------------------------------------------------------------------- #


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Outside the migration's transaction: a value added inside it cannot be
        # named by the CHECK created below. IF NOT EXISTS so a database already
        # carrying it (a re-run, a branch merged twice) upgrades instead of
        # failing. SQLite has no enum type — its constraint is rebuilt from the
        # Python enum by `create_all` — so it skips this entirely.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE decor_type ADD VALUE IF NOT EXISTS 'lmdf' AFTER 'ldsp'")

    op.drop_constraint(_SHAPE_CHECK, "decor_formats", type_="check")
    clear_finished_sides_on_bare_boards(bind)
    op.create_check_constraint(_SHAPE_CHECK, "decor_formats", NEW_SHAPE_CHECK)


def downgrade() -> None:
    op.drop_constraint(_SHAPE_CHECK, "decor_formats", type_="check")
    restore_finished_sides_for_old_rule(op.get_bind())
    op.create_check_constraint(_SHAPE_CHECK, "decor_formats", OLD_SHAPE_CHECK)
