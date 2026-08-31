"""Pytest fixtures: an isolated async DB and an httpx client wired to it.

Tests run against an in-memory SQLite database by default so they need no
external services. Set ``DATABASE_URL`` (e.g. to a throwaway Postgres) to run
the same suite against Postgres.
"""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Make sure settings/engine import in test mode before app modules load.
os.environ.setdefault("ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

from app.api.deps import get_session
from app.main import app
from app.models import Base, import_all_models
from app.modules.access.login_throttle import login_throttle
from app.modules.client_portal.api import workshop_link_throttle

import_all_models()


@pytest.fixture(autouse=True)
def _reset_ip_throttles() -> None:
    # Every IP throttle is process-global in-memory state — isolate tests.
    login_throttle.reset()
    workshop_link_throttle.reset()


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@dataclass(frozen=True)
class BoundaryHarness:
    """HTTP client with production transaction semantics + a sessionmaker for DB inspection."""

    http: AsyncClient
    sessions: async_sessionmaker[AsyncSession]


@pytest.fixture
async def boundary_client(tmp_path: Path) -> AsyncIterator[BoundaryHarness]:
    """Client whose requests cross the real commit/rollback boundary.

    Unlike ``client`` (one shared session, no commit, no rollback), each request
    gets a fresh session and the override mirrors ``app/core/db.py::get_session``
    verbatim: commit on success, rollback on any exception. State a request
    mutates before raising an APIError is only visible afterwards if the service
    persisted it deliberately — exactly the production behavior (CB-133).
    The database is file-backed so separate connections see one schema.
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'boundary.db'}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Mirror SessionLocal's configuration (app/core/db.py).
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def _override() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield BoundaryHarness(http=ac, sessions=maker)
    app.dependency_overrides.clear()
    await engine.dispose()
