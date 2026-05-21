"""User management — platform-user registry and workshop-staff + grants.

Provisioning a workshop with its first owner lives in the workshop module
(it creates the Workshop too); this module owns the user/grant mechanics it
calls into (docs/ref/features/access-management.md, platform.md).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, conflict, forbidden, not_found
from app.core.principal import Principal
from app.core.security import generate_temp_password, hash_password, password_complexity_ok
from app.models.enums import Permission, PrincipalType, UserStatus
from app.models.identity import PermissionGrant, PlatformUser, WorkshopUser
from app.models.workshop import Branch
from app.services import audit, sessions


@dataclass
class CreatedUser:
    user: PlatformUser | WorkshopUser
    temp_password: str


def _normalise_login(login: str) -> str:
    return login.strip().lower()


def _resolve_password(password: str | None) -> tuple[str, str]:
    """Return (plaintext, hash); generate a temp password when none supplied."""
    plaintext = password or generate_temp_password()
    if password and not password_complexity_ok(password):
        raise AppError(
            "weak_password",
            "Password must be ≥ 8 chars with an upper, a lower, and a digit.",
        )
    return plaintext, hash_password(plaintext)


# --- platform users --------------------------------------------------------


async def create_platform_user(
    db: AsyncSession,
    actor: Principal | None,
    *,
    full_name: str,
    login: str,
    phone: str,
    password: str | None = None,
) -> CreatedUser:
    login = _normalise_login(login)
    existing = (
        await db.execute(select(PlatformUser).where(PlatformUser.login == login))
    ).scalar_one_or_none()
    if existing is not None:
        raise conflict("That login is already taken.", code="login_taken")
    plaintext, password_hash = _resolve_password(password)
    user = PlatformUser(
        login=login,
        password_hash=password_hash,
        full_name=full_name.strip(),
        phone=phone.strip(),
        force_password_change=True,
    )
    db.add(user)
    await db.flush()
    await audit.record_action(
        db,
        actor=actor,
        action="platform_user.created",
        entity_type="platform_user",
        entity_id=user.id,
        summary=f"Created platform user {login}",
    )
    return CreatedUser(user=user, temp_password=plaintext)


async def list_platform_users(db: AsyncSession) -> list[PlatformUser]:
    return list(
        (await db.execute(select(PlatformUser).order_by(PlatformUser.created_at.desc())))
        .scalars()
        .all()
    )


async def _count_active_platform_users(db: AsyncSession) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(PlatformUser)
            .where(PlatformUser.status == UserStatus.ACTIVE)
        )
    ).scalar_one()


async def reset_platform_password(db: AsyncSession, actor: Principal, user_id: uuid.UUID) -> str:
    user = await db.get(PlatformUser, user_id)
    if user is None:
        raise not_found("Platform user not found.")
    plaintext, password_hash = _resolve_password(None)
    user.password_hash = password_hash
    user.force_password_change = True
    await sessions.revoke_all(db, PrincipalType.PLATFORM_USER, user.id)
    await audit.record_action(
        db,
        actor=actor,
        action="platform_user.password_reset",
        entity_type="platform_user",
        entity_id=user.id,
    )
    return plaintext


async def set_platform_user_status(
    db: AsyncSession, actor: Principal, user_id: uuid.UUID, *, blocked: bool
) -> PlatformUser:
    user = await db.get(PlatformUser, user_id)
    if user is None:
        raise not_found("Platform user not found.")
    if blocked:
        if user.id == actor.id:
            raise forbidden("You cannot block yourself.")
        if await _count_active_platform_users(db) <= 1 and user.status is UserStatus.ACTIVE:
            raise forbidden("There must be at least one active platform operator.")
        user.status = UserStatus.BLOCKED
        await sessions.revoke_all(db, PrincipalType.PLATFORM_USER, user.id)
    else:
        user.status = UserStatus.ACTIVE
    await audit.record_action(
        db,
        actor=actor,
        action="platform_user.blocked" if blocked else "platform_user.unblocked",
        entity_type="platform_user",
        entity_id=user.id,
    )
    return user


# --- workshop users + grants ----------------------------------------------


async def _validate_grants(
    db: AsyncSession, workshop_id: uuid.UUID, grants: list[tuple[Permission, uuid.UUID]]
) -> None:
    branch_ids = {b for (_, b) in grants}
    if not branch_ids:
        return
    rows = (
        (
            await db.execute(
                select(Branch.id).where(
                    Branch.id.in_(branch_ids), Branch.workshop_id == workshop_id
                )
            )
        )
        .scalars()
        .all()
    )
    if set(rows) != branch_ids:
        raise AppError("invalid_branch", "A grant references a branch outside this workshop.")


async def create_workshop_user(
    db: AsyncSession,
    owner: Principal,
    *,
    full_name: str,
    login: str,
    phone: str,
    home_branch_id: uuid.UUID | None,
    grants: list[tuple[Permission, uuid.UUID]] | None = None,
    password: str | None = None,
) -> CreatedUser:
    assert owner.workshop_id is not None
    login = _normalise_login(login)
    clash = (
        await db.execute(
            select(WorkshopUser).where(
                WorkshopUser.workshop_id == owner.workshop_id,
                WorkshopUser.login == login,
            )
        )
    ).scalar_one_or_none()
    if clash is not None:
        raise conflict("That login is already used in this workshop.", code="login_taken")
    if home_branch_id is not None:
        branch = await db.get(Branch, home_branch_id)
        if branch is None or branch.workshop_id != owner.workshop_id:
            raise AppError("invalid_branch", "Home branch is not in this workshop.")
    grants = grants or []
    await _validate_grants(db, owner.workshop_id, grants)
    plaintext, password_hash = _resolve_password(password)
    user = WorkshopUser(
        workshop_id=owner.workshop_id,
        login=login,
        password_hash=password_hash,
        full_name=full_name.strip(),
        phone=phone.strip(),
        is_owner=False,
        home_branch_id=home_branch_id,
        force_password_change=True,
    )
    db.add(user)
    await db.flush()
    for permission, branch_id in grants:
        db.add(
            PermissionGrant(
                workshop_user_id=user.id,
                permission=permission,
                branch_id=branch_id,
                granted_by_user_id=owner.id,
            )
        )
    await db.flush()
    await audit.record_action(
        db,
        actor=owner,
        action="workshop_user.created",
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=owner.workshop_id,
        summary=f"Created staff {login}",
    )
    return CreatedUser(user=user, temp_password=plaintext)


async def owned_workshop_user(
    db: AsyncSession, owner: Principal, user_id: uuid.UUID
) -> WorkshopUser:
    user = await db.get(WorkshopUser, user_id)
    if user is None or user.workshop_id != owner.workshop_id:
        raise not_found("Workshop user not found.")
    return user


async def list_workshop_users(db: AsyncSession, workshop_id: uuid.UUID) -> list[WorkshopUser]:
    return list(
        (
            await db.execute(
                select(WorkshopUser)
                .where(WorkshopUser.workshop_id == workshop_id)
                .order_by(WorkshopUser.is_owner.desc(), WorkshopUser.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def get_user_grants(db: AsyncSession, user_id: uuid.UUID) -> list[PermissionGrant]:
    return list(
        (
            await db.execute(
                select(PermissionGrant).where(PermissionGrant.workshop_user_id == user_id)
            )
        )
        .scalars()
        .all()
    )


async def edit_workshop_user(
    db: AsyncSession,
    owner: Principal,
    user_id: uuid.UUID,
    *,
    full_name: str | None = None,
    phone: str | None = None,
    home_branch_id: uuid.UUID | None = None,
    home_branch_set: bool = False,
) -> WorkshopUser:
    user = await owned_workshop_user(db, owner, user_id)
    if full_name is not None:
        user.full_name = full_name.strip()
    if phone is not None:
        user.phone = phone.strip()
    if home_branch_set:
        if home_branch_id is not None:
            branch = await db.get(Branch, home_branch_id)
            if branch is None or branch.workshop_id != owner.workshop_id:
                raise AppError("invalid_branch", "Home branch is not in this workshop.")
        user.home_branch_id = home_branch_id
    await audit.record_action(
        db,
        actor=owner,
        action="workshop_user.updated",
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=owner.workshop_id,
    )
    return user


async def set_workshop_user_grants(
    db: AsyncSession,
    owner: Principal,
    user_id: uuid.UUID,
    grants: list[tuple[Permission, uuid.UUID]],
) -> WorkshopUser:
    user = await owned_workshop_user(db, owner, user_id)
    if user.is_owner:
        raise forbidden("The owner already holds every permission.")
    assert owner.workshop_id is not None
    await _validate_grants(db, owner.workshop_id, grants)
    existing = await get_user_grants(db, user_id)
    for g in existing:
        await db.delete(g)
    await db.flush()
    deduped = sorted(set(grants), key=lambda g: (g[0].value, str(g[1])))
    for permission, branch_id in deduped:
        db.add(
            PermissionGrant(
                workshop_user_id=user.id,
                permission=permission,
                branch_id=branch_id,
                granted_by_user_id=owner.id,
            )
        )
    await db.flush()
    await audit.record_action(
        db,
        actor=owner,
        action="workshop_user.grants_set",
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=owner.workshop_id,
        details={"grants": [[p.value, str(b)] for p, b in deduped]},
    )
    return user


async def reset_workshop_password(db: AsyncSession, owner: Principal, user_id: uuid.UUID) -> str:
    user = await owned_workshop_user(db, owner, user_id)
    plaintext, password_hash = _resolve_password(None)
    user.password_hash = password_hash
    user.force_password_change = True
    await sessions.revoke_all(db, PrincipalType.WORKSHOP_USER, user.id)
    await audit.record_action(
        db,
        actor=owner,
        action="workshop_user.password_reset",
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=owner.workshop_id,
    )
    return plaintext


async def set_workshop_user_status(
    db: AsyncSession, owner: Principal, user_id: uuid.UUID, *, blocked: bool
) -> WorkshopUser:
    user = await owned_workshop_user(db, owner, user_id)
    if user.is_owner:
        raise forbidden("The owner cannot be blocked from inside the workshop.")
    user.status = UserStatus.BLOCKED if blocked else UserStatus.ACTIVE
    if blocked:
        await sessions.revoke_all(db, PrincipalType.WORKSHOP_USER, user.id)
    await audit.record_action(
        db,
        actor=owner,
        action="workshop_user.blocked" if blocked else "workshop_user.unblocked",
        entity_type="workshop_user",
        entity_id=user.id,
        workshop_id=owner.workshop_id,
    )
    return user
