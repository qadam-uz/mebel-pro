"""The `backfill-image-variants` maintenance CLI.

What it is for: every file uploaded before renditions existed carries
`variant_keys IS NULL`, and until something fills that column a `?size=sm` read
has nothing but the original to serve. The read path renders such a file on its
first sized request now, so this command is the way to pay that cost *before*
anyone waits for it — which is what a deploy over an existing catalog does.

Covered here is the command's own logic: which rows it picks up, what it records
for each outcome, and that a store which refuses every write ends the run instead
of spinning on rows it keeps failing to settle.
"""

import io
import json
import uuid
from typing import Any

import pytest
from app import cli
from app.models import Base
from app.models.enums import AuthenticatedPrincipalType, FileStorageStatus
from app.modules.support import files as files_module
from app.modules.support.contracts import File as StoredFile
from app.modules.support.files import FileStorageUnavailable, InMemoryFileStorage, StoredObject
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.test_image_variants import png_bytes


class RefusingStorage(InMemoryFileStorage):
    """Reads fine, refuses every write — an object store that is down for PUTs."""

    def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        raise FileStorageUnavailable("ServiceUnavailable")


@pytest.fixture()
async def backfill_db(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> async_sessionmaker[AsyncSession]:
    """A file-backed database the CLI's own `SessionLocal` opens for itself.

    File-backed rather than in-memory because the command runs its own sessions
    on its own connections, exactly as it does in production.
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'backfill.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(cli, "SessionLocal", maker)
    return maker


async def _add_file(
    sessions: async_sessionmaker[AsyncSession],
    storage: InMemoryFileStorage,
    *,
    content: bytes,
    content_type: str = "image/png",
    name: str = "swatch.png",
    store_it: bool = True,
) -> uuid.UUID:
    """A stored file with no renditions — the pre-feature row shape."""
    key = f"uploads/{uuid.uuid4().hex}/{name}"
    if store_it:
        storage.put(key, content, content_type)
    row = StoredFile(
        storage_key=key,
        original_name=name,
        content_type=content_type,
        size_bytes=len(content),
        storage_status=FileStorageStatus.STORED,
        uploaded_by_type=AuthenticatedPrincipalType.WORKSHOP_USER,
        uploaded_by_id=uuid.uuid4(),
        variant_keys=None,
    )
    async with sessions() as db:
        db.add(row)
        await db.commit()
    return row.id


def _last_line(captured: str) -> dict[str, Any]:
    return json.loads([line for line in captured.strip().splitlines() if line][-1])


async def test_an_explicit_none_is_stored_as_sql_null_so_the_query_finds_it(
    backfill_db: async_sessionmaker[AsyncSession],
) -> None:
    """The column's `none_as_null`, pinned.

    Without it SQLAlchemy writes the JSON string `null` for a Python `None`.
    That reads back as `None` — so nothing looks wrong — but it does not match
    `IS NULL`, and the backfill would quietly skip every row whose rendition
    write failed. The flag is invisible until this test fails.
    """
    storage = InMemoryFileStorage()
    file_id = await _add_file(backfill_db, storage, content=png_bytes(300, 300))

    async with backfill_db() as db:
        found = await db.scalar(select(StoredFile.id).where(StoredFile.variant_keys.is_(None)))

    assert found == file_id


async def test_backfill_renders_and_records_every_old_image(
    backfill_db: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    storage = InMemoryFileStorage()
    monkeypatch.setattr(files_module, "file_storage", lambda: storage)
    big = await _add_file(backfill_db, storage, content=png_bytes(2160, 2160))

    await cli._backfill_image_variants(batch_size=10, limit=None)

    assert _last_line(capsys.readouterr().out) == {
        "status": "done",
        "generated": 1,
        "no_variants_needed": 0,
        "failed": 0,
    }
    async with backfill_db() as db:
        row = await db.get(StoredFile, big)
    assert row is not None
    assert set(row.variant_keys or {}) == {"sm", "md"}
    small = storage.open((row.variant_keys or {})["sm"])
    assert Image.open(io.BytesIO(small)).size == (160, 160)


async def test_an_image_too_small_to_need_a_rendition_is_marked_done(
    backfill_db: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`{}` rather than NULL: the next run must not read these bytes again."""
    storage = InMemoryFileStorage()
    monkeypatch.setattr(files_module, "file_storage", lambda: storage)
    tiny = await _add_file(backfill_db, storage, content=png_bytes(120, 120))

    await cli._backfill_image_variants(batch_size=10, limit=None)

    assert _last_line(capsys.readouterr().out)["no_variants_needed"] == 1
    async with backfill_db() as db:
        row = await db.get(StoredFile, tiny)
    assert row is not None
    assert row.variant_keys == {}


async def test_a_second_run_finds_nothing_left_to_do(
    backfill_db: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Idempotent, which is what makes it safe to run on every deploy."""
    storage = InMemoryFileStorage()
    monkeypatch.setattr(files_module, "file_storage", lambda: storage)
    await _add_file(backfill_db, storage, content=png_bytes(900, 900))

    await cli._backfill_image_variants(batch_size=10, limit=None)
    writes = len(storage.objects)
    capsys.readouterr()
    await cli._backfill_image_variants(batch_size=10, limit=None)

    assert _last_line(capsys.readouterr().out) == {
        "status": "done",
        "generated": 0,
        "no_variants_needed": 0,
        "failed": 0,
    }
    assert len(storage.objects) == writes


async def test_pdfs_are_left_alone(
    backfill_db: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    storage = InMemoryFileStorage()
    monkeypatch.setattr(files_module, "file_storage", lambda: storage)
    receipt = await _add_file(
        backfill_db,
        storage,
        content=b"%PDF-1.4 fake",
        content_type="application/pdf",
        name="receipt.pdf",
    )

    await cli._backfill_image_variants(batch_size=10, limit=None)

    assert _last_line(capsys.readouterr().out)["generated"] == 0
    async with backfill_db() as db:
        row = await db.get(StoredFile, receipt)
    assert row is not None
    # Untouched: a PDF has no rendition to record, and NULL is what says so.
    assert row.variant_keys is None


async def test_a_row_whose_bytes_are_gone_is_reported_and_ends_the_run(
    backfill_db: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failure leaves the column NULL — so the same rows come back next query.

    Without the no-progress guard this loop never terminates, which on a
    production database with one orphaned row would be a hung command.
    """
    storage = InMemoryFileStorage()
    monkeypatch.setattr(files_module, "file_storage", lambda: storage)
    orphan = await _add_file(backfill_db, storage, content=png_bytes(900, 900), store_it=False)

    await cli._backfill_image_variants(batch_size=10, limit=None)

    assert _last_line(capsys.readouterr().out) == {
        "status": "done",
        "generated": 0,
        "no_variants_needed": 0,
        "failed": 1,
    }
    async with backfill_db() as db:
        row = await db.get(StoredFile, orphan)
    assert row is not None
    assert row.variant_keys is None


async def test_a_store_that_refuses_writes_leaves_the_rows_retryable(
    backfill_db: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An outage is transient — it must not be recorded as "nothing to render"."""
    storage = RefusingStorage()
    monkeypatch.setattr(files_module, "file_storage", lambda: storage)
    key = f"uploads/{uuid.uuid4().hex}/swatch.png"
    storage.contents[key] = png_bytes(2160, 2160)
    async with backfill_db() as db:
        db.add(
            StoredFile(
                storage_key=key,
                original_name="swatch.png",
                content_type="image/png",
                size_bytes=len(storage.contents[key]),
                storage_status=FileStorageStatus.STORED,
                uploaded_by_type=AuthenticatedPrincipalType.WORKSHOP_USER,
                uploaded_by_id=uuid.uuid4(),
            )
        )
        await db.commit()

    await cli._backfill_image_variants(batch_size=10, limit=None)

    assert _last_line(capsys.readouterr().out)["failed"] == 1
    async with backfill_db() as db:
        rows = list((await db.scalars(select(StoredFile))).all())
    assert [row.variant_keys for row in rows] == [None]
