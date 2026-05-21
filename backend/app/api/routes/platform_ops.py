"""Platform-ops routes (superadmin app) — platform-operator scoped.

Jobs console, error monitor, audit viewer, and the health dashboard. All gated
by ``CurrentPlatformUser`` (docs/ref/features/platform.md, workshop.md).
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentPlatformUser, Session
from app.core.errors import conflict, not_found
from app.models.enums import ErrorGroupStatus
from app.schemas.platform_ops import (
    ActionLogRow,
    DashboardOut,
    ErrorGroupDetail,
    ErrorGroupRow,
    JobOut,
    RecentWorkshop,
    StatusChangeRow,
)
from app.services import errors as error_service
from app.services import platform_ops as service
from app.services.scheduler import scheduler

jobs_router = APIRouter()
errors_router = APIRouter()
audit_router = APIRouter()
dashboard_router = APIRouter()


# --- jobs console -----------------------------------------------------------


@jobs_router.get("", response_model=list[JobOut])
async def list_jobs(_: CurrentPlatformUser, db: Session) -> list[JobOut]:
    rows = await service.list_jobs(db)
    return [JobOut(**r) for r in rows]


@jobs_router.post("/{name}/run", response_model=JobOut)
async def run_job(name: str, _: CurrentPlatformUser, db: Session) -> JobOut:
    if name not in scheduler.jobs:
        raise not_found("No such job.", code="job_not_found")
    run = await scheduler.run_now(name)
    if run is None:
        raise conflict("Job is already running.", code="job_already_running")
    rows = await service.list_jobs(db)
    return next(JobOut(**r) for r in rows if r["name"] == name)


# --- error monitor ----------------------------------------------------------


@errors_router.get("", response_model=list[ErrorGroupRow])
async def list_errors(
    _: CurrentPlatformUser,
    db: Session,
    module: str | None = None,
    code: str | None = None,
    status: ErrorGroupStatus | None = None,
    min_count_24h: Annotated[int | None, Query(ge=1)] = None,
) -> list[ErrorGroupRow]:
    rows = await error_service.list_groups(
        db, module=module, code=code, status=status, min_count_24h=min_count_24h
    )
    return [ErrorGroupRow(**r) for r in rows]


@errors_router.get("/{group_id}", response_model=ErrorGroupDetail)
async def get_error(group_id: uuid.UUID, _: CurrentPlatformUser, db: Session) -> ErrorGroupDetail:
    detail = await error_service.get_group_detail(db, group_id)
    if detail is None:
        raise not_found("Error group not found.", code="error_group_not_found")
    return ErrorGroupDetail.model_validate(detail)


@errors_router.post("/{group_id}/resolve", response_model=ErrorGroupRow)
async def resolve_error(group_id: uuid.UUID, _: CurrentPlatformUser, db: Session) -> ErrorGroupRow:
    group = await error_service.resolve_group(db, group_id)
    if group is None:
        raise not_found("Error group not found.", code="error_group_not_found")
    rows = await error_service.list_groups(db, code=group.code)
    return next(ErrorGroupRow(**r) for r in rows if r["id"] == group_id)


# --- audit viewer -----------------------------------------------------------


@audit_router.get("/actions", response_model=list[ActionLogRow])
async def audit_actions(
    _: CurrentPlatformUser,
    db: Session,
    action: str | None = None,
    family: str | None = None,
    module: str | None = None,
    actor: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    workshop_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ActionLogRow]:
    rows = await service.list_actions(
        db,
        action=action,
        action_family=family,
        module=module,
        actor_search=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        workshop_id=workshop_id,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return [ActionLogRow.model_validate(r) for r in rows]


@audit_router.get("/status-changes", response_model=list[StatusChangeRow])
async def audit_status_changes(
    _: CurrentPlatformUser,
    db: Session,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    actor: str | None = None,
    workshop_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[StatusChangeRow]:
    rows = await service.list_status_changes(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        from_status=from_status,
        to_status=to_status,
        actor_search=actor,
        workshop_id=workshop_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return [StatusChangeRow.model_validate(r) for r in rows]


# --- dashboard --------------------------------------------------------------


@dashboard_router.get("", response_model=DashboardOut)
async def dashboard(_: CurrentPlatformUser, db: Session) -> DashboardOut:
    data = await service.dashboard(db)
    return DashboardOut(
        workshops_count=data["workshops_count"],
        branches_count=data["branches_count"],
        clients_count=data["clients_count"],
        recent_workshops=[RecentWorkshop.model_validate(w) for w in data["recent_workshops"]],
        failed_jobs_24h=data["failed_jobs_24h"],
        open_error_groups=data["open_error_groups"],
    )
