import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.core.errors import APIError
from app.models import Base, import_all_models
from app.modules.access.api import hash_otp_code, verify_otp_code
from app.modules.access.contracts import PhoneVerificationChallenge
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import_all_models()

pytestmark = pytest.mark.skipif(
    os.environ.get("POSTGRES_CONCURRENCY") != "1"
    or not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="set POSTGRES_CONCURRENCY=1 with a throwaway Postgres DATABASE_URL",
)


async def test_postgres_parallel_wrong_guesses_cannot_exceed_attempt_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent wrong guesses serialize on the challenge row lock (CB-133).

    Without FOR UPDATE each guess could read attempt_count=0 and overwrite the
    others' increments, granting far more than MAX_VERIFY_ATTEMPTS tries.
    """
    monkeypatch.setattr(settings, "OTP_DEV_CODES", [])
    monkeypatch.setattr(settings, "OTP_CODE_PEPPER", "test-pepper")
    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        now = datetime.now(UTC)
        async with maker() as setup:
            setup.add(
                PhoneVerificationChallenge(
                    phone="+998901234567",
                    code_hash=hash_otp_code("654321"),
                    request_ip="203.0.113.5",
                    expires_at=now + timedelta(minutes=5),
                    attempt_count=0,
                    created_at=now,
                )
            )
            await setup.commit()

        async def guess() -> object:
            # Mirrors get_session: fresh session per request, rollback on the
            # APIError — any attempt state must have been committed by the
            # service itself before raising.
            async with maker() as session:
                try:
                    await verify_otp_code(
                        session,
                        phone="+998901234567",
                        code="111111",
                        name=None,
                        trace_id="otp-concurrency",
                    )
                    await session.commit()
                    return None
                except APIError as exc:
                    await session.rollback()
                    return exc

        results = await asyncio.gather(*(guess() for _ in range(8)))
        errors = [result for result in results if isinstance(result, APIError)]

        assert len(errors) == 8
        assert {error.code for error in errors} <= {"invalid_code", "too_many_attempts"}
        async with maker() as verify:
            challenge = await verify.scalar(select(PhoneVerificationChallenge))
            assert challenge is not None
            assert challenge.attempt_count == 5
            assert challenge.consumed_at is not None
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
