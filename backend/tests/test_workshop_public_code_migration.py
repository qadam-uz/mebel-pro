"""The public-code migration backfills every workshop that already exists.

`workshops.public_code` is `nullable=False` and unique, so unlike a plain
column-add this revision has to fill the rows the deploy finds before it can
close the column — a workshop provisioned yesterday must have a working client
link the moment the deploy lands, and no two workshops may share one. Nothing
else in the suite executes a migration, so this drives it directly against a
hand-built SQLite table holding only the columns it touches.
"""

import importlib.util
import uuid
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

# I, L, O and U are absent by construction: a code has to survive being read off
# a printed sheet and typed back in.
EXCLUDED_LETTERS = set("ILOU")


def _load_migration() -> ModuleType:
    """Import the revision by path — `app/migrations/versions` is not a package."""

    path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "migrations"
        / "versions"
        / "f1c8d3a29b47_workshop_public_code.py"
    )
    spec = importlib.util.spec_from_file_location("_migration_f1c8d3a29b47", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_migration()


def _workshops_table(connection: sa.Connection, names: list[str]) -> None:
    connection.exec_driver_sql("CREATE TABLE workshops (id TEXT PRIMARY KEY, name TEXT NOT NULL)")
    for name in names:
        connection.exec_driver_sql(
            "INSERT INTO workshops (id, name) VALUES (?, ?)", (str(uuid.uuid4()), name)
        )


def test_every_existing_workshop_is_backfilled_with_a_distinct_code() -> None:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _workshops_table(connection, ["Alfa", "Beta", "Gamma"])

        with Operations.context(MigrationContext.configure(connection)):
            MIGRATION.upgrade()

        codes = [
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT public_code FROM workshops ORDER BY name"
            ).fetchall()
        ]

    assert len(codes) == 3
    assert len(set(codes)) == 3
    for code in codes:
        assert len(code) == 8
        assert set(code) <= set(MIGRATION._ALPHABET)
        assert not set(code) & EXCLUDED_LETTERS
    engine.dispose()


def test_backfilled_column_is_closed_and_unique() -> None:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _workshops_table(connection, ["Alfa"])
        with Operations.context(MigrationContext.configure(connection)):
            MIGRATION.upgrade()
        taken = connection.exec_driver_sql("SELECT public_code FROM workshops").scalar()

        # A second workshop may not reuse a code — the printed link has to name
        # exactly one shop, forever.
        with pytest.raises(sa.exc.IntegrityError):
            connection.exec_driver_sql(
                "INSERT INTO workshops (id, name, public_code) VALUES (?, ?, ?)",
                (str(uuid.uuid4()), "Beta", taken),
            )

    # And no workshop may exist without one.
    with engine.begin() as connection, pytest.raises(sa.exc.IntegrityError):
        connection.exec_driver_sql(
            "INSERT INTO workshops (id, name) VALUES (?, ?)", (str(uuid.uuid4()), "Gamma")
        )
    engine.dispose()
