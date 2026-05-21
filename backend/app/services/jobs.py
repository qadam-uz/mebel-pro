"""Scheduled-job implementations (docs/ref/features/platform.md).

Each takes a session and returns a short human summary stored on the JobRun.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BranchStatus
from app.models.inventory import StockItem
from app.models.workshop import Branch
from app.services import notifications as notif_service
from app.services import sessions as session_service
from app.services.recipients import low_stock_recipients

if TYPE_CHECKING:
    from app.services.scheduler import Scheduler

CLEANUP_SESSIONS = "cleanup-expired-sessions"
DAILY_LOW_STOCK = "daily-low-stock-summary"


async def cleanup_expired_sessions(db: AsyncSession) -> str:
    removed = await session_service.prune_expired(db)
    return f"Pruned {removed} expired session(s)."


async def daily_low_stock_summary(db: AsyncSession) -> str:
    """One coalesced notification per branch rolling up its low-stock items."""
    branches = (
        (await db.execute(select(Branch).where(Branch.status != BranchStatus.INACTIVE)))
        .scalars()
        .all()
    )
    total_notified = 0
    for branch in branches:
        low = (
            (
                await db.execute(
                    select(StockItem).where(
                        StockItem.branch_id == branch.id,
                        StockItem.on_hand <= StockItem.min_stock,
                    )
                )
            )
            .scalars()
            .all()
        )
        if not low:
            continue
        recipients = await low_stock_recipients(db, branch)
        total_notified += await notif_service.notify_many(
            db,
            recipients=recipients,
            event_code="warehouse.low_stock_summary",
            entity_type="branch",
            entity_id=branch.id,
            payload={"branch_name": branch.name, "low_count": len(low)},
        )
    return f"Low-stock summary fanned out to {total_notified} recipient(s)."


def register_default_jobs(scheduler: Scheduler) -> None:
    scheduler.register(CLEANUP_SESSIONS, 3600, cleanup_expired_sessions)
    scheduler.register(DAILY_LOW_STOCK, 86400, daily_low_stock_summary)
