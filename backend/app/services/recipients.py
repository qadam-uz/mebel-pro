"""Resolve notification recipients for workshop-scoped events.

A workshop-wide event fans out to the owner plus the staff who hold the
relevant grant on the branch (docs/ref/features/notifications.md).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Permission, PrincipalType, UserStatus
from app.models.identity import PermissionGrant, WorkshopUser
from app.models.workshop import Branch

Recipient = tuple[PrincipalType, uuid.UUID]


async def owner_id(db: AsyncSession, workshop_id: uuid.UUID) -> uuid.UUID | None:
    return (
        await db.execute(
            select(WorkshopUser.id).where(
                WorkshopUser.workshop_id == workshop_id,
                WorkshopUser.is_owner.is_(True),
            )
        )
    ).scalar_one_or_none()


async def staff_with_permission(
    db: AsyncSession, branch_id: uuid.UUID, permission: Permission
) -> list[uuid.UUID]:
    rows = (
        (
            await db.execute(
                select(PermissionGrant.workshop_user_id)
                .join(WorkshopUser, WorkshopUser.id == PermissionGrant.workshop_user_id)
                .where(
                    PermissionGrant.branch_id == branch_id,
                    PermissionGrant.permission == permission,
                    WorkshopUser.status == UserStatus.ACTIVE,
                )
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def branch_recipients(
    db: AsyncSession, workshop_id: uuid.UUID, branch_id: uuid.UUID, permission: Permission
) -> list[Recipient]:
    """Owner + active staff with ``permission`` on the branch."""
    ids: set[uuid.UUID] = set(await staff_with_permission(db, branch_id, permission))
    owner = await owner_id(db, workshop_id)
    if owner is not None:
        ids.add(owner)
    return [(PrincipalType.WORKSHOP_USER, uid) for uid in ids]


async def low_stock_recipients(db: AsyncSession, branch: Branch) -> list[Recipient]:
    return await branch_recipients(db, branch.workshop_id, branch.id, Permission.MANAGE_INVENTORY)
