"""The data half of `c8e2a1f60b47`, driven directly.

Narrowing `finished_sides` to the faced types is not a shape-only change: the
new `ck_decor_formats_shape` cannot be created over the `dsp` / `mdf` rows that
`c4e91a7b52d0` backfilled with an invented «2», so the revision NULLs them
first. Miss a row and the upgrade aborts on a production database with a CHECK
violation; over-reach and it silently erases a real one-sided LDSP, which is a
different product at a different price and unrecoverable.

Nothing else in the suite would notice either mistake: the tests build their
schema with `create_all`, so a migration only ever runs against a real database.
That is why the step is a module-level function on the revision — it can be
driven against a plain SQLite connection carrying just the columns it touches.
The enum half (`ALTER TYPE decor_type ADD VALUE 'lmdf'`) is Postgres-only DDL
with no data to assert on, and is left to the migration run itself.
"""

import importlib.util
import uuid
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from app.modules.catalog.contracts import DECOR_FORMAT_SHAPE_CHECK
from sqlalchemy.engine import Connection


def _load_migration() -> ModuleType:
    """Import the revision by path — `app/migrations/versions` is not a package."""

    path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "migrations"
        / "versions"
        / "c8e2a1f60b47_add_lmdf_and_narrow_finished_sides.py"
    )
    spec = importlib.util.spec_from_file_location("_migration_c8e2a1f60b47", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_migration()

METADATA = sa.MetaData()

# Only the columns the step reads or writes, and deliberately without the shape
# CHECK: the point of the fixture is the state the new constraint cannot yet be
# created over.
FORMATS = sa.Table(
    "decor_formats",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("type", sa.String(32), nullable=False),
    sa.Column("finished_sides", sa.SmallInteger(), nullable=True),
    sa.Column("status", sa.String(16), nullable=False),
)


@pytest.fixture
def formats() -> Iterator[Connection]:
    """Formats as the pre-2026-09-08 rule left them.

    Every board type carries a count (the old CHECK required it) and every other
    type carries none (the old CHECK forbade it). One dsp/mdf row is inactive —
    a retired format is still a row the constraint is evaluated over.
    """

    engine = sa.create_engine("sqlite://")
    connection = engine.connect()
    METADATA.create_all(connection)
    for type_, sides, status in (
        ("ldsp", 2, "active"),
        ("ldsp", 1, "active"),
        ("dsp", 2, "active"),
        ("mdf", 2, "active"),
        ("mdf", 1, "inactive"),
        ("fanera", None, "active"),
        ("kromka", None, "active"),
    ):
        connection.execute(
            sa.insert(FORMATS).values(
                id=uuid.uuid4(), type=type_, finished_sides=sides, status=status
            )
        )
    yield connection
    connection.close()
    engine.dispose()


def _by_type(connection: Connection) -> list[tuple[str, int | None]]:
    return sorted(
        (str(row.type), row.finished_sides)
        for row in connection.execute(sa.select(FORMATS.c.type, FORMATS.c.finished_sides))
    )


def test_only_the_bare_boards_lose_their_invented_face_count(formats: Connection) -> None:
    """dsp and mdf come out NULL; the one-sided LDSP must survive untouched."""

    changed = MIGRATION.clear_finished_sides_on_bare_boards(formats)

    assert changed == 3  # one dsp + two mdf, the retired one included
    assert _by_type(formats) == [
        ("dsp", None),
        ("fanera", None),
        ("kromka", None),
        ("ldsp", 1),
        ("ldsp", 2),
        ("mdf", None),
        ("mdf", None),
    ]


def test_downgrade_puts_the_old_rule_back_on_the_data(formats: Connection) -> None:
    """The old CHECK cannot be created over what `upgrade()` leaves behind.

    It demands a count on every dsp/mdf row and forbids one outside
    (ldsp, dsp, mdf) — `lmdf` included, since the old rule never heard of it.
    Restoring the *shape* without restoring that is a downgrade that aborts,
    which is the worst possible moment to find out.
    """

    formats.execute(
        sa.insert(FORMATS).values(id=uuid.uuid4(), type="lmdf", finished_sides=1, status="active")
    )
    MIGRATION.clear_finished_sides_on_bare_boards(formats)

    MIGRATION.restore_finished_sides_for_old_rule(formats)

    assert _by_type(formats) == [
        ("dsp", 2),
        ("fanera", None),
        ("kromka", None),
        ("ldsp", 1),
        ("ldsp", 2),
        ("lmdf", None),
        ("mdf", 2),
        ("mdf", 2),
    ]
    # The two-sided norm is the only value it can put back: what a bare sheet's
    # face count "really was" is not recoverable, because it never existed.
    assert MIGRATION.BACKFILL_FINISHED_SIDES == 2


def test_the_revision_and_the_model_spell_the_same_shape_rule() -> None:
    """The only link between the mapped CHECK and the one in the database.

    The suite builds its schema with `create_all`, so a model predicate that
    drifts from the migration's is green everywhere and wrong in production.
    A frozen revision keeps its own copy on purpose — but this one is the head,
    so at this moment the two must agree.
    """

    assert MIGRATION.NEW_SHAPE_CHECK == DECOR_FORMAT_SHAPE_CHECK
    assert "'lmdf'" in MIGRATION.NEW_SHAPE_CHECK
    assert "'lmdf'" not in MIGRATION.OLD_SHAPE_CHECK
