"""Dev/test seed helpers for foundation fixtures."""

import uuid
from decimal import Decimal

from app.core.security import hash_password
from app.modules.access.contracts import PlatformUser, WorkshopUser
from app.modules.workshop.api import next_branch_no
from app.modules.workshop.contracts import Branch, Workshop
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_platform_user(
    db: AsyncSession,
    *,
    login: str = "admin",
    password: str = "Admin123",
    password_reset_required: bool = True,
) -> PlatformUser:
    user = PlatformUser(
        login=login,
        password_hash=hash_password(password),
        full_name="Platform Admin",
        phone="+998901234567",
        password_reset_required=password_reset_required,
    )
    db.add(user)
    await db.flush()
    return user


async def seed_workshop_with_owner(
    db: AsyncSession,
    *,
    login: str = "owner",
) -> tuple[Workshop, Branch, WorkshopUser]:
    """Seed a workshop with its owner. Logins are globally unique — pass a distinct
    `login` when a test seeds more than one workshop."""
    workshop_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    workshop = Workshop(
        id=workshop_id,
        owner_user_id=owner_id,
        name="Demo Workshop",
    )
    db.add(workshop)
    await db.flush()
    branch = Branch(
        workshop_id=workshop.id,
        branch_no=await next_branch_no(db),
        name="Yunusobod",
        address="Tashkent, Yunusobod",
        phone="+998902222222",
        latitude=Decimal("41.365"),
        longitude=Decimal("69.285"),
    )
    db.add(branch)
    await db.flush()
    owner = WorkshopUser(
        id=owner_id,
        workshop_id=workshop.id,
        login=login,
        password_hash=hash_password("Owner123"),
        full_name="Workshop Owner",
        phone="+998903333333",
        is_owner=True,
        home_branch_id=branch.id,
    )
    db.add(owner)
    await db.flush()
    return workshop, branch, owner
