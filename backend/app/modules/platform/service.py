"""Platform operator use cases."""

import re
import secrets
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.core.security import PasswordPolicyError, hash_password, validate_password
from app.models.enums import (
    AuthenticatedPrincipalType,
    BranchStatus,
    ErrorRecordStatus,
    UserStatus,
    WorkshopStatus,
)
from app.modules.access.api import (
    normalize_uz_phone,
    prune_expired_sessions,
    revoke_for_principal,
    revoke_for_workshop,
)
from app.modules.access.contracts import Client, PlatformUser, WorkshopUser
from app.modules.catalog.contracts import BranchPricing
from app.modules.inventory.contracts import StockItem
from app.modules.platform.contracts import ErrorOccurrence, ErrorRecord, JobDefinition, JobRun
from app.modules.platform.errors import refresh_error_record_counts
from app.modules.platform.scheduler import RegisteredJob, registry
from app.modules.platform.schemas import (
    PlatformUserCreateRequest,
    PlatformUserPatchRequest,
    ProvisionWorkshopRequest,
)
from app.modules.support.api import (
    list_action_logs,
    list_status_change_logs,
    record_action,
    record_status_change,
)
from app.modules.workshop.contracts import Branch, Workshop
from app.modules.workshop.schemas import dump_working_hours

CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,31}$")


@dataclass(frozen=True)
class ProvisionedWorkshop:
    workshop: Workshop
    branch: Branch
    owner: WorkshopUser
    temp_password: str


@dataclass(frozen=True)
class CreatedPlatformUser:
    user: PlatformUser
    temp_password: str


@dataclass(frozen=True)
class PlatformJobRecord:
    definition: JobDefinition
    recent_runs: list[JobRun]


@dataclass(frozen=True)
class PlatformOverview:
    workshops_total: int
    workshops_active: int
    workshops_blocked: int
    branches_total: int
    clients_total: int
    platform_users_active: int


@dataclass(frozen=True)
class WorkshopListRow:
    workshop: Workshop
    owner_login: str
    branch_count: int


@dataclass(frozen=True)
class WorkshopDetailRow:
    workshop: Workshop
    branches: list[Branch]
    owner: WorkshopUser
    block_reason: str | None


async def _cleanup_expired_sessions_job(db: AsyncSession) -> str:
    count = await prune_expired_sessions(db)
    return f"Pruned {count} expired sessions"


async def _daily_low_stock_summary_job(db: AsyncSession) -> str:
    count = await db.scalar(
        select(func.count()).select_from(StockItem).where(StockItem.on_hand <= StockItem.min_stock)
    )
    return f"{count or 0} low-stock stock items found"


DEFAULT_JOBS = (
    RegisteredJob(
        name="cleanup-expired-sessions",
        schedule="hourly",
        handler=_cleanup_expired_sessions_job,
    ),
    RegisteredJob(
        name="daily-low-stock-summary",
        schedule="daily",
        handler=_daily_low_stock_summary_job,
    ),
)


def ensure_default_jobs_registered() -> None:
    for job in DEFAULT_JOBS:
        registry.register(job)


async def list_workshops(db: AsyncSession) -> list[WorkshopListRow]:
    # AB-37: surface the owner login (join WorkshopUser) and a branch count
    # (aggregate over Branch) on each list row — both derived from existing data,
    # no denormalized columns. Owner is a guaranteed 1:1 (inner join); branches
    # are counted in full (an at-a-glance "Filiallar" total, active or not).
    query = (
        select(Workshop, WorkshopUser.login, func.count(Branch.id))
        .join(WorkshopUser, WorkshopUser.id == Workshop.owner_user_id)
        .outerjoin(Branch, Branch.workshop_id == Workshop.id)
        .group_by(Workshop.id, WorkshopUser.login)
        .order_by(Workshop.created_at.desc(), Workshop.name)
    )
    rows = (await db.execute(query)).all()
    return [
        WorkshopListRow(workshop=workshop, owner_login=login, branch_count=int(count or 0))
        for workshop, login, count in rows
    ]


async def get_platform_overview(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
) -> PlatformOverview:
    require_platform_operator(principal)
    workshops_total = await db.scalar(select(func.count()).select_from(Workshop))
    workshops_active = await db.scalar(
        select(func.count()).select_from(Workshop).where(Workshop.status == WorkshopStatus.ACTIVE)
    )
    workshops_blocked = await db.scalar(
        select(func.count()).select_from(Workshop).where(Workshop.status == WorkshopStatus.BLOCKED)
    )
    branches_total = await db.scalar(select(func.count()).select_from(Branch))
    clients_total = await db.scalar(select(func.count()).select_from(Client))
    platform_users_active = await db.scalar(
        select(func.count())
        .select_from(PlatformUser)
        .where(PlatformUser.status == UserStatus.ACTIVE)
    )
    return PlatformOverview(
        workshops_total=int(workshops_total or 0),
        workshops_active=int(workshops_active or 0),
        workshops_blocked=int(workshops_blocked or 0),
        branches_total=int(branches_total or 0),
        clients_total=int(clients_total or 0),
        platform_users_active=int(platform_users_active or 0),
    )


async def get_workshop_detail(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
) -> WorkshopDetailRow:
    workshop = await db.get(Workshop, workshop_id)
    if workshop is None:
        raise APIError(
            "workshop_not_found",
            "Workshop not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    branches = (
        await db.scalars(
            select(Branch).where(Branch.workshop_id == workshop.id).order_by(Branch.created_at)
        )
    ).all()
    owner = await db.get(WorkshopUser, workshop.owner_user_id)
    if owner is None:
        raise RuntimeError("workshop owner_user_id points to a missing owner")
    block_reason = (
        await _latest_block_reason(db, workshop_id=workshop.id)
        if workshop.status is WorkshopStatus.BLOCKED
        else None
    )
    return WorkshopDetailRow(
        workshop=workshop,
        branches=list(branches),
        owner=owner,
        block_reason=block_reason,
    )


async def _latest_block_reason(db: AsyncSession, *, workshop_id: uuid.UUID) -> str | None:
    # AB-20: the block reason lives on the status-change log written at block time
    # (service.block_workshop). A currently-blocked workshop's most recent
    # workshop-entity transition is that block, so take the latest row whose
    # to_status is `blocked` and return its reason (None if never recorded).
    logs = await list_status_change_logs(
        db,
        workshop_id=workshop_id,
        entity_type="workshop",
        limit=10,
    )
    for log in logs:
        if log.to_status == WorkshopStatus.BLOCKED.value:
            return log.reason
    return None


async def provision_workshop(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: ProvisionWorkshopRequest,
) -> ProvisionedWorkshop:
    require_platform_operator(principal)
    code = await _resolve_workshop_code(db, payload.workshop.code, payload.workshop.name)
    temp_password = payload.temp_password or generate_temp_password()
    try:
        validate_password(temp_password)
    except PasswordPolicyError as exc:
        raise APIError(
            "weak_password",
            str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc
    owner_login = _required_text(payload.owner.login, "owner_login_required")
    workshop_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    workshop = Workshop(
        id=workshop_id,
        code=code,
        name=_required_text(payload.workshop.name, "workshop_name_required"),
        phone=normalize_uz_phone(payload.workshop.phone),
        address=_optional_text(payload.workshop.address),
        owner_user_id=owner_id,
        status=WorkshopStatus.ACTIVE,
        currency=payload.workshop.currency,
    )
    db.add(workshop)
    await db.flush()

    branch = Branch(
        workshop_id=workshop.id,
        name=_required_text(payload.branch.name, "branch_name_required"),
        address=_required_text(payload.branch.address, "branch_address_required"),
        phone=normalize_uz_phone(payload.branch.phone),
        latitude=payload.branch.latitude,
        longitude=payload.branch.longitude,
        working_hours=dump_working_hours(payload.branch.working_hours),
        status=BranchStatus.ACTIVE,
    )
    db.add(branch)
    await db.flush()
    db.add(BranchPricing(branch_id=branch.id))

    owner = WorkshopUser(
        id=owner_id,
        workshop_id=workshop.id,
        login=owner_login,
        password_hash=hash_password(temp_password),
        full_name=_required_text(payload.owner.full_name, "owner_name_required"),
        phone=normalize_uz_phone(payload.owner.phone),
        is_owner=True,
        home_branch_id=branch.id,
        status=UserStatus.ACTIVE,
        password_reset_required=True,
    )
    db.add(owner)
    await db.flush()

    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="platform.workshop.provision",
        entity_type="workshop",
        entity_id=workshop.id,
        workshop_id=workshop.id,
        summary=f"Provisioned workshop {workshop.name}",
        details={
            "workshop_code": workshop.code,
            "owner_login": owner.login,
            "branch_id": str(branch.id),
        },
    )
    return ProvisionedWorkshop(
        workshop=workshop,
        branch=branch,
        owner=owner,
        temp_password=temp_password,
    )


async def block_workshop(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    workshop_id: uuid.UUID,
    reason: str,
) -> Workshop:
    require_platform_operator(principal)
    normalized_reason = _required_text(reason, "reason_required")
    workshop = await db.get(Workshop, workshop_id)
    if workshop is None:
        raise APIError(
            "workshop_not_found",
            "Workshop not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if workshop.status is WorkshopStatus.BLOCKED:
        raise APIError(
            "invalid_status",
            "Workshop is already blocked",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    from_status = workshop.status.value
    workshop.status = WorkshopStatus.BLOCKED
    await revoke_for_workshop(db, workshop.id)
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action="platform.workshop.block",
        entity_type="workshop",
        entity_id=workshop.id,
        workshop_id=workshop.id,
        summary=f"Blocked workshop {workshop.name}",
        details={"reason": normalized_reason},
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="workshop",
        entity_id=workshop.id,
        workshop_id=workshop.id,
        from_status=from_status,
        to_status=workshop.status.value,
        reason=normalized_reason,
        action_log_id=action.id,
    )
    return workshop


async def unblock_workshop(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    workshop_id: uuid.UUID,
) -> Workshop:
    require_platform_operator(principal)
    workshop = await db.get(Workshop, workshop_id)
    if workshop is None:
        raise APIError(
            "workshop_not_found",
            "Workshop not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if workshop.status is WorkshopStatus.ACTIVE:
        raise APIError(
            "invalid_status",
            "Workshop is already active",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    from_status = workshop.status.value
    workshop.status = WorkshopStatus.ACTIVE
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action="platform.workshop.unblock",
        entity_type="workshop",
        entity_id=workshop.id,
        workshop_id=workshop.id,
        summary=f"Unblocked workshop {workshop.name}",
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="workshop",
        entity_id=workshop.id,
        workshop_id=workshop.id,
        from_status=from_status,
        to_status=workshop.status.value,
        action_log_id=action.id,
    )
    return workshop


def require_platform_operator(principal: AuthenticatedPrincipal) -> None:
    if principal.principal_type is not AuthenticatedPrincipalType.PLATFORM_USER:
        raise APIError("forbidden", "Forbidden", status_code=status.HTTP_403_FORBIDDEN)


async def list_platform_users(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
) -> list[PlatformUser]:
    require_platform_operator(principal)
    return list(
        (
            await db.scalars(
                select(PlatformUser).order_by(PlatformUser.status, PlatformUser.full_name)
            )
        ).all()
    )


async def create_platform_user(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    payload: PlatformUserCreateRequest,
) -> CreatedPlatformUser:
    require_platform_operator(principal)
    login = _required_text(payload.login, "login_required")
    if await _platform_login_exists(db, login=login):
        raise APIError("login_exists", "Login already exists", status_code=status.HTTP_409_CONFLICT)
    temp_password = payload.temp_password or generate_temp_password()
    try:
        validate_password(temp_password)
    except PasswordPolicyError as exc:
        raise APIError(
            "weak_password",
            str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc
    user = PlatformUser(
        login=login,
        password_hash=hash_password(temp_password),
        full_name=_required_text(payload.full_name, "full_name_required"),
        phone=normalize_uz_phone(payload.phone),
        status=UserStatus.ACTIVE,
        password_reset_required=True,
    )
    db.add(user)
    await db.flush()
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="platform.user.create",
        entity_type="platform_user",
        entity_id=user.id,
        summary=f"Created platform user {user.login}",
        details={"login": user.login},
    )
    return CreatedPlatformUser(user=user, temp_password=temp_password)


async def update_platform_user(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    user_id: uuid.UUID,
    payload: PlatformUserPatchRequest,
) -> PlatformUser:
    require_platform_operator(principal)
    user = await _get_platform_user(db, user_id=user_id)
    if payload.full_name is not None:
        user.full_name = _required_text(payload.full_name, "full_name_required")
    if payload.phone is not None:
        user.phone = normalize_uz_phone(payload.phone)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="platform.user.update",
        entity_type="platform_user",
        entity_id=user.id,
        summary=f"Updated platform user {user.login}",
    )
    await db.flush()
    await db.refresh(user)
    return user


async def reset_platform_user_password(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    user_id: uuid.UUID,
) -> CreatedPlatformUser:
    require_platform_operator(principal)
    user = await _get_platform_user(db, user_id=user_id)
    temp_password = generate_temp_password()
    user.password_hash = hash_password(temp_password)
    user.password_reset_required = True
    await revoke_for_principal(
        db,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        principal_id=user.id,
    )
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="platform.user.password.reset",
        entity_type="platform_user",
        entity_id=user.id,
        summary=f"Reset password for platform user {user.login}",
    )
    await db.flush()
    await db.refresh(user)
    return CreatedPlatformUser(user=user, temp_password=temp_password)


async def block_platform_user(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    user_id: uuid.UUID,
    reason: str,
) -> PlatformUser:
    require_platform_operator(principal)
    normalized_reason = _required_text(reason, "reason_required")
    if user_id == principal.principal_id:
        raise APIError(
            "cannot_block_self",
            "A platform operator cannot block themselves",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    user = await _get_platform_user(db, user_id=user_id)
    if user.status is UserStatus.BLOCKED:
        raise APIError(
            "invalid_status",
            "Platform user is already blocked",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    await _ensure_another_active_platform_user(db, blocked_user_id=user.id)
    from_status = user.status.value
    user.status = UserStatus.BLOCKED
    await revoke_for_principal(
        db,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        principal_id=user.id,
    )
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action="platform.user.block",
        entity_type="platform_user",
        entity_id=user.id,
        summary=f"Blocked platform user {user.login}",
        details={"reason": normalized_reason},
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="platform_user",
        entity_id=user.id,
        from_status=from_status,
        to_status=user.status.value,
        reason=normalized_reason,
        action_log_id=action.id,
    )
    await db.flush()
    await db.refresh(user)
    return user


async def unblock_platform_user(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    user_id: uuid.UUID,
) -> PlatformUser:
    require_platform_operator(principal)
    user = await _get_platform_user(db, user_id=user_id)
    if user.status is UserStatus.ACTIVE:
        raise APIError(
            "invalid_status",
            "Platform user is already active",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    from_status = user.status.value
    user.status = UserStatus.ACTIVE
    action = await record_action(
        db,
        actor=actor_from_principal(principal),
        action="platform.user.unblock",
        entity_type="platform_user",
        entity_id=user.id,
        summary=f"Unblocked platform user {user.login}",
    )
    await record_status_change(
        db,
        actor=actor_from_principal(principal),
        entity_type="platform_user",
        entity_id=user.id,
        from_status=from_status,
        to_status=user.status.value,
        action_log_id=action.id,
    )
    await db.flush()
    await db.refresh(user)
    return user


async def list_platform_jobs(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
) -> list[PlatformJobRecord]:
    require_platform_operator(principal)
    await _ensure_platform_job_definitions(db)
    definitions = list(
        (
            await db.scalars(
                select(JobDefinition).order_by(JobDefinition.enabled.desc(), JobDefinition.name)
            )
        ).all()
    )
    records: list[PlatformJobRecord] = []
    for definition in definitions:
        runs = list(
            (
                await db.scalars(
                    select(JobRun)
                    .where(JobRun.job_name == definition.name)
                    .order_by(JobRun.started_at.desc())
                    .limit(5)
                )
            ).all()
        )
        records.append(PlatformJobRecord(definition=definition, recent_runs=runs))
    return records


async def run_platform_job(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    name: str,
) -> JobRun:
    require_platform_operator(principal)
    await _ensure_platform_job_definitions(db)
    job = registry.get(name)
    if job is None:
        raise APIError("job_not_found", "Job not found", status_code=status.HTTP_404_NOT_FOUND)
    run = await registry.run(db, name, trace_id=principal.trace_id)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="platform.job.run",
        entity_type="job",
        entity_id=run.id,
        summary=f"Triggered job {name}",
        details={"status": run.status.value, "job_name": name},
    )
    return run


async def list_error_records(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    status_filter: ErrorRecordStatus | None = None,
    module: str | None = None,
) -> list[ErrorRecord]:
    require_platform_operator(principal)
    query = select(ErrorRecord).order_by(
        ErrorRecord.status,
        ErrorRecord.last_occurred_at.desc().nullslast(),
        ErrorRecord.code,
    )
    if status_filter is not None:
        query = query.where(ErrorRecord.status == status_filter)
    if module is not None:
        query = query.where(ErrorRecord.module == module)
    # AB-44: ErrorRecord rows are grouped per code+module so cardinality is small
    # in practice, but cap the result defensively so a pathological spread of
    # distinct codes can't return an unbounded list to the monitor.
    query = query.limit(200)
    records = list((await db.scalars(query)).all())
    return await refresh_error_record_counts(db, records)


async def get_error_record_detail(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    record_id: uuid.UUID,
) -> tuple[ErrorRecord, list[ErrorOccurrence]]:
    require_platform_operator(principal)
    record = await db.get(ErrorRecord, record_id)
    if record is None:
        raise APIError("error_not_found", "Error record not found", status_code=404)
    await refresh_error_record_counts(db, [record])
    occurrences = list(
        (
            await db.scalars(
                select(ErrorOccurrence)
                .where(ErrorOccurrence.error_record_id == record.id)
                .order_by(ErrorOccurrence.occurred_at.desc())
                .limit(25)
            )
        ).all()
    )
    return record, occurrences


async def resolve_error_record(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    record_id: uuid.UUID,
) -> ErrorRecord:
    require_platform_operator(principal)
    record, _ = await get_error_record_detail(db, principal=principal, record_id=record_id)
    record.status = ErrorRecordStatus.RESOLVED
    record.resolved_by_user_id = principal.principal_id
    record.resolved_at = datetime.now(UTC)
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="platform.error.resolve",
        entity_type="error_record",
        entity_id=record.id,
        summary=f"Resolved error code {record.code}",
        details={"code": record.code},
    )
    await db.flush()
    await db.refresh(record)
    return record


async def reopen_error_record(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    record_id: uuid.UUID,
) -> ErrorRecord:
    # AB-25: the inverse of resolve — flip a resolved record back to open and clear
    # the resolution metadata, so a code that recurs after being marked resolved
    # can be re-triaged. The status enum already carries OPEN, so no migration.
    require_platform_operator(principal)
    record, _ = await get_error_record_detail(db, principal=principal, record_id=record_id)
    record.status = ErrorRecordStatus.OPEN
    record.resolved_by_user_id = None
    record.resolved_at = None
    await record_action(
        db,
        actor=actor_from_principal(principal),
        action="platform.error.reopen",
        entity_type="error_record",
        entity_id=record.id,
        summary=f"Reopened error code {record.code}",
        details={"code": record.code},
    )
    await db.flush()
    await db.refresh(record)
    return record


async def list_platform_action_logs(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    workshop_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    action: str | None = None,
    limit: int = 50,
) -> Sequence[object]:
    require_platform_operator(principal)
    return await list_action_logs(
        db,
        workshop_id=workshop_id,
        branch_id=branch_id,
        action=action,
        limit=limit,
    )


async def list_platform_status_change_logs(
    db: AsyncSession,
    *,
    principal: AuthenticatedPrincipal,
    workshop_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    limit: int = 50,
) -> Sequence[object]:
    require_platform_operator(principal)
    return await list_status_change_logs(
        db,
        workshop_id=workshop_id,
        branch_id=branch_id,
        entity_type=entity_type,
        limit=limit,
    )


async def _resolve_workshop_code(
    db: AsyncSession,
    requested_code: str | None,
    workshop_name: str,
) -> str:
    if requested_code is not None:
        code = requested_code.strip()
        if not CODE_RE.fullmatch(code):
            raise APIError(
                "invalid_workshop_code",
                "Invalid workshop code",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if await _workshop_code_exists(db, code):
            raise APIError(
                "workshop_code_exists",
                "Workshop code already exists",
                status_code=status.HTTP_409_CONFLICT,
            )
        return code

    base = _slugify(workshop_name)
    code = base
    while await _workshop_code_exists(db, code):
        code = f"{base}-{secrets.randbelow(10_000):04d}"
    return code


async def _workshop_code_exists(db: AsyncSession, code: str) -> bool:
    existing = await db.scalar(select(Workshop.id).where(func.lower(Workshop.code) == code.lower()))
    return existing is not None


async def _platform_login_exists(db: AsyncSession, *, login: str) -> bool:
    existing = await db.scalar(
        select(PlatformUser.id).where(func.lower(PlatformUser.login) == login.lower())
    )
    return existing is not None


async def _get_platform_user(db: AsyncSession, *, user_id: uuid.UUID) -> PlatformUser:
    user = await db.get(PlatformUser, user_id)
    if user is None:
        raise APIError("user_not_found", "User not found", status_code=status.HTTP_404_NOT_FOUND)
    return user


async def _ensure_another_active_platform_user(
    db: AsyncSession,
    *,
    blocked_user_id: uuid.UUID,
) -> None:
    active_ids = list(
        (
            await db.scalars(
                select(PlatformUser.id)
                .where(PlatformUser.status == UserStatus.ACTIVE)
                .order_by(PlatformUser.id)
                .with_for_update()
            )
        ).all()
    )
    if not any(active_id != blocked_user_id for active_id in active_ids):
        raise APIError(
            "last_platform_operator",
            "At least one active platform operator is required",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


async def _ensure_platform_job_definitions(db: AsyncSession) -> None:
    ensure_default_jobs_registered()
    for job in registry.registered():
        definition = await db.scalar(select(JobDefinition).where(JobDefinition.name == job.name))
        if definition is None:
            try:
                async with db.begin_nested():
                    db.add(JobDefinition(name=job.name, schedule=job.schedule, enabled=True))
                    await db.flush()
            except IntegrityError:
                definition = await db.scalar(
                    select(JobDefinition).where(JobDefinition.name == job.name)
                )
                if definition is not None:
                    definition.schedule = job.schedule
        else:
            definition.schedule = job.schedule
    await db.flush()


def _required_text(value: str, code: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise APIError(code, "Required field is missing", status_code=status.HTTP_400_BAD_REQUEST)
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized or None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    if len(slug) < 3:
        slug = f"workshop-{secrets.randbelow(10_000):04d}"
    return slug[:32].strip("-")


def generate_temp_password() -> str:
    return f"Tmp{secrets.randbelow(1_000_000):06d}{secrets.token_urlsafe(8)}"
