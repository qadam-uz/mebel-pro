import asyncio

from app.models import Base
from app.models.enums import JobRunStatus
from app.services.scheduler import JobRegistry, RegisteredJob
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


async def test_job_registry_skips_concurrent_runs() -> None:
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    registry = JobRegistry()
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_handler(_: AsyncSession) -> str:
        started.set()
        await release.wait()
        return "finished"

    registry.register(RegisteredJob(name="demo", schedule="manual", handler=slow_handler))

    async with maker() as first_session, maker() as second_session:
        first_task = asyncio.create_task(registry.run(first_session, "demo", trace_id="trace-1"))
        await started.wait()

        skipped = await registry.run(second_session, "demo", trace_id="trace-2")
        await second_session.commit()
        release.set()
        completed = await first_task
        await first_session.commit()

    await engine.dispose()

    assert skipped.status is JobRunStatus.SKIPPED
    assert skipped.brief_log == "already running"
    assert completed.status is JobRunStatus.OK
    assert completed.brief_log == "finished"


async def test_job_registry_records_failed_runs() -> None:
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    registry = JobRegistry()

    async def failing_handler(_: AsyncSession) -> str:
        raise RuntimeError("failed job")

    registry.register(RegisteredJob(name="failing", schedule="manual", handler=failing_handler))

    async with maker() as session:
        run = await registry.run(session, "failing", trace_id="trace-failed")
        await session.commit()

    await engine.dispose()

    assert run.status is JobRunStatus.FAILED
    assert run.error_code == "job_failed"
    assert run.error_message == "failed job"
