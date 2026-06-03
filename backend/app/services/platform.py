"""Platform operator use cases."""

import re
import secrets
import uuid
from dataclasses import dataclass

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.principal import AuthenticatedPrincipal, actor_from_principal
from app.core.security import PasswordPolicyError, hash_password, validate_password
from app.models.catalog import BranchPricing
from app.models.enums import (
    AuthenticatedPrincipalType,
    BranchStatus,
    UserStatus,
    WorkshopStatus,
)
from app.models.identity import WorkshopUser
from app.models.workshop import Branch, Workshop
from app.schemas.platform import ProvisionWorkshopRequest
from app.schemas.workshop import dump_working_hours
from app.services.audit import record_action, record_status_change
from app.services.otp import normalize_uz_phone
from app.services.sessions import revoke_for_workshop

CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,31}$")


@dataclass(frozen=True)
class ProvisionedWorkshop:
    workshop: Workshop
    branch: Branch
    owner: WorkshopUser
    temp_password: str


async def list_workshops(db: AsyncSession) -> list[Workshop]:
    rows = (
        await db.scalars(select(Workshop).order_by(Workshop.created_at.desc(), Workshop.name))
    ).all()
    return list(rows)


async def get_workshop_detail(
    db: AsyncSession,
    *,
    workshop_id: uuid.UUID,
) -> tuple[Workshop, list[Branch], WorkshopUser]:
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
    return workshop, list(branches), owner


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
