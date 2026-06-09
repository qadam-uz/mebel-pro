"""Platform-operator routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AccountReadyPrincipal, Session
from app.models.enums import ErrorRecordStatus
from app.modules.platform.api import (
    block_platform_user,
    block_workshop,
    create_platform_user,
    get_error_record_detail,
    get_platform_overview,
    get_workshop_detail,
    list_error_records,
    list_platform_action_logs,
    list_platform_jobs,
    list_platform_status_change_logs,
    list_platform_users,
    list_workshops,
    provision_workshop,
    require_platform_operator,
    reset_platform_user_password,
    resolve_error_record,
    run_platform_job,
    unblock_platform_user,
    unblock_workshop,
    update_platform_user,
)
from app.modules.platform.schemas import (
    ActionLogResponse,
    BlockPlatformUserRequest,
    BlockWorkshopRequest,
    BranchSummary,
    ErrorOccurrenceResponse,
    ErrorRecordDetail,
    ErrorRecordSummary,
    JobDefinitionResponse,
    JobRunResponse,
    PlatformJobSummary,
    PlatformOverviewResponse,
    PlatformUserCreateRequest,
    PlatformUserPatchRequest,
    PlatformUserResponse,
    PlatformUserTempPasswordResponse,
    PlatformWorkshopDetail,
    ProvisionWorkshopRequest,
    ProvisionWorkshopResponse,
    StatusChangeLogResponse,
    WorkshopSummary,
    WorkshopUserSummary,
)

router = APIRouter(prefix="/platform", tags=["platform"])
ErrorStatusQuery = Annotated[ErrorRecordStatus | None, Query(alias="status")]
LimitQuery = Annotated[int, Query(ge=1, le=200)]


@router.get("/overview", response_model=PlatformOverviewResponse)
async def overview_show(
    principal: AccountReadyPrincipal,
    db: Session,
) -> PlatformOverviewResponse:
    overview = await get_platform_overview(db, principal=principal)
    return PlatformOverviewResponse.model_validate(overview)


@router.get("/workshops", response_model=list[WorkshopSummary])
async def workshops_index(
    principal: AccountReadyPrincipal,
    db: Session,
) -> list[WorkshopSummary]:
    require_platform_operator(principal)
    rows = await list_workshops(db)
    return [WorkshopSummary.model_validate(row) for row in rows]


@router.post(
    "/workshops",
    response_model=ProvisionWorkshopResponse,
    status_code=status.HTTP_201_CREATED,
)
async def workshops_create(
    payload: ProvisionWorkshopRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ProvisionWorkshopResponse:
    provisioned = await provision_workshop(db, principal=principal, payload=payload)
    return ProvisionWorkshopResponse(
        workshop=WorkshopSummary.model_validate(provisioned.workshop),
        branch=BranchSummary.model_validate(provisioned.branch),
        owner=WorkshopUserSummary.model_validate(provisioned.owner),
        temp_password=provisioned.temp_password,
    )


@router.get("/workshops/{workshop_id}", response_model=PlatformWorkshopDetail)
async def workshops_show(
    workshop_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> PlatformWorkshopDetail:
    require_platform_operator(principal)
    workshop, branches, owner = await get_workshop_detail(db, workshop_id=workshop_id)
    return PlatformWorkshopDetail(
        workshop=WorkshopSummary.model_validate(workshop),
        branches=[BranchSummary.model_validate(branch) for branch in branches],
        owner=WorkshopUserSummary.model_validate(owner),
    )


@router.post("/workshops/{workshop_id}/block", response_model=WorkshopSummary)
async def workshops_block(
    workshop_id: uuid.UUID,
    payload: BlockWorkshopRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopSummary:
    workshop = await block_workshop(
        db,
        principal=principal,
        workshop_id=workshop_id,
        reason=payload.reason,
    )
    return WorkshopSummary.model_validate(workshop)


@router.post("/workshops/{workshop_id}/unblock", response_model=WorkshopSummary)
async def workshops_unblock(
    workshop_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> WorkshopSummary:
    workshop = await unblock_workshop(db, principal=principal, workshop_id=workshop_id)
    return WorkshopSummary.model_validate(workshop)


@router.get("/jobs", response_model=list[PlatformJobSummary])
async def jobs_index(
    principal: AccountReadyPrincipal,
    db: Session,
) -> list[PlatformJobSummary]:
    records = await list_platform_jobs(db, principal=principal)
    return [
        PlatformJobSummary(
            definition=JobDefinitionResponse.model_validate(record.definition),
            recent_runs=[JobRunResponse.model_validate(run) for run in record.recent_runs],
        )
        for record in records
    ]


@router.post("/jobs/{job_name}/run", response_model=JobRunResponse)
async def jobs_run(
    job_name: str,
    principal: AccountReadyPrincipal,
    db: Session,
) -> JobRunResponse:
    run = await run_platform_job(db, principal=principal, name=job_name)
    return JobRunResponse.model_validate(run)


@router.get("/errors", response_model=list[ErrorRecordSummary])
async def errors_index(
    principal: AccountReadyPrincipal,
    db: Session,
    status_filter: ErrorStatusQuery = None,
    module: str | None = None,
) -> list[ErrorRecordSummary]:
    rows = await list_error_records(
        db,
        principal=principal,
        status_filter=status_filter,
        module=module,
    )
    return [ErrorRecordSummary.model_validate(row) for row in rows]


@router.get("/errors/{record_id}", response_model=ErrorRecordDetail)
async def errors_show(
    record_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ErrorRecordDetail:
    record, occurrences = await get_error_record_detail(
        db,
        principal=principal,
        record_id=record_id,
    )
    return ErrorRecordDetail(
        record=ErrorRecordSummary.model_validate(record),
        occurrences=[ErrorOccurrenceResponse.model_validate(row) for row in occurrences],
    )


@router.post("/errors/{record_id}/resolve", response_model=ErrorRecordSummary)
async def errors_resolve(
    record_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> ErrorRecordSummary:
    row = await resolve_error_record(db, principal=principal, record_id=record_id)
    return ErrorRecordSummary.model_validate(row)


@router.get("/users", response_model=list[PlatformUserResponse])
async def users_index(
    principal: AccountReadyPrincipal,
    db: Session,
) -> list[PlatformUserResponse]:
    rows = await list_platform_users(db, principal=principal)
    return [PlatformUserResponse.model_validate(row) for row in rows]


@router.post(
    "/users",
    response_model=PlatformUserTempPasswordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def users_create(
    payload: PlatformUserCreateRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> PlatformUserTempPasswordResponse:
    created = await create_platform_user(db, principal=principal, payload=payload)
    return PlatformUserTempPasswordResponse(
        user=PlatformUserResponse.model_validate(created.user),
        temp_password=created.temp_password,
    )


@router.patch("/users/{user_id}", response_model=PlatformUserResponse)
async def users_update(
    user_id: uuid.UUID,
    payload: PlatformUserPatchRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> PlatformUserResponse:
    row = await update_platform_user(db, principal=principal, user_id=user_id, payload=payload)
    return PlatformUserResponse.model_validate(row)


@router.post("/users/{user_id}/reset-password", response_model=PlatformUserTempPasswordResponse)
async def users_reset_password(
    user_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> PlatformUserTempPasswordResponse:
    reset = await reset_platform_user_password(db, principal=principal, user_id=user_id)
    return PlatformUserTempPasswordResponse(
        user=PlatformUserResponse.model_validate(reset.user),
        temp_password=reset.temp_password,
    )


@router.post("/users/{user_id}/block", response_model=PlatformUserResponse)
async def users_block(
    user_id: uuid.UUID,
    payload: BlockPlatformUserRequest,
    principal: AccountReadyPrincipal,
    db: Session,
) -> PlatformUserResponse:
    row = await block_platform_user(
        db,
        principal=principal,
        user_id=user_id,
        reason=payload.reason,
    )
    return PlatformUserResponse.model_validate(row)


@router.post("/users/{user_id}/unblock", response_model=PlatformUserResponse)
async def users_unblock(
    user_id: uuid.UUID,
    principal: AccountReadyPrincipal,
    db: Session,
) -> PlatformUserResponse:
    row = await unblock_platform_user(db, principal=principal, user_id=user_id)
    return PlatformUserResponse.model_validate(row)


@router.get("/audit/actions", response_model=list[ActionLogResponse])
async def audit_actions_index(
    principal: AccountReadyPrincipal,
    db: Session,
    workshop_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    action: str | None = None,
    limit: LimitQuery = 50,
) -> list[ActionLogResponse]:
    rows = await list_platform_action_logs(
        db,
        principal=principal,
        workshop_id=workshop_id,
        branch_id=branch_id,
        action=action,
        limit=limit,
    )
    return [ActionLogResponse.model_validate(row) for row in rows]


@router.get("/audit/status-changes", response_model=list[StatusChangeLogResponse])
async def audit_status_index(
    principal: AccountReadyPrincipal,
    db: Session,
    workshop_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    limit: LimitQuery = 50,
) -> list[StatusChangeLogResponse]:
    rows = await list_platform_status_change_logs(
        db,
        principal=principal,
        workshop_id=workshop_id,
        branch_id=branch_id,
        entity_type=entity_type,
        limit=limit,
    )
    return [StatusChangeLogResponse.model_validate(row) for row in rows]
