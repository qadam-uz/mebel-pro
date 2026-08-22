"""The data half of the decor-format migration, driven directly.

`c4e91a7b52d0` does four things no autogenerate can express, and three of them
are one-way: it merges the board/kromka twin decors, mints one `decor_formats`
row per distinct product a branch was carrying, and lifts customer-supplied
boards out of `branch_materials` into their own table **keeping their ids**. A
mistake in any of those is silent and permanent — a merged-away decor is gone, a
re-minted board id orphans every `own_panel_counts` key, every material snapshot
and every panel that pointed at it.

That is why the migration's data steps are module-level functions rather than a
block inside `upgrade()`: they can be driven against a plain SQLite connection
with an old-shape schema built by hand, which is what this file does. It is the
only test that ever executes them.

The schema below is the database **mid-migration**, right after step 1's renames
and step 2/3's new tables and columns and right before `run_data_moves` — that
is the state the helpers are written against, so it is the state they are tested
in. It carries only the tables and columns they read or write; the real
migration's constraints and indexes are the schema's own business and are
exercised by the models' tests.
"""

import importlib.util
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Connection


def _load_migration() -> ModuleType:
    """Import the revision by path — `app/migrations/versions` is not a package."""

    path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "migrations"
        / "versions"
        / "c4e91a7b52d0_decor_formats_and_customer_boards.py"
    )
    spec = importlib.util.spec_from_file_location("_migration_c4e91a7b52d0", path)
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
    "workshops",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
)
sa.Table(
    "branches",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("workshop_id", sa.Uuid(), nullable=False),
)
sa.Table(
    "cutting_drafts",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
)
sa.Table(
    "files",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("entity_type", sa.String(), nullable=False),
    sa.Column("entity_id", sa.Uuid(), nullable=True),
)
# Already renamed from `dekorlar` by step 1 — and still carrying `type`, which
# step 5 drops only after the backfill has read it.
sa.Table(
    "decors",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("manufacturer_id", sa.Uuid(), nullable=False),
    sa.Column("type", sa.String(), nullable=False),
    sa.Column("code", sa.String(), nullable=True),
    sa.Column("name", sa.String(), nullable=False),
    sa.Column("has_grain", sa.Boolean(), nullable=False),
    sa.Column("image_file_id", sa.Uuid(), nullable=True),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("search_key", sa.String(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
# The wide pre-drop shape: the branch still owns the format, and a walk-in's
# board is still a row in here wearing `customer_supplied`.
sa.Table(
    "branch_materials",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("branch_id", sa.Uuid(), nullable=False),
    sa.Column("decor_id", sa.Uuid(), nullable=False),
    sa.Column("thickness_mm", sa.Numeric(), nullable=False),
    sa.Column("length_mm", sa.Integer(), nullable=True),
    sa.Column("width_mm", sa.Integer(), nullable=True),
    sa.Column("tape_width_mm", sa.Integer(), nullable=True),
    sa.Column("customer_supplied", sa.Boolean(), nullable=False),
    sa.Column("name", sa.String(), nullable=True),
    sa.Column("has_grain", sa.Boolean(), nullable=True),
    sa.Column("source_draft_id", sa.Uuid(), nullable=True),
    sa.Column("stock_material_id", sa.Uuid(), nullable=True),
    sa.Column("price_tiyin", sa.BigInteger(), nullable=False),
    sa.Column("min_stock", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    # Added empty by step 3; the backfill fills it.
    sa.Column("decor_format_id", sa.Uuid(), nullable=True),
)
sa.Table(
    "decor_formats",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("decor_id", sa.Uuid(), nullable=False),
    sa.Column("type", sa.String(), nullable=False),
    sa.Column("thickness_mm", sa.Numeric(), nullable=False),
    sa.Column("length_mm", sa.Integer(), nullable=True),
    sa.Column("width_mm", sa.Integer(), nullable=True),
    sa.Column("tape_width_mm", sa.Integer(), nullable=True),
    sa.Column("finished_sides", sa.SmallInteger(), nullable=True),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)
sa.Table(
    "customer_boards",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("workshop_id", sa.Uuid(), nullable=False),
    sa.Column("branch_id", sa.Uuid(), nullable=False),
    sa.Column("name", sa.String(), nullable=True),
    sa.Column("type", sa.String(), nullable=False),
    sa.Column("thickness_mm", sa.Numeric(), nullable=False),
    sa.Column("length_mm", sa.Integer(), nullable=False),
    sa.Column("width_mm", sa.Integer(), nullable=False),
    sa.Column("has_grain", sa.Boolean(), nullable=False),
    sa.Column("price_tiyin", sa.BigInteger(), nullable=False),
    sa.Column("stock_material_id", sa.Uuid(), nullable=True),
    sa.Column("source_draft_id", sa.Uuid(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
sa.Table(
    "cutting_panels",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("branch_material_id", sa.Uuid(), nullable=True),
    sa.Column("customer_board_id", sa.Uuid(), nullable=True),
)
sa.Table(
    "order_items",
    METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("branch_material_id", sa.Uuid(), nullable=True),
    sa.Column("customer_board_id", sa.Uuid(), nullable=True),
)


# The demo catalog's shape, in miniature: one manufacturer, one code, two decor
# rows — the LDSP board and its matching kromka, which the old identity rule
# (`manufacturer + tur + kod`) forced apart. The board is the one with the photo.
MANUFACTURER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
BOARD_DECOR_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b1")
TAPE_DECOR_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b2")
IMAGE_FILE_ID = uuid.UUID("00000000-0000-0000-0000-0000000000f1")
WORKSHOP_ID = uuid.UUID("00000000-0000-0000-0000-0000000000e1")
BRANCH_ID = uuid.UUID("00000000-0000-0000-0000-0000000000e2")
OTHER_BRANCH_ID = uuid.UUID("00000000-0000-0000-0000-0000000000e3")
DRAFT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000d1")

BOARD_MATERIAL_ID = uuid.UUID("00000000-0000-0000-0000-000000000101")
OTHER_BOARD_MATERIAL_ID = uuid.UUID("00000000-0000-0000-0000-000000000102")
THIN_MATERIAL_ID = uuid.UUID("00000000-0000-0000-0000-000000000103")
TAPE_MATERIAL_ID = uuid.UUID("00000000-0000-0000-0000-000000000104")
CUSTOMER_BOARD_ID = uuid.UUID("00000000-0000-0000-0000-000000000105")

PANEL_ID = uuid.UUID("00000000-0000-0000-0000-000000000201")
CUSTOMER_PANEL_ID = uuid.UUID("00000000-0000-0000-0000-000000000202")
ORDER_ITEM_ID = uuid.UUID("00000000-0000-0000-0000-000000000203")
CUSTOMER_ORDER_ITEM_ID = uuid.UUID("00000000-0000-0000-0000-000000000204")

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _insert(connection: Connection, table: str, **values: Any) -> None:
    connection.execute(sa.insert(METADATA.tables[table]).values(**values))


def _rows(connection: Connection, statement: sa.Select[Any]) -> list[Any]:
    return list(connection.execute(statement).all())


@pytest.fixture
def migrated() -> Iterator[Connection]:
    """An old-shape SQLite database with the data moves already run."""

    engine = sa.create_engine("sqlite://")
    connection = engine.connect()
    METADATA.create_all(connection)

    _insert(connection, "manufacturers", id=MANUFACTURER_ID, name="Egger")
    _insert(connection, "workshops", id=WORKSHOP_ID)
    _insert(connection, "branches", id=BRANCH_ID, workshop_id=WORKSHOP_ID)
    _insert(connection, "branches", id=OTHER_BRANCH_ID, workshop_id=WORKSHOP_ID)
    _insert(connection, "cutting_drafts", id=DRAFT_ID)
    _insert(
        connection,
        "files",
        id=IMAGE_FILE_ID,
        entity_type="material",
        entity_id=TAPE_DECOR_ID,
    )

    def decor(decor_id: uuid.UUID, type_: str, image: uuid.UUID | None) -> None:
        _insert(
            connection,
            "decors",
            id=decor_id,
            manufacturer_id=MANUFACTURER_ID,
            type=type_,
            code="H1145",
            name="Sonoma eman",
            has_grain=True,
            image_file_id=image,
            status="active",
            search_key="sonomaemanh1145egger",
            created_at=_NOW,
        )

    # The kromka row is the OLDER of the two and has no photo: the keeper rule
    # has to prefer the image over age, or the merged catalog loses its picture.
    decor(TAPE_DECOR_ID, "kromka", None)
    decor(BOARD_DECOR_ID, "ldsp", IMAGE_FILE_ID)

    def material(
        material_id: uuid.UUID,
        decor_id: uuid.UUID,
        *,
        branch_id: uuid.UUID = BRANCH_ID,
        thickness: str,
        length: int | None,
        width: int | None,
        tape_width: int | None = None,
        price: int = 100,
    ) -> None:
        _insert(
            connection,
            "branch_materials",
            id=material_id,
            branch_id=branch_id,
            decor_id=decor_id,
            thickness_mm=Decimal(thickness),
            length_mm=length,
            width_mm=width,
            tape_width_mm=tape_width,
            customer_supplied=False,
            name=None,
            has_grain=None,
            source_draft_id=None,
            stock_material_id=None,
            price_tiyin=price,
            min_stock=0,
            status="active",
            created_at=_NOW,
            updated_at=_NOW,
        )

    # Two branches carrying the IDENTICAL sheet: they must collapse onto one
    # platform format, which is the whole reason the format moved to the
    # platform. A thinner sheet of the same decor stays its own format.
    material(BOARD_MATERIAL_ID, BOARD_DECOR_ID, thickness="18", length=2800, width=2070)
    material(
        OTHER_BOARD_MATERIAL_ID,
        BOARD_DECOR_ID,
        branch_id=OTHER_BRANCH_ID,
        thickness="18",
        length=2800,
        width=2070,
        price=999,
    )
    material(THIN_MATERIAL_ID, BOARD_DECOR_ID, thickness="16", length=2800, width=2070)
    # Carried against the TWIN decor, so proving it is repointed proves the
    # merge reached the branch rows and not just the `decors` table.
    material(
        TAPE_MATERIAL_ID,
        TAPE_DECOR_ID,
        thickness="0.4",
        length=None,
        width=None,
        tape_width=22,
    )

    # A walk-in's own sheet, still living in `branch_materials`. Its substitute
    # is the branch's 18 mm row, and a panel and an order item point at it.
    _insert(
        connection,
        "branch_materials",
        id=CUSTOMER_BOARD_ID,
        branch_id=BRANCH_ID,
        decor_id=BOARD_DECOR_ID,
        thickness_mm=Decimal("18"),
        length_mm=2440,
        width_mm=1220,
        tape_width_mm=None,
        customer_supplied=True,
        name="Mijoz listi",
        has_grain=None,
        source_draft_id=DRAFT_ID,
        stock_material_id=BOARD_MATERIAL_ID,
        price_tiyin=250,
        min_stock=0,
        status="active",
        created_at=_NOW,
        updated_at=_NOW,
    )

    _insert(connection, "cutting_panels", id=PANEL_ID, branch_material_id=BOARD_MATERIAL_ID)
    _insert(
        connection,
        "cutting_panels",
        id=CUSTOMER_PANEL_ID,
        branch_material_id=CUSTOMER_BOARD_ID,
    )
    _insert(connection, "order_items", id=ORDER_ITEM_ID, branch_material_id=BOARD_MATERIAL_ID)
    _insert(
        connection,
        "order_items",
        id=CUSTOMER_ORDER_ITEM_ID,
        branch_material_id=CUSTOMER_BOARD_ID,
    )

    MIGRATION.run_data_moves(connection)
    try:
        yield connection
    finally:
        connection.close()
        engine.dispose()


def test_the_twin_decors_merge_onto_the_one_that_has_the_photo(migrated: Connection) -> None:
    """Identity lost `tur`, so the board and its kromka are one decor now.

    The keeper is the row with an image: a decor has one photo and it is the
    board row that carries it in practice. Picking the oldest instead would have
    kept the kromka here and silently dropped the catalog picture — which is why
    the tape row in the fixture is deliberately the older of the two.
    """
    decors = _rows(
        migrated,
        sa.select(METADATA.tables["decors"].c.id, METADATA.tables["decors"].c.image_file_id),
    )

    assert len(decors) == 1
    assert decors[0].id == BOARD_DECOR_ID
    assert decors[0].image_file_id == IMAGE_FILE_ID


def test_the_merged_away_decors_image_rows_follow_the_keeper(migrated: Connection) -> None:
    """`files.entity_id` is what authorizes reading a catalog photo.

    Leaving it pointing at a deleted decor id would make the image unreadable
    with no error anywhere — it would simply stop rendering.
    """
    files = METADATA.tables["files"]
    owners = _rows(migrated, sa.select(files.c.entity_id).where(files.c.entity_type == "material"))

    assert [row.entity_id for row in owners] == [BOARD_DECOR_ID]


def test_every_distinct_product_becomes_one_shared_platform_format(
    migrated: Connection,
) -> None:
    """Two branches carrying the same sheet end up on ONE format id.

    That shared id is the point of the move — it is what later makes
    cross-workshop analytics, a central price list and board-to-tape pairing
    possible at all. The formats themselves hang off the *kept* decor, so the
    tape's format proves the staged substrate survived the merge.
    """
    formats = METADATA.tables["decor_formats"]
    rows = _rows(migrated, sa.select(formats).order_by(formats.c.type, formats.c.thickness_mm))

    assert [
        (row.decor_id, row.type, Decimal(row.thickness_mm), row.length_mm, row.width_mm)
        for row in rows
    ] == [
        (BOARD_DECOR_ID, "kromka", Decimal("0.4"), None, None),
        (BOARD_DECOR_ID, "ldsp", Decimal("16"), 2800, 2070),
        (BOARD_DECOR_ID, "ldsp", Decimal("18"), 2800, 2070),
    ]
    by_key = {(row.type, Decimal(row.thickness_mm)): row for row in rows}
    # The tape kept its tape width and gained no panel size; the boards the
    # reverse. Nothing in the old schema recorded a one-sided sheet, so every
    # backfilled board is the two-sided norm and the tape has none.
    assert by_key[("kromka", Decimal("0.4"))].tape_width_mm == 22
    assert by_key[("kromka", Decimal("0.4"))].finished_sides is None
    assert by_key[("ldsp", Decimal("18"))].tape_width_mm is None
    assert by_key[("ldsp", Decimal("18"))].finished_sides == 2
    assert {row.status for row in rows} == {"active"}


def test_branch_rows_are_repointed_and_keep_their_own_prices(migrated: Connection) -> None:
    """The branch row keeps its price and threshold; only its identity moves."""
    materials = METADATA.tables["branch_materials"]
    rows = {
        row.id: row
        for row in _rows(
            migrated,
            sa.select(materials.c.id, materials.c.decor_format_id, materials.c.price_tiyin),
        )
    }

    # The customer board is gone from this table entirely.
    assert set(rows) == {
        BOARD_MATERIAL_ID,
        OTHER_BOARD_MATERIAL_ID,
        THIN_MATERIAL_ID,
        TAPE_MATERIAL_ID,
    }
    assert all(row.decor_format_id is not None for row in rows.values())
    # Two branches, one format, two prices — the branch still owns the money.
    assert rows[BOARD_MATERIAL_ID].decor_format_id == rows[OTHER_BOARD_MATERIAL_ID].decor_format_id
    assert rows[BOARD_MATERIAL_ID].price_tiyin == 100
    assert rows[OTHER_BOARD_MATERIAL_ID].price_tiyin == 999
    # A different thickness is a different product.
    assert rows[THIN_MATERIAL_ID].decor_format_id != rows[BOARD_MATERIAL_ID].decor_format_id


def test_the_customer_board_moves_out_keeping_the_same_id(migrated: Connection) -> None:
    """The id is the load-bearing part of this move.

    `own_panel_counts`, `material_snapshots` and `pricing_overrides.
    material_prices` are all dicts keyed by material-id STRING, and no FK
    protects them. Minting a new id here would leave every one of those keys
    pointing at nothing, with no error at migration time and no error at read
    time — just a draft that has forgotten how many sheets the customer brought.
    """
    boards = METADATA.tables["customer_boards"]
    rows = _rows(migrated, sa.select(boards))

    assert len(rows) == 1
    board = rows[0]
    assert board.id == CUSTOMER_BOARD_ID
    assert board.workshop_id == WORKSHOP_ID
    assert board.branch_id == BRANCH_ID
    assert board.name == "Mijoz listi"
    # The substrate came from the Mijoz-era decor the row hung off, and the
    # grain from the decor too — `tolali` was nullable on the board row.
    assert board.type == "ldsp"
    assert board.has_grain is True
    assert (board.length_mm, board.width_mm, Decimal(board.thickness_mm)) == (
        2440,
        1220,
        Decimal("18"),
    )
    # Provenance and the substitute the shortfall is billed from both survive.
    assert board.source_draft_id == DRAFT_ID
    assert board.stock_material_id == BOARD_MATERIAL_ID
    assert board.price_tiyin == 250


def test_panels_and_order_items_are_rekeyed_onto_the_board(migrated: Connection) -> None:
    """Exactly one of the two FKs is set on every row after the move.

    The final schema makes that a CHECK; the backfill has to arrive at it or the
    migration cannot add the constraint. A shop-supplied row must be untouched
    in the same pass — re-keying too much is as wrong as too little.
    """
    panels = METADATA.tables["cutting_panels"]
    items = METADATA.tables["order_items"]

    panel_rows = {row.id: row for row in _rows(migrated, sa.select(panels))}
    item_rows = {row.id: row for row in _rows(migrated, sa.select(items))}

    assert panel_rows[CUSTOMER_PANEL_ID].customer_board_id == CUSTOMER_BOARD_ID
    assert panel_rows[CUSTOMER_PANEL_ID].branch_material_id is None
    assert item_rows[CUSTOMER_ORDER_ITEM_ID].customer_board_id == CUSTOMER_BOARD_ID
    assert item_rows[CUSTOMER_ORDER_ITEM_ID].branch_material_id is None

    # The shop-supplied pair is left exactly as it was.
    assert panel_rows[PANEL_ID].branch_material_id == BOARD_MATERIAL_ID
    assert panel_rows[PANEL_ID].customer_board_id is None
    assert item_rows[ORDER_ITEM_ID].branch_material_id == BOARD_MATERIAL_ID
    assert item_rows[ORDER_ITEM_ID].customer_board_id is None

    for row in (*panel_rows.values(), *item_rows.values()):
        assert (row.branch_material_id is None) != (row.customer_board_id is None)


def test_the_run_returns_the_only_record_of_what_it_collapsed(migrated: Connection) -> None:
    """The merge map is logged because the merged-away rows no longer exist.

    Re-running the whole thing on a fresh copy is the only way to check it, so
    the summary the migration prints is the audit trail — assert its shape here
    rather than trusting a `print` nobody reads.
    """
    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        METADATA.create_all(connection)
        _insert(connection, "manufacturers", id=MANUFACTURER_ID, name="Egger")
        for decor_id, type_, image in (
            (TAPE_DECOR_ID, "kromka", None),
            (BOARD_DECOR_ID, "ldsp", IMAGE_FILE_ID),
        ):
            _insert(
                connection,
                "decors",
                id=decor_id,
                manufacturer_id=MANUFACTURER_ID,
                type=type_,
                code="H1145",
                name="Sonoma eman",
                has_grain=True,
                image_file_id=image,
                status="active",
                search_key="sonomaemanh1145egger",
                created_at=_NOW,
            )
        summary = MIGRATION.run_data_moves(connection)

    assert summary["merge_map"] == {str(TAPE_DECOR_ID): str(BOARD_DECOR_ID)}
    assert summary["formats"] == 0
    assert summary["boards"] == 0


def test_a_code_less_decor_merges_by_name_instead(migrated: Connection) -> None:
    """`boshqa` and `yogoch` decors routinely have no code at all.

    Identity falls back to the name there, case-insensitively — otherwise the
    twins the reshape exists to dissolve survive for exactly the decors whose
    names are typed by hand and therefore differ in case.
    """
    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        METADATA.create_all(connection)
        _insert(connection, "manufacturers", id=MANUFACTURER_ID, name="Egger")
        for decor_id, type_, name in (
            (TAPE_DECOR_ID, "kromka", "oq"),
            (BOARD_DECOR_ID, "ldsp", "Oq"),
        ):
            _insert(
                connection,
                "decors",
                id=decor_id,
                manufacturer_id=MANUFACTURER_ID,
                type=type_,
                code=None,
                name=name,
                has_grain=False,
                image_file_id=None,
                status="active",
                search_key="oqegger",
                created_at=_NOW,
            )
        summary = MIGRATION.run_data_moves(connection)
        remaining = _rows(connection, sa.select(METADATA.tables["decors"].c.id))

    assert len(summary["merge_map"]) == 1
    assert len(remaining) == 1
