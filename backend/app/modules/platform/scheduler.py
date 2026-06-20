"""In-process scheduler/job registry skeleton."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import JobRunStatus
from app.modules.platform.contracts import JobDefinition, JobRun

JobHandler = Callable[[AsyncSession], Awaitable[str | None]]


@dataclass(frozen=True)
class RegisteredJob:
    name: str
    schedule: str
    handler: JobHandler


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, RegisteredJob] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def register(self, job: RegisteredJob) -> None:
        self._jobs[job.name] = job
        self._locks.setdefault(job.name, asyncio.Lock())

    def get(self, name: str) -> RegisteredJob | None:
        return self._jobs.get(name)

    def registered(self) -> list[RegisteredJob]:
        return sorted(self._jobs.values(), key=lambda job: job.name)

    async def run(self, db: AsyncSession, name: str, *, trace_id: str | None = None) -> JobRun:
        job = self._jobs[name]
        lock = self._locks.setdefault(name, asyncio.Lock())
        definition = await _ensure_definition(db, job)
        if lock.locked():
            return await _record_run(
                db,
                job_definition_id=definition.id,
                job_name=name,
                status=JobRunStatus.SKIPPED,
                brief_log="already running",
                trace_id=trace_id,
            )
        async with lock:
            definition = await _ensure_definition(db, job)
            definition.running = True
            await db.flush()
            run = await _record_run(
                db,
                job_definition_id=definition.id,
                job_name=name,
                status=JobRunStatus.RUNNING,
                trace_id=trace_id,
            )
            # Make running truth visible to other operator sessions while the handler works.
            await db.commit()
            try:
                brief = await job.handler(db)
            except Exception as exc:
                run.status = JobRunStatus.FAILED
                run.error_code = "job_failed"
                run.error_message = str(exc)
                run.finished_at = datetime.now(UTC)
                definition.last_result = JobRunStatus.FAILED
            else:
                run.status = JobRunStatus.OK
                run.brief_log = brief
                run.finished_at = datetime.now(UTC)
                definition.last_result = run.status
            definition.running = False
            definition.last_run_at = run.started_at
            await db.flush()
            return run


async def _record_run(
    db: AsyncSession,
    *,
    job_definition_id: uuid.UUID,
    job_name: str,
    status: JobRunStatus,
    brief_log: str | None = None,
    trace_id: str | None = None,
) -> JobRun:
    run = JobRun(
        job_definition_id=job_definition_id,
        job_name=job_name,
        status=status,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC) if status is not JobRunStatus.RUNNING else None,
        brief_log=brief_log,
        trace_id=trace_id,
    )
    db.add(run)
    await db.flush()
    return run


async def _ensure_definition(db: AsyncSession, job: RegisteredJob) -> JobDefinition:
    definition = await db.scalar(select(JobDefinition).where(JobDefinition.name == job.name))
    if definition is None:
        definition = JobDefinition(name=job.name, schedule=job.schedule)
        db.add(definition)
        await db.flush()
    definition.schedule = job.schedule
    return definition


registry = JobRegistry()
