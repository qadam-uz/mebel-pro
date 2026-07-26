"""Time-dimension counters for the platform dashboard.

Storage is UTC everywhere, but the business calendar is Uzbekistan's. Period
boundaries are therefore built in ``Asia/Tashkent`` and converted to UTC for the
query, so an order placed at 02:00 Tashkent counts toward *that* day instead of
the previous one (a naive UTC "day" rolls over at 05:00 local — invisible on a
lifetime total, fatal on a daily one).

The zone is a module constant on purpose: v1 is Uzbekistan-only and a setting
nobody would ever change is exactly the complexity the operating envelope rules
out. This is a presentation-boundary concern only — storage stays UTC.

Periods are **calendar** periods, not rolling windows: "oylik" is the 1st of
this month to now, so on the 1st it shows that day alone. The current bucket is
partial by design — that is what "this month so far" means.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

TASHKENT = ZoneInfo("Asia/Tashkent")

# Sparkline lengths — decorative-supporting trend, so a short honest window.
SPARK_DAYS = 14
SPARK_WEEKS = 12
SPARK_MONTHS = 12
SPARK_YEARS = 5


@dataclass(frozen=True)
class MetricSpark:
    """Bucket counts, oldest first. The last entry is the current, partial period."""

    daily: list[int]
    weekly: list[int]
    monthly: list[int]
    yearly: list[int]


@dataclass(frozen=True)
class MetricCounts:
    """Calendar-period counts plus the trend behind each of them."""

    daily: int
    weekly: int
    monthly: int
    yearly: int
    spark: MetricSpark


def _day_starts(now_local: datetime, count: int) -> list[datetime]:
    today = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return [today - timedelta(days=offset) for offset in reversed(range(count))]


def _week_starts(now_local: datetime, count: int) -> list[datetime]:
    # Monday 00:00 — `weekday()` is 0 for Monday, so this is the ISO week start.
    monday = now_local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=now_local.weekday()
    )
    return [monday - timedelta(weeks=offset) for offset in reversed(range(count))]


def _month_starts(now_local: datetime, count: int) -> list[datetime]:
    starts = []
    for offset in reversed(range(count)):
        months = now_local.year * 12 + (now_local.month - 1) - offset
        starts.append(
            now_local.replace(
                year=months // 12,
                month=months % 12 + 1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        )
    return starts


def _year_starts(now_local: datetime, count: int) -> list[datetime]:
    january = now_local.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return [january.replace(year=january.year - offset) for offset in reversed(range(count))]


def _bucket_bounds(starts: list[datetime], now: datetime) -> list[tuple[datetime, datetime]]:
    """Half-open [start, end) ranges in UTC; the newest bucket ends at `now`."""
    utc_starts = [start.astimezone(UTC) for start in starts]
    return list(zip(utc_starts, [*utc_starts[1:], now], strict=True))


def _bucket_count(
    column: InstrumentedAttribute[datetime],
    bounds: tuple[datetime, datetime],
) -> Any:
    start, end = bounds
    return func.count(case(((column >= start) & (column < end), 1)))


def _series_query(
    model: type[Any],
    column: InstrumentedAttribute[datetime],
    windows: list[list[tuple[datetime, datetime]]],
    now: datetime,
) -> Select[Any]:
    """One scan per table: every bucket of every granularity as a conditional count.

    Counting happens in SQL — no rows cross into Python. The scan is bounded by
    the oldest boundary (the 5-year sparkline) and by `now`, so rows dated into
    the future are excluded from every bucket rather than inflating "today".
    """
    columns = [_bucket_count(column, bounds) for window in windows for bounds in window]
    earliest = min(bounds[0] for window in windows for bounds in window)
    return select(*columns).select_from(model).where(column >= earliest, column < now)


async def count_by_period(
    db: AsyncSession,
    model: type[Any],
    column: InstrumentedAttribute[datetime],
    *,
    now: datetime,
) -> MetricCounts:
    """Calendar-period counts for one `created_at`-style column, Tashkent-aligned."""
    now_local = now.astimezone(TASHKENT)
    windows = [
        _bucket_bounds(_day_starts(now_local, SPARK_DAYS), now),
        _bucket_bounds(_week_starts(now_local, SPARK_WEEKS), now),
        _bucket_bounds(_month_starts(now_local, SPARK_MONTHS), now),
        _bucket_bounds(_year_starts(now_local, SPARK_YEARS), now),
    ]
    row = (await db.execute(_series_query(model, column, windows, now))).one()

    series: list[list[int]] = []
    cursor = 0
    for window in windows:
        series.append([int(value or 0) for value in row[cursor : cursor + len(window)]])
        cursor += len(window)
    daily, weekly, monthly, yearly = series

    # The current period *is* the newest bucket of its own series — one source
    # of truth, so the headline number and its trend can never disagree.
    return MetricCounts(
        daily=daily[-1],
        weekly=weekly[-1],
        monthly=monthly[-1],
        yearly=yearly[-1],
        spark=MetricSpark(daily=daily, weekly=weekly, monthly=monthly, yearly=yearly),
    )
