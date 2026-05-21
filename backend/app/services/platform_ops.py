"""Platform-ops read models — jobs console, dashboard, and the audit viewer.

Superadmin-only surfaces (docs/ref/features/platform.md, workshop.md). The jobs
console reads the in-process scheduler's registry plus the latest ``JobRun`` per
job; the dashboard rolls up health counts (no workshop financials); the audit
viewer reads the two append-only logs cross-workshop with filters.
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ErrorGroupStatus, JobRunResult
from app.models.identity import Client
from app.models.platform import ErrorGroup, JobRun
from app.models.support import ActionLog, StatusChangeLog
from app.models.workshop import Branch, Workshop
from app.services.scheduler import scheduler

# --- jobs console -----------------------------------------------------------


async def _latest_run(db: AsyncSession, job_name: str) -> JobRun | None:
    return (
        await db.execute(
            select(JobRun)
            .where(JobRun.job_name == job_name)
            .order_by(JobRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def list_jobs(db: AsyncSession) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for job in scheduler.jobs.values():
        run = await _latest_run(db, job.name)
        out.append(
            {
                "name": job.name,
                "interval_seconds": job.interval_seconds,
                "last_started_at": run.started_at if run else None,
                "last_finished_at": run.finished_at if run else None,
                "last_result": run.result if run else None,
                "last_log": run.log if run else None,
            }
        )
    out.sort(key=lambda j: str(j["name"]))
    return out


# --- dashboard --------------------------------------------------------------


async def _count(db: AsyncSession, model: Any) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def dashboard(db: AsyncSession) -> dict[str, Any]:
    workshops_count = await _count(db, Workshop)
    branches_count = await _count(db, Branch)
    clients_count = await _count(db, Client)

    recent_workshops = list(
        (await db.execute(select(Workshop).order_by(Workshop.created_at.desc()).limit(5)))
        .scalars()
        .all()
    )

    now = datetime.now(UTC)
    failed_jobs_24h = (
        await db.execute(
            select(func.count())
            .select_from(JobRun)
            .where(
                JobRun.result == JobRunResult.FAILED,
                JobRun.started_at >= now - timedelta(hours=24),
            )
        )
    ).scalar_one()
    open_error_groups = (
        await db.execute(
            select(func.count())
            .select_from(ErrorGroup)
            .where(ErrorGroup.status == ErrorGroupStatus.OPEN)
        )
    ).scalar_one()

    return {
        "workshops_count": workshops_count,
        "branches_count": branches_count,
        "clients_count": clients_count,
        "recent_workshops": recent_workshops,
        "failed_jobs_24h": failed_jobs_24h,
        "open_error_groups": open_error_groups,
    }


# --- audit viewer -----------------------------------------------------------


def _day_bounds(d: date, *, end: bool) -> datetime:
    return datetime.combine(d, time.max if end else time.min, tzinfo=UTC)


async def list_actions(
    db: AsyncSession,
    *,
    action: str | None = None,
    action_family: str | None = None,
    module: str | None = None,
    actor_search: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    workshop_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ActionLog]:
    stmt = select(ActionLog)
    if action is not None:
        stmt = stmt.where(ActionLog.action == action)
    if action_family is not None:
        stmt = stmt.where(ActionLog.action.like(f"{action_family}.%"))
    if module is not None:
        # the action family is the module prefix (e.g. ``order.confirmed``)
        stmt = stmt.where(ActionLog.action.like(f"{module}.%"))
    if entity_type is not None:
        stmt = stmt.where(ActionLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(ActionLog.entity_id == entity_id)
    if workshop_id is not None:
        stmt = stmt.where(ActionLog.workshop_id == workshop_id)
    if branch_id is not None:
        stmt = stmt.where(ActionLog.branch_id == branch_id)
    if actor_search is not None:
        actor_uuid = _maybe_uuid(actor_search)
        if actor_uuid is not None:
            stmt = stmt.where(
                or_(
                    ActionLog.actor_user_id == actor_uuid,
                    ActionLog.actor_client_id == actor_uuid,
                )
            )
        else:
            stmt = stmt.where(ActionLog.summary.ilike(f"%{actor_search}%"))
    if date_from is not None:
        stmt = stmt.where(ActionLog.created_at >= _day_bounds(date_from, end=False))
    if date_to is not None:
        stmt = stmt.where(ActionLog.created_at <= _day_bounds(date_to, end=True))
    stmt = stmt.order_by(ActionLog.created_at.desc()).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())


async def list_status_changes(
    db: AsyncSession,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    actor_search: str | None = None,
    workshop_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[StatusChangeLog]:
    stmt = select(StatusChangeLog)
    if entity_type is not None:
        stmt = stmt.where(StatusChangeLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(StatusChangeLog.entity_id == entity_id)
    if from_status is not None:
        stmt = stmt.where(StatusChangeLog.from_status == from_status)
    if to_status is not None:
        stmt = stmt.where(StatusChangeLog.to_status == to_status)
    if workshop_id is not None:
        stmt = stmt.where(StatusChangeLog.workshop_id == workshop_id)
    if actor_search is not None:
        actor_uuid = _maybe_uuid(actor_search)
        if actor_uuid is not None:
            stmt = stmt.where(
                or_(
                    StatusChangeLog.actor_user_id == actor_uuid,
                    StatusChangeLog.actor_client_id == actor_uuid,
                )
            )
    if date_from is not None:
        stmt = stmt.where(StatusChangeLog.changed_at >= _day_bounds(date_from, end=False))
    if date_to is not None:
        stmt = stmt.where(StatusChangeLog.changed_at <= _day_bounds(date_to, end=True))
    stmt = stmt.order_by(StatusChangeLog.changed_at.desc()).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())


def _maybe_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
