"""The production-mode migration adds the column with no backfill behind it.

`branches.production_mode` is `simple` for every row — the ones the deploy finds
and the ones created after it. That is the decided behavior, not an oversight:
the shops that exist run on paper and never tapped the per-stage choreography,
so there was nothing mid-spine to protect, and simple is the adoption default
(orders.md). A backfill to `full` would silently opt every existing workshop out
of the flow this whole feature was built for, so the test pins its absence.
Nothing else in the suite executes a migration, so this drives it directly
against a hand-built SQLite table holding only the columns it touches.
"""

import importlib.util
import uuid
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _load_migration() -> ModuleType:
    """Import the revision by path — `app/migrations/versions` is not a package."""

    path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "migrations"
        / "versions"
        / "d3f5a9c1e846_branch_production_mode.py"
    )
    spec = importlib.util.spec_from_file_location("_migration_d3f5a9c1e846", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_migration()


def test_provisioned_and_new_branches_are_both_simple() -> None:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE branches (id TEXT PRIMARY KEY, name TEXT NOT NULL)"
        )
        for name in ("Yunusobod", "Chilonzor"):
            connection.exec_driver_sql(
                "INSERT INTO branches (id, name) VALUES (?, ?)", (str(uuid.uuid4()), name)
            )

        with Operations.context(MigrationContext.configure(connection)):
            MIGRATION.upgrade()

        provisioned = connection.exec_driver_sql(
            "SELECT production_mode FROM branches ORDER BY name"
        ).fetchall()
        # A branch created after the deploy takes the column's own default.
        connection.exec_driver_sql(
            "INSERT INTO branches (id, name) VALUES (?, ?)", (str(uuid.uuid4()), "Sergeli")
        )
        born = connection.exec_driver_sql(
            "SELECT production_mode FROM branches WHERE name = 'Sergeli'"
        ).scalar()

    # No `UPDATE branches SET production_mode = 'full'` behind the column: the
    # rows the server default filled keep it.
    assert [row[0] for row in provisioned] == ["simple", "simple"]
    assert born == "simple"
    engine.dispose()
