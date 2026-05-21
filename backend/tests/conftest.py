"""Pytest fixtures: an isolated async DB and an httpx client wired to it.

Tests run against an in-memory SQLite database (StaticPool, so the schema
survives across connections) and need no external services. Set
``DATABASE_URL`` to run the same suite against a throwaway Postgres.
"""

import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Make sure settings/engine import in test mode before app modules load.
os.environ.setdefault("ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

from app.api.deps import get_session
from app.main import app
from app.models import Base
from app.models.enums import PrincipalType
from app.services import sessions as session_service


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    # Point the app-level session factory at this test's engine too, so code
    # that opens its *own* session (the in-process scheduler, the 500 error
    # handler) shares the same schema-bearing in-memory DB instead of the real
    # one. Restored after the test.
    from app.core import db as db_module
    from app.services import scheduler as scheduler_module

    original_session_local = db_module.SessionLocal
    original_scheduler_local = scheduler_module.SessionLocal
    db_module.SessionLocal = maker
    scheduler_module.SessionLocal = maker  # scheduler bound the name at import

    async with maker() as session:
        yield session

    db_module.SessionLocal = original_session_local
    scheduler_module.SessionLocal = original_scheduler_local
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


@pytest.fixture
def auth_headers(
    db_session: AsyncSession,
) -> Callable[[PrincipalType, uuid.UUID], Awaitable[dict[str, str]]]:
    """Factory: mint a session for a principal and return Bearer auth headers."""

    async def _make(principal_type: PrincipalType, principal_id: uuid.UUID) -> dict[str, str]:
        issued = await session_service.create_session(db_session, principal_type, principal_id)
        await db_session.commit()
        return {"Authorization": f"Bearer {issued.access_token}"}

    return _make
