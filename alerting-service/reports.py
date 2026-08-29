from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TypedDict

import asyncpg

class HighestPingResult(TypedDict):
    server_name: str
    server_id: str
    region: str
    max_ping_ms: float
    recorded_at: datetime


class TopCrasherResult(TypedDict):
    server_name: str
    server_id: str
    region: str
    crash_count: int


class EventSummary(TypedDict):
    crash: int
    offline: int
    high_ping: int
    recovery: int
    total: int


class ServerStatusSummary(TypedDict):
    total: int
    online: int
    offline: int


class AvgPingResult(TypedDict):
    server_name: str
    server_id: str
    region: str
    avg_ping_ms: float


class DailyReport(TypedDict):
    report_date: str
    window_label: str          # "So'nggi 5 daqiqa" yoki "Bugun (28-avg)"
    highest_ping: HighestPingResult | None
    avg_pings: list[AvgPingResult]   # top 3 eng yuqori avg ping serverlar
    top_crashers: list[TopCrasherResult]
    event_summary: EventSummary
    server_statuses: ServerStatusSummary

def _time_window(lookback_minutes: int | None = None, lookback_days: int | None = None) -> tuple[datetime, datetime]:
    """
    Tahlil uchun vaqt oynasini qaytaradi.
    lookback_minutes berilsa — minutlar bo'yicha,
    lookback_days berilsa — kunlar bo'yicha.
    """
    now = datetime.now(timezone.utc)
    if lookback_minutes is not None:
        start = now - timedelta(minutes=lookback_minutes)
    elif lookback_days is not None:
        start = now - timedelta(days=lookback_days)
    else:
        start = now - timedelta(minutes=5)
    return start, now

async def get_highest_ping(
    pool: asyncpg.Pool,
    lookback_minutes: int | None = None,
    lookback_days: int | None = None,
) -> HighestPingResult | None:
    """Eng baland ping qayd etilgan server va vaqtni qaytaradi."""
    start, end = _time_window(lookback_minutes, lookback_days)
    query = """
        SELECT
            sm.ping_ms        AS max_ping_ms,
            sm.time           AS recorded_at,
            sm.server_id,
            ms.server_name,
            ms.region
        FROM server_metrics sm
        JOIN monitored_servers ms ON ms.server_id = sm.server_id
        WHERE sm.time >= $1
          AND sm.time <  $2
          AND sm.ping_ms IS NOT NULL
        ORDER BY sm.ping_ms DESC
        LIMIT 1;
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, start, end)

    if row is None:
        return None

    return HighestPingResult(
        server_name=row["server_name"],
        server_id=row["server_id"],
        region=row["region"],
        max_ping_ms=float(row["max_ping_ms"]),
        recorded_at=row["recorded_at"],
    )


async def get_avg_pings(
    pool: asyncpg.Pool,
    lookback_minutes: int | None = None,
    lookback_days: int | None = None,
    limit: int = 3,
) -> list[AvgPingResult]:
    """Vaqt oynasida o'rtacha ping bo'yicha TOP N server."""
    start, end = _time_window(lookback_minutes, lookback_days)
    query = """
        SELECT
            sm.server_id,
            ms.server_name,
            ms.region,
            AVG(sm.ping_ms) AS avg_ping_ms
        FROM server_metrics sm
        JOIN monitored_servers ms ON ms.server_id = sm.server_id
        WHERE sm.time >= $1
          AND sm.time <  $2
          AND sm.ping_ms IS NOT NULL
        GROUP BY sm.server_id, ms.server_name, ms.region
        ORDER BY avg_ping_ms DESC
        LIMIT $3;
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, start, end, limit)

    return [
        AvgPingResult(
            server_name=row["server_name"],
            server_id=row["server_id"],
            region=row["region"],
            avg_ping_ms=float(row["avg_ping_ms"]),
        )
        for row in rows
    ]


async def get_top_crashers(
    pool: asyncpg.Pool,
    lookback_minutes: int | None = None,
    lookback_days: int | None = None,
    limit: int = 5,
) -> list[TopCrasherResult]:
    """Eng ko'p CRASH / OFFLINE event bo'lgan serverlar."""
    start, end = _time_window(lookback_minutes, lookback_days)
    query = """
        SELECT
            se.server_id,
            ms.server_name,
            ms.region,
            COUNT(*) AS crash_count
        FROM server_events se
        JOIN monitored_servers ms ON ms.server_id = se.server_id
        WHERE se.time >= $1
          AND se.time <  $2
          AND se.event_type IN ('CRASH', 'OFFLINE')
        GROUP BY se.server_id, ms.server_name, ms.region
        ORDER BY crash_count DESC
        LIMIT $3;
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, start, end, limit)

    return [
        TopCrasherResult(
            server_name=row["server_name"],
            server_id=row["server_id"],
            region=row["region"],
            crash_count=row["crash_count"],
        )
        for row in rows
    ]


async def get_event_summary(
    pool: asyncpg.Pool,
    lookback_minutes: int | None = None,
    lookback_days: int | None = None,
) -> EventSummary:
    """Voqealar turi bo'yicha soni."""
    start, end = _time_window(lookback_minutes, lookback_days)
    query = """
        SELECT event_type, COUNT(*) AS cnt
        FROM server_events
        WHERE time >= $1
          AND time <  $2
        GROUP BY event_type;
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, start, end)

    counts: dict[str, int] = {row["event_type"]: row["cnt"] for row in rows}
    crash     = counts.get("CRASH", 0)
    offline   = counts.get("OFFLINE", 0)
    high_ping = counts.get("HIGH_PING", 0)
    recovery  = counts.get("RECOVERY", 0)

    return EventSummary(
        crash=crash,
        offline=offline,
        high_ping=high_ping,
        recovery=recovery,
        total=sum(counts.values()),
    )


async def get_server_statuses(pool: asyncpg.Pool) -> ServerStatusSummary:
    """Hozirgi ONLINE/OFFLINE holatlar soni (vaqt oynasiga bog'liq emas)."""
    query = """
        SELECT
            COUNT(*)                                      AS total,
            COUNT(*) FILTER (WHERE status = 'ONLINE')    AS online,
            COUNT(*) FILTER (WHERE status = 'OFFLINE')   AS offline
        FROM monitored_servers;
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query)

    return ServerStatusSummary(
        total=row["total"],
        online=row["online"],
        offline=row["offline"],
    )

async def build_report(
    pool: asyncpg.Pool,
    lookback_minutes: int | None = None,
    lookback_days: int | None = None,
) -> DailyReport:
    """Barcha so'rovlarni parallel ravishda bajarib, to'liq hisobot qaytaradi."""

    kwargs = dict(lookback_minutes=lookback_minutes, lookback_days=lookback_days)

    (
        highest_ping,
        avg_pings,
        top_crashers,
        event_summary,
        server_statuses,
    ) = await asyncio.gather(
        get_highest_ping(pool, **kwargs),
        get_avg_pings(pool, **kwargs, limit=3),
        get_top_crashers(pool, **kwargs, limit=5),
        get_event_summary(pool, **kwargs),
        get_server_statuses(pool),
    )

    now_utc = datetime.now(timezone.utc)
    report_date = now_utc.strftime("%Y-%m-%d %H:%M UTC")

    if lookback_minutes is not None:
        window_label = f"So'nggi {lookback_minutes} daqiqa"
    else:
        window_label = f"So'nggi {lookback_days} kun"

    return DailyReport(
        report_date=report_date,
        window_label=window_label,
        highest_ping=highest_ping,
        avg_pings=avg_pings,
        top_crashers=top_crashers,
        event_summary=event_summary,
        server_statuses=server_statuses,
    )
