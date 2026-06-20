import asyncio

from app.models import Base, import_all_models
from app.models.enums import JobRunStatus
from app.modules.platform.contracts import JobDefinition
from app.modules.platform.scheduler import JobRegistry, RegisteredJob
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import_all_models()


async def test_job_registry_skips_concurrent_runs() -> None:
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    registry = JobRegistry()
    started = asyncio.Event()
    release = asyncio.Event()
    observed_running: bool | None = None

    async def slow_handler(session: AsyncSession) -> str:
        nonlocal observed_running
        observed_running = await session.scalar(
            select(JobDefinition.running).where(JobDefinition.name == "demo")
        )
        started.set()
        await release.wait()
        return "finished"

    registry.register(RegisteredJob(name="demo", schedule="manual", handler=slow_handler))

    async with maker() as first_session, maker() as second_session:
        first_task = asyncio.create_task(registry.run(first_session, "demo", trace_id="trace-1"))
        await started.wait()

        visible_definition = await second_session.scalar(
            select(JobDefinition).where(JobDefinition.name == "demo")
        )
        skipped = await registry.run(second_session, "demo", trace_id="trace-2")
        await second_session.commit()
        release.set()
        completed = await first_task
        await first_session.commit()
    async with maker() as check_session:
        definition = await check_session.scalar(
            select(JobDefinition).where(JobDefinition.name == "demo")
        )

    await engine.dispose()

    assert definition is not None
    assert visible_definition is not None
    assert visible_definition.running is True
    assert observed_running is True
    assert definition.running is False
    assert definition.last_result is JobRunStatus.OK
    assert skipped.status is JobRunStatus.SKIPPED
    assert skipped.job_definition_id == definition.id
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
    async with maker() as check_session:
        definition = await check_session.scalar(
            select(JobDefinition).where(JobDefinition.name == "failing")
        )

    await engine.dispose()

    assert definition is not None
    assert definition.running is False
    assert definition.last_result is JobRunStatus.FAILED
    assert run.status is JobRunStatus.FAILED
    assert run.error_code == "job_failed"
    assert run.error_message == "failed job"
