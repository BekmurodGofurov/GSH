"""Shared SQL constants for gateway-api.

These live here rather than in main.py so that the agent tools can reuse
them without importing main. main.py imports app.agent.router at load
time, so a `import main` from anywhere under app/ closes an import cycle
-- and under `python main.py` (how the Dockerfile starts the service)
that cycle re-executes main.py under a second module name and crashes at
import with a partially initialized module. Keep this module free of any
app/ or main imports.
"""

# Every monitored server joined with its most recent metric row.
LATEST_SERVERS_QUERY = """
    SELECT
        ms.server_id,
        ms.server_name,
        ms.region,
        ms.status,
        ms.last_online_at,
        ms.last_offline_at,
        lm.player_count,
        lm.max_players,
        lm.ping_ms::double precision AS ping_ms,
        lm.time AS last_metric_at
    FROM monitored_servers ms
    LEFT JOIN LATERAL (
        SELECT time, player_count, max_players, ping_ms
        FROM server_metrics
        WHERE server_id = ms.server_id
        ORDER BY time DESC
        LIMIT 1
    ) lm ON TRUE
    ORDER BY ms.server_name;
"""

# A metric older than this is not "right now" any more. The poller sweeps
# every 3 seconds, so anything past two minutes means that server stopped
# reporting -- counting its last player number as live would overstate the
# fleet (and understate it once the row ages out of the window entirely).
LIVE_METRIC_MAX_AGE = "2 minutes"

# One row describing the whole fleet: how many servers, how many online,
# and how many players are on them right now.
#
# The agent used to answer "how many players are online?" by summing a
# truncated server list, which produced a number far below the real one.
# Summing in SQL removes both the truncation and the arithmetic from the
# model's hands.
FLEET_OVERVIEW_QUERY = f"""
    SELECT
        COUNT(*) AS total_servers,
        COUNT(*) FILTER (WHERE ms.status = 'ONLINE') AS online_servers,
        COUNT(*) FILTER (WHERE ms.status <> 'ONLINE') AS offline_servers,
        COUNT(*) FILTER (
            WHERE lm.time IS NULL
               OR lm.time < NOW() - INTERVAL '{LIVE_METRIC_MAX_AGE}'
        ) AS stale_servers,
        COALESCE(SUM(lm.player_count) FILTER (
            WHERE ms.status = 'ONLINE'
              AND lm.time > NOW() - INTERVAL '{LIVE_METRIC_MAX_AGE}'
        ), 0) AS total_players,
        COALESCE(SUM(lm.max_players) FILTER (
            WHERE ms.status = 'ONLINE'
              AND lm.time > NOW() - INTERVAL '{LIVE_METRIC_MAX_AGE}'
        ), 0) AS total_slots,
        ROUND(AVG(lm.ping_ms) FILTER (
            WHERE ms.status = 'ONLINE'
              AND lm.ping_ms > 0
              AND lm.time > NOW() - INTERVAL '{LIVE_METRIC_MAX_AGE}'
        ), 1)::double precision AS avg_ping,
        MAX(lm.time) AS last_metric_at
    FROM monitored_servers ms
    LEFT JOIN LATERAL (
        SELECT time, player_count, max_players, ping_ms
        FROM server_metrics
        WHERE server_id = ms.server_id
        ORDER BY time DESC
        LIMIT 1
    ) lm ON TRUE;
"""

# Per-server quality over a time window, for "which server is best?".
#
# A single latest ping (what LATEST_SERVERS_QUERY returns) is one UDP
# sample measured from the monitoring box while every other server is
# being queried at the same time, so it swings by tens of milliseconds
# between sweeps. Ranking on it alone put a different server on top each
# time it was asked. This query supplies what a stable answer needs
# instead: average ping over the window, how much it varies (jitter),
# the p95 tail, how often the server answered at all (uptime), and how
# many times it dropped out (crash_count).
#
# $1 is the window in hours -- a validated integer, never a string built
# from user input.
SERVER_RANKING_QUERY = """
    WITH window_metrics AS (
        SELECT
            sm.server_id,
            COUNT(*) AS sample_count,
            COUNT(*) FILTER (WHERE sm.ping_ms > 0) AS responsive_samples,
            AVG(sm.ping_ms) FILTER (WHERE sm.ping_ms > 0) AS avg_ping,
            STDDEV_SAMP(sm.ping_ms) FILTER (WHERE sm.ping_ms > 0) AS ping_jitter,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY sm.ping_ms)
                FILTER (WHERE sm.ping_ms > 0) AS p95_ping,
            MAX(sm.time) AS last_metric_at
        FROM server_metrics sm
        WHERE sm.time > NOW() - (INTERVAL '1 hour' * $1)
        GROUP BY sm.server_id
    ),
    window_events AS (
        SELECT
            se.server_id,
            COUNT(*) FILTER (WHERE se.event_type IN ('OFFLINE', 'CRASH')) AS crash_count,
            COUNT(*) FILTER (
                WHERE se.event_type NOT IN ('OFFLINE', 'CRASH', 'RECOVERY')
            ) AS anomaly_count
        FROM server_events se
        WHERE se.time > NOW() - (INTERVAL '1 hour' * $1)
        GROUP BY se.server_id
    )
    SELECT
        ms.server_id,
        ms.server_name,
        ms.region,
        ms.status,
        ROUND(wm.avg_ping, 1)::double precision AS avg_ping,
        ROUND(COALESCE(wm.ping_jitter, 0), 1)::double precision AS ping_jitter,
        ROUND(wm.p95_ping::numeric, 1)::double precision AS p95_ping,
        wm.sample_count,
        wm.responsive_samples,
        ROUND(
            100.0 * wm.responsive_samples / NULLIF(wm.sample_count, 0), 1
        )::double precision AS uptime_pct,
        wm.last_metric_at,
        COALESCE(we.crash_count, 0) AS crash_count,
        COALESCE(we.anomaly_count, 0) AS anomaly_count,
        lm.player_count,
        lm.max_players,
        lm.ping_ms::double precision AS current_ping,
        EXTRACT(EPOCH FROM (NOW() - wm.last_metric_at))::double precision AS metric_age_s
    FROM monitored_servers ms
    JOIN window_metrics wm ON wm.server_id = ms.server_id
    LEFT JOIN window_events we ON we.server_id = ms.server_id
    LEFT JOIN LATERAL (
        SELECT player_count, max_players, ping_ms
        FROM server_metrics
        WHERE server_id = ms.server_id
        ORDER BY time DESC
        LIMIT 1
    ) lm ON TRUE
    WHERE wm.avg_ping IS NOT NULL
    ORDER BY wm.avg_ping ASC;
"""
