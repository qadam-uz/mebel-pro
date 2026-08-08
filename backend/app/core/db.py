"""Async SQLAlchemy engine, session factory and FastAPI dependency."""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _engine_options() -> dict[str, Any]:
    """Engine kwargs, with pool sizing applied only where the pool accepts it.

    The test suite runs on `sqlite+aiosqlite://`, whose pool takes none of the
    sizing arguments — passing them raises at import time, before a single test
    can run. So they are added for real database drivers only.
    """
    options: dict[str, Any] = {"echo": settings.DEBUG, "pool_pre_ping": True}
    if settings.sqlalchemy_database_uri.startswith("sqlite"):
        return options
    options.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_POOL_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    )
    return options


engine: AsyncEngine = create_async_engine(
    settings.sqlalchemy_database_uri,
    **_engine_options(),
)

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped session.

    Commits on success, rolls back on exception, always closes.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
