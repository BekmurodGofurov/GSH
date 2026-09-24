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
