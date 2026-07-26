"""Calendar-period counters behind the platform dashboard (AB-119).

The whole point of these counters is that they are *Tashkent* calendar periods
over UTC storage. A naive UTC day rolls over at 05:00 local, which silently
misfiles every order taken between midnight and 5am — so the boundary cases are
the tests that matter. `Client` stands in for any `created_at` table: the
bucketing in `metrics.py` is model-agnostic and the wiring for orders and
workshops is covered through the overview endpoint.
"""

from datetime import UTC, datetime

from app.modules.access.contracts import Client
from app.modules.platform.metrics import (
    SPARK_DAYS,
    SPARK_MONTHS,
    SPARK_WEEKS,
    SPARK_YEARS,
    MetricCounts,
    count_by_period,
)
from sqlalchemy.ext.asyncio import AsyncSession


async def _add_client(db: AsyncSession, *, created_at: datetime, phone: str) -> None:
    db.add(Client(phone=phone, name="Registered", created_at=created_at))
    await db.flush()


async def _counts(db: AsyncSession, *, now: datetime) -> MetricCounts:
    return await count_by_period(db, Client, Client.created_at, now=now)


async def test_daily_count_rolls_over_at_tashkent_midnight_not_utc(
    db_session: AsyncSession,
) -> None:
    # Sunday 2026-03-15, 11:00 in Tashkent. The local day opened at 19:00 UTC
    # the calendar day before.
    now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
    # 02:30 Tashkent *today* — the row a UTC-based day would misfile as yesterday.
    await _add_client(
        db_session, created_at=datetime(2026, 3, 14, 21, 30, tzinfo=UTC), phone="+998901000001"
    )
    # 23:00 Tashkent yesterday — genuinely yesterday, and must stay there.
    await _add_client(
        db_session, created_at=datetime(2026, 3, 14, 18, 0, tzinfo=UTC), phone="+998901000002"
    )

    counts = await _counts(db_session, now=now)

    assert counts.daily == 1
    assert counts.spark.daily[-1] == 1
    assert counts.spark.daily[-2] == 1


async def test_monthly_count_is_the_calendar_month_not_a_rolling_window(
    db_session: AsyncSession,
) -> None:
    # The 1st of April in Tashkent: "oylik" must show that one day only.
    now = datetime(2026, 4, 1, 6, 0, tzinfo=UTC)
    # 00:30 Tashkent on 1 April.
    await _add_client(
        db_session, created_at=datetime(2026, 3, 31, 19, 30, tzinfo=UTC), phone="+998901000001"
    )
    # Twelve days earlier — inside a 30-day rolling window, outside April.
    await _add_client(
        db_session, created_at=datetime(2026, 3, 20, 12, 0, tzinfo=UTC), phone="+998901000002"
    )

    counts = await _counts(db_session, now=now)

    assert counts.monthly == 1
    assert counts.spark.monthly[-2] == 1


async def test_weekly_count_starts_on_monday(db_session: AsyncSession) -> None:
    # Sunday 2026-03-15 in Tashkent; the current week opened Monday 2026-03-09.
    now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
    # 00:30 Tashkent on Monday 9 March — the first minutes of this week.
    await _add_client(
        db_session, created_at=datetime(2026, 3, 8, 19, 30, tzinfo=UTC), phone="+998901000001"
    )
    # 23:00 Tashkent on Sunday 8 March — last week, unless weeks start Sunday.
    await _add_client(
        db_session, created_at=datetime(2026, 3, 8, 18, 0, tzinfo=UTC), phone="+998901000002"
    )

    counts = await _counts(db_session, now=now)

    assert counts.weekly == 1
    assert counts.spark.weekly[-2] == 1


async def test_yearly_count_is_the_calendar_year(db_session: AsyncSession) -> None:
    now = datetime(2026, 1, 1, 6, 0, tzinfo=UTC)
    # 00:30 Tashkent on 1 January 2026.
    await _add_client(
        db_session, created_at=datetime(2025, 12, 31, 19, 30, tzinfo=UTC), phone="+998901000001"
    )
    # 23:00 Tashkent on 31 December 2025 — the previous year.
    await _add_client(
        db_session, created_at=datetime(2025, 12, 31, 18, 0, tzinfo=UTC), phone="+998901000002"
    )

    counts = await _counts(db_session, now=now)

    assert counts.yearly == 1
    assert counts.spark.yearly[-2] == 1


async def test_spark_series_keep_their_length_on_an_empty_platform(
    db_session: AsyncSession,
) -> None:
    # A brand-new platform must render as flat zeroes, not as a missing chart.
    counts = await _counts(db_session, now=datetime(2026, 3, 15, 6, 0, tzinfo=UTC))

    assert [len(counts.spark.daily), len(counts.spark.weekly)] == [SPARK_DAYS, SPARK_WEEKS]
    assert [len(counts.spark.monthly), len(counts.spark.yearly)] == [SPARK_MONTHS, SPARK_YEARS]
    assert set(counts.spark.daily) == {0}
    assert (counts.daily, counts.weekly, counts.monthly, counts.yearly) == (0, 0, 0, 0)


async def test_rows_dated_into_the_future_do_not_inflate_the_current_period(
    db_session: AsyncSession,
) -> None:
    # 21:30 UTC is 02:30 Tashkent *tomorrow* — a later day, not today's number.
    now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
    await _add_client(
        db_session, created_at=datetime(2026, 3, 15, 21, 30, tzinfo=UTC), phone="+998901000001"
    )

    counts = await _counts(db_session, now=now)

    assert counts.daily == 0
    assert counts.monthly == 0
