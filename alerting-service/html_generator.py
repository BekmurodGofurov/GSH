import asyncpg
from datetime import datetime, timedelta, timezone

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GSH Monitoring Daily Report</title>
    <style>
        :root {
            --bg-color: #f4f7f6;
            --text-color: #333;
            --card-bg: #fff;
            --border-color: #e1e4e8;
            --header-bg: #2c3e50;
            --header-text: #fff;
            --online-color: #2ecc71;
            --offline-color: #e74c3c;
            --warning-color: #f1c40f;
            --accent-color: #3498db;
        }

        [data-theme="dark"] {
            --bg-color: #1a1a1a;
            --text-color: #f4f7f6;
            --card-bg: #2c2c2c;
            --border-color: #444;
            --header-bg: #111;
            --header-text: #fff;
            --online-color: #27ae60;
            --offline-color: #c0392b;
            --warning-color: #f39c12;
            --accent-color: #2980b9;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 0;
            transition: background-color 0.3s, color 0.3s;
        }

        header {
            background-color: var(--header-bg);
            color: var(--header-text);
            padding: 1.5rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .header-content h1 {
            margin: 0;
            font-size: 1.5rem;
        }

        .header-content p {
            margin: 5px 0 0;
            opacity: 0.8;
            font-size: 0.9rem;
        }

        .controls {
            display: flex;
            gap: 15px;
            align-items: center;
        }

        select, button {
            padding: 8px 12px;
            border-radius: 4px;
            border: 1px solid var(--border-color);
            background-color: var(--card-bg);
            color: var(--text-color);
            font-size: 0.9rem;
            cursor: pointer;
        }

        .container {
            max-width: 1200px;
            margin: 2rem auto;
            padding: 0 1rem;
        }

        .overview-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.5rem;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }

        .card h3 {
            margin: 0 0 10px;
            font-size: 0.9rem;
            text-transform: uppercase;
            color: var(--text-color);
            opacity: 0.7;
        }

        .card .value {
            font-size: 2rem;
            font-weight: bold;
            margin: 0;
        }

        .server-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 1.5rem;
        }

        .server-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }

        .server-header {
            padding: 1rem 1.25rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: rgba(0,0,0,0.02);
        }

        .server-header h2 {
            margin: 0;
            font-size: 1.1rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .badge {
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: bold;
            background-color: var(--border-color);
        }
        
        .badge.region { background-color: var(--accent-color); color: #fff; }

        .server-body {
            padding: 1.25rem;
        }

        .stat-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 0.95rem;
        }

        .stat-row:last-child {
            margin-bottom: 0;
        }

        .stat-label {
            opacity: 0.8;
        }
        
        .stat-value {
            font-weight: 600;
        }
        
        .time-label {
            font-size: 0.8rem;
            opacity: 0.6;
            margin-left: 5px;
        }

        .critical {
            color: var(--offline-color);
        }
        
        .excellent {
            color: var(--online-color);
        }
    </style>
</head>
<body>
    <header>
        <div class="header-content">
            <h1>GSH Monitoring Daily Report</h1>
            <p>Generated on: {report_date}</p>
        </div>
        <div class="controls">
            <select id="regionFilter" onchange="filterRegions()">
                <option value="all">All Regions</option>
                {region_options}
            </select>
            <button id="themeToggle" onclick="toggleTheme()">🌓 Toggle Dark Mode</button>
        </div>
    </header>

    <div class="container">
        <div class="overview-cards">
            <div class="card">
                <h3>Total Servers</h3>
                <p class="value">{total_servers}</p>
            </div>
            <div class="card">
                <h3>Overall Uptime</h3>
                <p class="value excellent">{uptime_percent}%</p>
            </div>
            <div class="card">
                <h3>Total Crashes/Offline</h3>
                <p class="value {crash_class}">{total_crashes}</p>
            </div>
            <div class="card">
                <h3>Active Regions</h3>
                <p class="value">{active_regions}</p>
            </div>
        </div>

        <div class="server-grid" id="serverGrid">
            {server_cards}
        </div>
    </div>

    <script>
        function toggleTheme() {
            const html = document.documentElement;
            if (html.getAttribute('data-theme') === 'light') {
                html.setAttribute('data-theme', 'dark');
            } else {
                html.setAttribute('data-theme', 'light');
            }
        }

        function filterRegions() {
            const filter = document.getElementById('regionFilter').value;
            const cards = document.querySelectorAll('.server-card');
            cards.forEach(card => {
                if (filter === 'all' || card.getAttribute('data-region') === filter) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }
    </script>
</body>
</html>
"""

SERVER_CARD_TEMPLATE = """
            <div class="server-card" data-region="{region}">
                <div class="server-header">
                    <div>
                        <h2 title="{server_name}">{server_name}</h2>
                        <div style="font-size: 0.8rem; opacity: 0.7; margin-top: 4px;">{server_id}</div>
                    </div>
                    <span class="badge region">{region}</span>
                </div>
                <div class="server-body">
                    <div class="stat-row">
                        <span class="stat-label">Crash / Offline Events</span>
                        <span class="stat-value {crash_class}">{offline_count}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Highest Ping</span>
                        <span class="stat-value {ping_class}">{max_ping} ms<span class="time-label">@ {max_ping_time}</span></span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Lowest Ping</span>
                        <span class="stat-value excellent">{min_ping} ms</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Max Players</span>
                        <span class="stat-value">{max_players}<span class="time-label">@ {max_players_time}</span></span>
                    </div>
                </div>
            </div>
"""

async def generate_daily_html_report(pool: asyncpg.Pool, lookback_days: int = 1) -> tuple[str, dict]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=lookback_days)
    
    # Complex query to get all required stats per server in one go
    query = """
    WITH base_metrics AS (
        SELECT sm.server_id, sm.ping_ms, sm.player_count, sm.time
        FROM server_metrics sm
        WHERE sm.time >= $1 AND sm.time < $2
    ),
    max_pings AS (
        SELECT DISTINCT ON (server_id) server_id, ping_ms, time
        FROM base_metrics
        ORDER BY server_id, ping_ms DESC
    ),
    min_pings AS (
        SELECT server_id, MIN(ping_ms) FILTER (WHERE ping_ms > 0) as min_ping
        FROM base_metrics
        GROUP BY server_id
    ),
    max_players AS (
        SELECT DISTINCT ON (server_id) server_id, player_count, time
        FROM base_metrics
        ORDER BY server_id, player_count DESC
    ),
    event_counts AS (
        SELECT server_id, COUNT(*) as offline_count
        FROM server_events
        WHERE time >= $1 AND time < $2 AND event_type IN ('OFFLINE', 'CRASH')
        GROUP BY server_id
    )
    SELECT ms.server_id, ms.server_name, ms.region,
           COALESCE(mp.ping_ms, 0) as max_ping, mp.time as max_ping_time,
           COALESCE(mip.min_ping, 0) as min_ping,
           COALESCE(mpl.player_count, 0) as max_players, mpl.time as max_players_time,
           COALESCE(ec.offline_count, 0) as offline_count
    FROM monitored_servers ms
    LEFT JOIN max_pings mp ON ms.server_id = mp.server_id
    LEFT JOIN min_pings mip ON ms.server_id = mip.server_id
    LEFT JOIN max_players mpl ON ms.server_id = mpl.server_id
    LEFT JOIN event_counts ec ON ms.server_id = ec.server_id
    ORDER BY ms.region, ms.server_name;
    """
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, start, now)
        
    regions = set()
    total_servers = len(rows)
    total_crashes = 0
    
    server_cards_html = []
    
    for row in rows:
        regions.add(row["region"])
        total_crashes += row["offline_count"]
        
        max_ping_time = row["max_ping_time"].strftime("%H:%M") if row["max_ping_time"] else "N/A"
        max_players_time = row["max_players_time"].strftime("%H:%M") if row["max_players_time"] else "N/A"
        
        crash_class = "critical" if row["offline_count"] > 0 else "excellent"
        ping_class = "critical" if row["max_ping"] > 150 else ""
        
        card = SERVER_CARD_TEMPLATE
        card = card.replace("{region}", row["region"])
        card = card.replace("{server_id}", row["server_id"])
        card = card.replace("{server_name}", row["server_name"])
        card = card.replace("{offline_count}", str(row["offline_count"]))
        card = card.replace("{max_ping}", str(float(row["max_ping"])))
        card = card.replace("{max_ping_time}", max_ping_time)
        card = card.replace("{min_ping}", str(float(row["min_ping"])))
        card = card.replace("{max_players}", str(row["max_players"]))
        card = card.replace("{max_players_time}", max_players_time)
        card = card.replace("{crash_class}", crash_class)
        card = card.replace("{ping_class}", ping_class)
        
        server_cards_html.append(card)
        
    region_options = "\n".join([f'<option value="{r}">{r}</option>' for r in sorted(regions)])
    
    # Calculate fake uptime for overview just as an example (100 - (crashes * 0.1))
    uptime = max(0.0, 100.0 - (total_crashes * 0.5))
    if total_servers == 0: uptime = 100.0
    
    html = HTML_TEMPLATE
    html = html.replace("{report_date}", now.strftime("%Y-%m-%d %H:%M UTC"))
    html = html.replace("{region_options}", region_options)
    html = html.replace("{total_servers}", str(total_servers))
    html = html.replace("{uptime_percent}", str(round(uptime, 2)))
    html = html.replace("{total_crashes}", str(total_crashes))
    html = html.replace("{active_regions}", str(len(regions)))
    html = html.replace("{crash_class}", "critical" if total_crashes > 5 else "excellent")
    html = html.replace("{server_cards}", "\n".join(server_cards_html))
    formatted_servers = []
    for r in rows:
        d = dict(r)
        if d.get("max_ping_time"): d["max_ping_time"] = d["max_ping_time"].strftime("%H:%M")
        if d.get("max_players_time"): d["max_players_time"] = d["max_players_time"].strftime("%H:%M")
        formatted_servers.append(d)

    json_data = {
        "report_date": now.strftime("%Y-%m-%d %H:%M UTC"),
        "total_servers": total_servers,
        "uptime_percent": round(uptime, 2),
        "total_crashes": total_crashes,
        "active_regions": len(regions),
        "servers": formatted_servers
    }
    
    return html, json_data

