"""The data half of `e1a4c8b70d35`, driven directly.

Every decor in production carries a legacy run-on key. If the rebuild misses a
row, that decor stays findable only by the old substring rules — silently, with
no error anywhere — so the one thing worth proving is that a legacy key really
does become the spaced one, for rows the new formula treats differently.

Same shape as `test_catalog_format_migration.py`: the revision's data step is a
module-level function, so it can be driven against a hand-built SQLite schema.
"""

import importlib.util
import uuid
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from app.core.search_fold import build_search_key
from sqlalchemy.engine import Connection


def _load_migration() -> ModuleType:
    """Import the revision by path — `app/migrations/versions` is not a package."""

    path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "migrations"
        / "versions"
        / "e1a4c8b70d35_spaced_search_key_and_trigram_index.py"
    )
    spec = importlib.util.spec_from_file_location("_migration_e1a4c8b70d35", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_migration()

METADATA = sa.MetaData()

sa.Table(
    "manufacturers",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("name", sa.String(), nullable=False),
)
sa.Table(
    "decors",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("manufacturer_id", sa.Uuid(), nullable=False),
    sa.Column("code", sa.String(), nullable=True),
    sa.Column("name", sa.String(), nullable=False),
    sa.Column("search_key", sa.String(), nullable=False),
)
sa.Table(
    "decor_formats",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("decor_id", sa.Uuid(), nullable=False),
    sa.Column("type", sa.String(), nullable=False),
    sa.Column("status", sa.String(), nullable=False),
)

EGGER = uuid.UUID("00000000-0000-0000-0000-0000000000e1")
SONOMA = uuid.UUID("00000000-0000-0000-0000-0000000000d1")
OQ = uuid.UUID("00000000-0000-0000-0000-0000000000d2")


@pytest.fixture
def connection() -> Iterator[Connection]:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        METADATA.create_all(conn)
        conn.execute(METADATA.tables["manufacturers"].insert(), [{"id": EGGER, "name": "Egger"}])
        conn.execute(
            METADATA.tables["decors"].insert(),
            [
                {
                    "id": SONOMA,
                    "manufacturer_id": EGGER,
                    "code": "H1145",
                    "name": "Sonoma eman",
                    # Exactly what the previous revision wrote: one run-on blob.
                    "search_key": "sonomaemanh1145egger",
                },
                {
                    "id": OQ,
                    "manufacturer_id": EGGER,
                    "code": None,
                    "name": "Oq",
                    "search_key": "okegger",
                },
            ],
        )
        conn.execute(
            METADATA.tables["decor_formats"].insert(),
            [
                {"id": uuid.uuid4(), "decor_id": SONOMA, "type": "ldsp", "status": "active"},
                {"id": uuid.uuid4(), "decor_id": SONOMA, "type": "kromka", "status": "active"},
                # Retired: its word must not reach the key.
                {"id": uuid.uuid4(), "decor_id": SONOMA, "type": "mdf", "status": "inactive"},
            ],
        )
        yield conn


def _key(conn: Connection, decor_id: uuid.UUID) -> str:
    decors = METADATA.tables["decors"]
    return str(
        conn.execute(sa.select(decors.c.search_key).where(decors.c.id == decor_id)).scalar_one()
    )


def test_a_legacy_run_on_key_is_rebuilt_as_spaced_tokens(connection: Connection) -> None:
    MIGRATION.rebuild_search_keys(connection)

    rebuilt = _key(connection, SONOMA)
    assert rebuilt == build_search_key("Sonoma eman", "H1145", "Egger", "kromka", "ldsp")
    assert rebuilt.startswith(" ") and rebuilt.endswith(" ")
    # The word-start match the whole ranking rests on, which the old key could
    # not express.
    assert " sonoma" in rebuilt
    # The old key survives inside the new one only as the joined-name token, and
    # is no longer the whole key.
    assert rebuilt != "sonomaemanh1145egger"


def test_the_rebuild_carries_the_active_format_types_and_only_those(
    connection: Connection,
) -> None:
    MIGRATION.rebuild_search_keys(connection)

    rebuilt = _key(connection, SONOMA)
    assert " ldsp " in rebuilt
    assert " kromka " in rebuilt
    assert "mdf" not in rebuilt
    # A decor with no formats at all still gets a well-formed key.
    assert _key(connection, OQ) == build_search_key("Oq", None, "Egger")


def test_the_rebuild_is_idempotent(connection: Connection) -> None:
    """It runs on every deploy of this revision and on every re-run of a repair."""

    MIGRATION.rebuild_search_keys(connection)
    once = _key(connection, SONOMA)
    MIGRATION.rebuild_search_keys(connection)
    assert _key(connection, SONOMA) == once


def test_the_downgrade_restores_the_run_on_key(connection: Connection) -> None:
    MIGRATION.rebuild_search_keys(connection)
    MIGRATION.rebuild_search_keys(connection, spaced=False)
    assert _key(connection, SONOMA) == "sonomaemanh1145egger"
