"""In-process background scheduler — no external queue, no Celery, no cron.

Holds the v1 jobs (docs/ref/features/platform.md): hourly session prune and a
daily low-stock summary. Each run is recorded to ``job_run``; a job never runs
twice concurrently (a per-job lock); operators can trigger a run on demand.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.models.enums import JobRunResult
from app.models.platform import JobRun

log = get_logger("scheduler")

JobFunc = Callable[[AsyncSession], Awaitable[str]]


@dataclass
class JobDef:
    name: str
    interval_seconds: int
    func: JobFunc
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class Scheduler:
    def __init__(self) -> None:
        self._jobs: dict[str, JobDef] = {}
        self._tasks: list[asyncio.Task[None]] = []
        self._running = False

    def register(self, name: str, interval_seconds: int, func: JobFunc) -> None:
        self._jobs[name] = JobDef(name=name, interval_seconds=interval_seconds, func=func)

    @property
    def jobs(self) -> dict[str, JobDef]:
        return self._jobs

    async def start(self) -> None:
        if self._running:
            return
        # Register the default jobs lazily to avoid import cycles.
        from app.services import jobs as job_impls

        job_impls.register_default_jobs(self)
        self._running = True
        for job in self._jobs.values():
            self._tasks.append(asyncio.create_task(self._loop(job)))
        log.info("scheduler.started", jobs=list(self._jobs))

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

    async def _loop(self, job: JobDef) -> None:
        # Stagger first run slightly so startup isn't a thundering herd.
        await asyncio.sleep(min(5, job.interval_seconds))
        while self._running:
            await self.run_now(job.name)
            await asyncio.sleep(job.interval_seconds)

    async def run_now(self, name: str) -> JobRun | None:
        """Execute a job once, recording its run. Guarded against concurrency."""
        job = self._jobs.get(name)
        if job is None:
            return None
        if job.lock.locked():
            log.info("scheduler.skip_locked", job=name)
            return None
        async with job.lock:
            return await self._execute(job)

    async def _execute(self, job: JobDef) -> JobRun:
        async with SessionLocal() as db:
            run = JobRun(job_name=job.name, started_at=datetime.now(UTC))
            db.add(run)
            await db.flush()
            try:
                summary = await job.func(db)
                run.result = JobRunResult.OK
                run.log = summary
            except Exception as exc:  # record + notify, never crash the loop
                await db.rollback()
                run = JobRun(
                    job_name=job.name,
                    started_at=datetime.now(UTC),
                    result=JobRunResult.FAILED,
                    log=f"{type(exc).__name__}: {exc}",
                )
                db.add(run)
                log.error("scheduler.job_failed", job=job.name, error=str(exc))
            finally:
                run.finished_at = datetime.now(UTC)
                await db.commit()
            return run


scheduler = Scheduler()
