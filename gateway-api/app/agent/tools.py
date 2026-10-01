import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import HTTPException

# Import the SQL constants from queries.py, never from main: main imports
# this package at load time, so importing it back would close a cycle that
# crashes the service under `python main.py`.
from queries import (
    FLEET_OVERVIEW_QUERY,
    LATEST_SERVERS_QUERY,
    SERVER_RANKING_QUERY,
)

# A metric this old is no longer "now" -- matches LIVE_METRIC_MAX_AGE in
# queries.py. A server whose last sample is older than this is dropped from
# the ranking: its numbers describe a server that stopped reporting.
_LIVE_METRIC_MAX_AGE_S = 120

# Ranking weights, all in "equivalent milliseconds of ping" so they can be
# summed into one score where lower is better.
#
# The point of the weights is that a server is not best just because one
# UDP sample came back fast. Dropping out costs far more than being a few
# milliseconds slower, so a server with 0 crashes and 60ms ping outranks
# one with 2 crashes and 25ms ping. Jitter is weighted next: a server whose
# ping swings ±30ms plays worse than one steady at a higher number.
_CRASH_PENALTY = 40.0       # per OFFLINE/CRASH event in the window
_ANOMALY_PENALTY = 8.0      # per other incident (high ping, player drop…)
_DOWNTIME_PENALTY = 3.0     # per percentage point of missed polls
_JITTER_PENALTY = 2.0       # per ms of ping standard deviation

# READ tools

async def get_server_summary(db_pool) -> list[dict]:
    """Return current status of every monitored server with latest metric."""
    # LATEST_SERVERS_QUERY joins monitored_servers with the most recent
    # server_metrics row -- the same query the REST endpoint serves.
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(LATEST_SERVERS_QUERY)
    return [dict(r) for r in rows]

async def get_fleet_overview(db_pool) -> dict:
    """Return one row of counts for the whole fleet: servers, players, avg ping.

    Counting questions ("how many servers are online?", "how many players
    are on right now?") are answered from this, not from the server list:
    the model never sees a truncated list it has to add up itself.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(FLEET_OVERVIEW_QUERY)
    if not row:
        return {
            "total_servers": 0,
            "online_servers": 0,
            "offline_servers": 0,
            "total_players": 0,
            "total_slots": 0,
            "avg_ping": None,
            "stale_servers": 0,
        }
    data = dict(row)
    # The player total only covers servers that are reporting. Say so when
    # some are not, instead of presenting a short count as the whole fleet.
    if data.get("stale_servers"):
        data["note"] = (
            f"{data['stale_servers']} server(s) have not reported in the last "
            "2 minutes and are not included in the player count."
        )
    return data


def _ping_is_stable(avg_ping: float, jitter: float) -> bool:
    """Ping counts as stable when it varies by less than 15% of its average."""
    if not avg_ping:
        return False
    return jitter <= max(5.0, avg_ping * 0.15)


def _describe(row: dict, hours: int) -> list[str]:
    """Plain-language reasons for a server's placing, for the agent to read out."""
    reasons: list[str] = []
    avg_ping = row.get("avg_ping") or 0.0
    jitter = row.get("ping_jitter") or 0.0
    crashes = row.get("crash_count") or 0
    uptime = row.get("uptime_pct")

    if _ping_is_stable(avg_ping, jitter):
        reasons.append(f"ping is steady at {avg_ping}ms (varies ±{jitter}ms)")
    else:
        reasons.append(f"ping averages {avg_ping}ms but swings ±{jitter}ms")

    window = f"the last {hours} hour" + ("s" if hours != 1 else "")
    if crashes:
        reasons.append(f"went offline {crashes} time(s) in {window}")
    else:
        reasons.append(f"no crashes in {window}")

    if uptime is not None and uptime < 100:
        reasons.append(f"answered {uptime}% of health checks")

    anomalies = row.get("anomaly_count") or 0
    if anomalies:
        reasons.append(f"{anomalies} other incident(s) logged in {window}")

    return reasons


async def get_server_ranking(db_pool, hours: int = 1) -> dict:
    """Rank servers over the last `hours` by stability first, then latency.

    Returns every eligible server with the numbers behind its placing
    (average ping, jitter, crash count, uptime) and a sentence explaining
    why the top one won, so the agent can justify the pick rather than
    just naming the lowest ping it happened to see.
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(SERVER_RANKING_QUERY, hours)

    ranked: list[dict] = []
    excluded: list[dict] = []

    for raw in rows:
        row = dict(raw)
        age = row.get("metric_age_s")
        if row.get("status") != "ONLINE":
            excluded.append({"server_id": row["server_id"], "excluded_because": "server is offline"})
            continue
        if age is not None and age > _LIVE_METRIC_MAX_AGE_S:
            excluded.append({
                "server_id": row["server_id"],
                "excluded_because": f"no health check in {int(age)}s",
            })
            continue

        uptime = row.get("uptime_pct")
        row["score"] = round(
            (row.get("avg_ping") or 0.0)
            + (row.get("crash_count") or 0) * _CRASH_PENALTY
            + (row.get("anomaly_count") or 0) * _ANOMALY_PENALTY
            + (100.0 - (uptime if uptime is not None else 100.0)) * _DOWNTIME_PENALTY
            + (row.get("ping_jitter") or 0.0) * _JITTER_PENALTY,
            1,
        )
        row["reasons"] = _describe(row, hours)
        ranked.append(row)

    ranked.sort(key=lambda r: r["score"])
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i

    result = {
        "window_hours": hours,
        "ranked": ranked,
        "excluded": excluded,
        "ranked_by": (
            "stability first (crashes, uptime, ping jitter), then average ping. "
            "Lower score is better."
        ),
    }

    if ranked:
        best = ranked[0]
        result["best"] = best
        if len(ranked) > 1:
            runner_up = ranked[1]
            result["why_best"] = _compare(best, runner_up, hours)
        else:
            result["why_best"] = f"{best['server_name']} is the only eligible server."

    return result


def _compare(best: dict, runner_up: dict, hours: int) -> str:
    """One sentence on what separates the winner from the next server."""
    window = f"the last {hours} hour" + ("s" if hours != 1 else "")
    best_ping = best.get("avg_ping") or 0.0
    next_ping = runner_up.get("avg_ping") or 0.0

    if (best.get("crash_count") or 0) < (runner_up.get("crash_count") or 0):
        return (
            f"{best['server_name']} wins on stability: {best.get('crash_count', 0)} crashes "
            f"versus {runner_up.get('crash_count', 0)} for {runner_up['server_name']} over {window}, "
            f"at {best_ping}ms average ping."
        )
    if best_ping > next_ping:
        return (
            f"{best['server_name']} has a higher ping than {runner_up['server_name']} "
            f"({best_ping}ms vs {next_ping}ms) but holds it steadier "
            f"(±{best.get('ping_jitter', 0)}ms vs ±{runner_up.get('ping_jitter', 0)}ms) "
            f"and stayed up through {window}."
        )
    return (
        f"{best['server_name']} leads on both latency ({best_ping}ms vs {next_ping}ms) "
        f"and stability over {window}."
    )


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