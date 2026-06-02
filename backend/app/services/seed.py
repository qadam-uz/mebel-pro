"""Dev/test seed helpers for foundation fixtures."""

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.identity import PlatformUser, WorkshopUser
from app.models.workshop import Branch, Workshop


async def seed_platform_user(
    db: AsyncSession,
    *,
    login: str = "admin",
    password: str = "Admin123",  # noqa: S107 - deterministic dev/test seed only.
) -> PlatformUser:
    user = PlatformUser(
        login=login,
        password_hash=hash_password(password),
        full_name="Platform Admin",
        phone="+998901234567",
    )
    db.add(user)
    await db.flush()
    return user


async def seed_workshop_with_owner(db: AsyncSession) -> tuple[Workshop, Branch, WorkshopUser]:
    workshop_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    workshop = Workshop(
        id=workshop_id,
        owner_user_id=owner_id,
        name="Demo Workshop",
        phone="+998901111111",
        address="Tashkent",
    )
    db.add(workshop)
    await db.flush()
    branch = Branch(
        workshop_id=workshop.id,
        name="Yunusobod",
        address="Tashkent, Yunusobod",
        phone="+998902222222",
        latitude=Decimal("41.365"),
        longitude=Decimal("69.285"),
        working_hours={},
    )
    db.add(branch)
    await db.flush()
    owner = WorkshopUser(
        id=owner_id,
        workshop_id=workshop.id,
        login="owner",
        password_hash=hash_password("Owner123"),
        full_name="Workshop Owner",
        phone="+998903333333",
        is_owner=True,
        home_branch_id=branch.id,
    )
    db.add(owner)
    await db.flush()
    return workshop, branch, owner
