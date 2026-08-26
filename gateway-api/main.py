from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
import asyncpg
import asyncio
import os
app = FastAPI(
    title="CS2 Monitor Gateway API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_URL = os.getenv("DB_URL", "postgresql://postgres:postgrespassword@localhost:5433/game_monitor")
db_pool = None

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

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DB_URL)

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

# 1. Barcha serverlar ro'yxati va statusi
@app.get("/api/v1/servers")
async def get_servers():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(LATEST_SERVERS_QUERY)
        return [dict(r) for r in rows]

# 2. Server metriklari tarixi
@app.get("/api/v1/servers/{server_id:path}/metrics")
async def get_server_metrics(server_id: str, limit: int = Query(30, ge=5, le=300)):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT time, player_count, max_players, ping_ms
            FROM server_metrics
            WHERE server_id = $1
            ORDER BY time DESC
            LIMIT $2;
        """, server_id, limit)
        return [dict(r) for r in rows]

# 3. Server hodisalari va Crash loglari
@app.get("/api/v1/events")
async def get_events(limit: int = Query(20, ge=1, le=100)):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, time, server_id, event_type, message
            FROM server_events
            ORDER BY time DESC
            LIMIT $1;
        """, limit)
        return [dict(r) for r in rows]

# 4. TimescaleDB Agregatsiyasi (Daqiqalik o'rtacha metrikalar)
@app.get("/api/v1/analytics/ping-buckets")
async def get_ping_analytics(minutes: int = Query(10, ge=1, le=60)):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                time_bucket('1 minute', time) AS bucket,
                server_id,
                ROUND(AVG(ping_ms)::numeric, 2) AS avg_ping,
                ROUND(AVG(player_count)::numeric, 1) AS avg_players
            FROM server_metrics
            WHERE time > NOW() - (INTERVAL '1 minute' * $1)
            GROUP BY bucket, server_id
            ORDER BY bucket DESC;
        """, minutes)
        return [dict(r) for r in rows]

# 5. Live WebSocket (Frontend uchun real-time stream)
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            async with db_pool.acquire() as conn:
                servers = await conn.fetch(LATEST_SERVERS_QUERY)
                events = await conn.fetch("SELECT * FROM server_events ORDER BY time DESC LIMIT 5;")
                
                payload = {
                    "servers": [dict(s) for s in servers],
                    "events": [dict(e) for e in events]
                }
                await websocket.send_json(jsonable_encoder(payload))
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass