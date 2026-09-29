import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import HTTPException

# Import the SQL constants from queries.py, never from main: main imports
# this package at load time, so importing it back would close a cycle that
# crashes the service under `python main.py`.
from queries import LATEST_SERVERS_QUERY

# READ tools

async def get_server_summary(db_pool) -> list[dict]:
    """Return current status of every monitored server with latest metric."""
    # LATEST_SERVERS_QUERY joins monitored_servers with the most recent
    # server_metrics row -- the same query the REST endpoint serves.
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(LATEST_SERVERS_QUERY)
    return [dict(r) for r in rows]

async def get_recent_events(db_pool, limit: int = 10) -> list[dict]:
    """Return the last `limit` incident events from server_events."""
    # Fixed query — limit is a validated integer from EventQuery, passed as $1.
    # The LLM cannot change the SELECT columns or add WHERE conditions.
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, time, server_id, event_type, root_cause,
                   label_source, message, anomaly_score, diagnosis
            FROM server_events
            ORDER BY time DESC
            LIMIT $1;
            """,
            limit,
        )
    return [dict(r) for r in rows]


async def get_average_latency(
    db_pool, minutes: int = 10, server_id: str | None = None
) -> list[dict]:
    """Return avg ping and avg player count per server over the last N minutes."""
    # Two fixed queries — one with server filter, one without.
    # We never build a query string from user input.
    async with db_pool.acquire() as conn:
        if server_id:
            rows = await conn.fetch(
                """
                SELECT
                    time_bucket('1 minute', time) AS bucket,
                    server_id,
                    ROUND(AVG(ping_ms) FILTER (WHERE ping_ms > 0)::numeric, 2) AS avg_ping,
                    ROUND(AVG(player_count)::numeric, 1) AS avg_players
                FROM server_metrics
                WHERE time > NOW() - (INTERVAL '1 minute' * $1)
                  AND server_id = $2
                GROUP BY bucket, server_id
                ORDER BY bucket DESC;
                """,
                minutes,
                server_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    time_bucket('1 minute', time) AS bucket,
                    server_id,
                    ROUND(AVG(ping_ms) FILTER (WHERE ping_ms > 0)::numeric, 2) AS avg_ping,
                    ROUND(AVG(player_count)::numeric, 1) AS avg_players
                FROM server_metrics
                WHERE time > NOW() - (INTERVAL '1 minute' * $1)
                GROUP BY bucket, server_id
                ORDER BY bucket DESC;
                """,
                minutes,
            )
    return [dict(r) for r in rows]

# WRITE tool 

async def relabel_event(db_pool, event_id: int, root_cause: str) -> dict:
    """Re-label an incident's root cause. Same DB write as POST /api/v1/events/{id}/label."""
    # root_cause was validated by RelabelRequest.Literal — only 6 values are possible.
    # event_id was validated gt=0.  Neither was constructed from free user text.
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE server_events
            SET root_cause = $1, label_source = 'manual'
            WHERE id = $2;
            """,
            root_cause,
            event_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return {
        "event_id": event_id,
        "root_cause": root_cause,
        "label_source": "manual",
        "status": "relabelled",
    }


async def acknowledge_event(db_pool, event_id: int) -> dict:
    """Acknowledge an incident so repeated Telegram alerts stop firing for it."""
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE server_events
            SET is_acknowledged = TRUE,
                acknowledged_by = 'agent',
                acknowledged_at = NOW()
            WHERE id = $1;
            """,
            event_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return {"event_id": event_id, "status": "acknowledged"}


async def mute_server_alerts(db_pool, server_id: str, minutes: int, reason: str | None = None) -> dict:
    """Temporarily silence Telegram alerts for a server for the given number of minutes."""
    from datetime import datetime, timezone, timedelta
    muted_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    async with db_pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM monitored_servers WHERE server_id = $1;", server_id
        )
        if not exists:
            raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")
        row = await conn.fetchrow(
            """
            INSERT INTO alert_silences (server_id, muted_until, muted_by, reason)
            VALUES ($1, $2, 'agent', $3)
            RETURNING id, muted_until;
            """,
            server_id,
            muted_until,
            reason,
        )
    return {
        "server_id": server_id,
        "muted_until": row["muted_until"].isoformat(),
        "silence_id": row["id"],
        "status": "muted",
    }


async def poll_server_now(db_pool, server_id: str) -> dict:
    """Immediately fetch fresh metrics for a server without waiting for the polling loop."""
    import httpx, os
    ingestion_url = os.getenv("INGESTION_INTERNAL_URL", "http://ingestion-service:8001")
    url = f"{ingestion_url}/api/v1/servers/{server_id}/poll"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Ingestion service unreachable: {exc}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")
    return resp.json()


async def generate_daily_report(db_pool) -> dict:
    """Return today's daily summary report from the cache."""
    import datetime as _dt, json as _json
    today = _dt.date.today()
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT report_text, json_data FROM daily_reports WHERE report_date = $1;",
            today,
        )
    if not row:
        return {
            "status": "not_generated",
            "message": "Today's report has not been generated yet. Use /report in Telegram to trigger it now.",
        }
    return {
        "report_date": today.isoformat(),
        "report_text": row["report_text"],
        "json_data": _json.loads(row["json_data"]) if row["json_data"] else None,
    }