"""Single-redemption under real concurrency — needs Postgres row locking.

SQLite ignores `FOR UPDATE`, so the suite's default backend cannot tell a
serialized redeem from a racing one. Both halves of the handshake release
something exactly once, and both are read-modify-write: without the row lock
two in-flight requests read the same "still open" row and each grant a session.
"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.core.errors import APIError
from app.models import Base, import_all_models
from app.models.enums import AuthenticatedPrincipalType, TelegramLoginTokenStatus, UserStatus
from app.modules.access.api import (
    create_login_token,
    hash_login_code,
    poll_login_token,
    redeem_login_code,
)
from app.modules.access.contracts import Client, Session, TelegramLoginCode, TelegramLoginToken
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import_all_models()

pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_CONCURRENCY") != "1"
    or not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="set POSTGRES_CONCURRENCY=1 with a throwaway Postgres DATABASE_URL",
)

PARALLEL = 8


async def _fresh_schema() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def _drop_schema(maker: async_sessionmaker[AsyncSession]) -> None:
    engine = maker.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _seed_client(maker: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with maker() as session:
        person = Client(
            phone="+998901234567",
            name="Ali Valiyev",
            status=UserStatus.ACTIVE,
            telegram_user_id=5150,
        )
        session.add(person)
        await session.commit()
        return person.id


async def _client_session_count(maker: async_sessionmaker[AsyncSession]) -> int:
    async with maker() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(Session)
                .where(Session.principal_type == AuthenticatedPrincipalType.CLIENT)
            )
            or 0
        )


async def test_parallel_polls_of_one_confirmed_token_release_one_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    maker = await _fresh_schema()
    try:
        client_id = await _seed_client(maker)
        async with maker() as setup:
            issued = await create_login_token(setup, request_ip="203.0.113.7")
            row = await setup.scalar(select(TelegramLoginToken))
            assert row is not None
            row.status = TelegramLoginTokenStatus.CONFIRMED
            row.client_id = client_id
            row.confirmed_at = datetime.now(UTC)
            await setup.commit()

        async def poll() -> object:
            # Mirrors get_session: a fresh session per request, committed on
            # success and rolled back on failure.
            async with maker() as session:
                try:
                    result = await poll_login_token(
                        session, poll_secret=issued.poll_secret, trace_id="poll-race"
                    )
                    await session.commit()
                    return result
                except APIError as exc:
                    await session.rollback()
                    return exc

        results = await asyncio.gather(*(poll() for _ in range(PARALLEL)))

        logins = [r for r in results if getattr(r, "login", None) is not None]
        assert len(logins) == 1
        assert await _client_session_count(maker) == 1
        async with maker() as verify:
            token = await verify.scalar(select(TelegramLoginToken))
            assert token is not None
            assert token.status is TelegramLoginTokenStatus.USED
    finally:
        await _drop_schema(maker)


async def test_parallel_redeems_of_one_live_code_release_one_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_LOGIN_CODE_PEPPER", "test-pepper")
    monkeypatch.setattr(settings, "TELEGRAM_LOGIN_RATE_LIMITS_ENABLED", False)
    maker = await _fresh_schema()
    try:
        client_id = await _seed_client(maker)
        now = datetime.now(UTC)
        async with maker() as setup:
            setup.add(
                TelegramLoginCode(
                    code_hash=hash_login_code("654321"),
                    client_id=client_id,
                    expires_at=now + timedelta(minutes=5),
                    created_at=now,
                )
            )
            await setup.commit()

        async def redeem() -> object:
            async with maker() as session:
                try:
                    result = await redeem_login_code(
                        session, code="654321", request_ip="203.0.113.8", trace_id="code-race"
                    )
                    await session.commit()
                    return result
                except APIError as exc:
                    await session.rollback()
                    return exc

        results = await asyncio.gather(*(redeem() for _ in range(PARALLEL)))

        errors = [r for r in results if isinstance(r, APIError)]
        assert len(results) - len(errors) == 1
        assert {error.code for error in errors} == {"invalid_code"}
        assert await _client_session_count(maker) == 1
        async with maker() as verify:
            code_row = await verify.scalar(select(TelegramLoginCode))
            assert code_row is not None
            assert code_row.consumed_at is not None
    finally:
        await _drop_schema(maker)
