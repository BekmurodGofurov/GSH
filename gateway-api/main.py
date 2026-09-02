import os
import sys
from pathlib import Path
import asyncio
import asyncpg
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder

# Support standalone and container imports for shared_schemas
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared_schemas.models import ServerMetric

# Schema for registering a new server
from pydantic import BaseModel, Field

class ServerCreate(BaseModel):
    server_id: str   # Format: "188.212.101.109:27015"
    server_name: str
    region: str      # "Vienna", "Warsaw", "EU-East"

class EventLabelRequest(BaseModel):
    root_cause: str = Field(
        ...,
        description="SERVER_CRASH, HIGH_LATENCY, DDOS_ATTACK, REGIONAL_OUTAGE, PLAYER_DROP, MAINTENANCE"
    )

from fastapi import Depends, Security
from fastapi.security.api_key import APIKeyHeader

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise ValueError("DB_URL environment variable is not set. Please provide it in the .env file.")

import secrets
from fastapi import Request, Response

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
active_sessions = set()

async def verify_api_key(request: Request, api_key: str = Security(api_key_header)):
    if ADMIN_API_KEY and api_key:
        if secrets.compare_digest(api_key, ADMIN_API_KEY):
            return api_key
            
    session_token = request.cookies.get("admin_session")
    if session_token and session_token in active_sessions:
        return session_token
        
    raise HTTPException(status_code=403, detail="Unauthorized")

db_pool = None

def get_db_pool():
    if db_pool is None:
        raise HTTPException(
            status_code=503,
            detail="Database connection is not ready yet. Please retry shortly.",
        )
    return db_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_pool = await asyncpg.create_pool(DB_URL)
    yield
    if db_pool:
        await db_pool.close()

app = FastAPI(
    title="CS2 Monitor Gateway API",
    version="1.0.0",
    lifespan=lifespan
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# --- SERVER MANAGEMENT (ADMIN / CLIENT) ---



class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/v1/admin/login")
async def admin_login(creds: LoginRequest, response: Response):
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Admin feature disabled")
        
    if secrets.compare_digest(creds.username, ADMIN_USERNAME) and secrets.compare_digest(creds.password, ADMIN_PASSWORD):
        session_token = secrets.token_urlsafe(32)
        active_sessions.add(session_token)
        response.set_cookie(key="admin_session", value=session_token, httponly=True, samesite="lax")
        return {"status": "success"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/v1/admin/me")
async def admin_me(api_key: str = Depends(verify_api_key)):
    return {"status": "authenticated"}

@app.post("/api/v1/admin/logout")
async def admin_logout(request: Request, response: Response):
    session_token = request.cookies.get("admin_session")
    if session_token in active_sessions:
        active_sessions.remove(session_token)
    response.delete_cookie("admin_session")
    return {"status": "success"}

@app.post("/api/v1/servers", status_code=201)
async def add_monitored_server(data: ServerCreate, api_key: str = Depends(verify_api_key)):
    """Add or update a monitored CS2 server (requires admin API key)."""
    async with get_db_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO monitored_servers (server_id, server_name, region, status)
            VALUES ($1, $2, $3, 'OFFLINE')
            ON CONFLICT (server_id) DO UPDATE
            SET server_name = EXCLUDED.server_name, region = EXCLUDED.region;
        """, data.server_id, data.server_name, data.region)
    return {"status": "success", "message": f"Server {data.server_id} added to monitoring"}

# --- READ ENDPOINTS ---

@app.get("/api/v1/servers")
async def get_servers():
    async with get_db_pool().acquire() as conn:
        rows = await conn.fetch(LATEST_SERVERS_QUERY)
        return [dict(r) for r in rows]

@app.get("/api/v1/servers/{server_id:path}/metrics")
async def get_server_metrics(server_id: str, limit: int = Query(30, ge=5, le=300)):
    async with get_db_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT time, player_count, max_players, ping_ms
            FROM server_metrics
            WHERE server_id = $1
            ORDER BY time DESC
            LIMIT $2;
        """, server_id, limit)
        return [dict(r) for r in rows]

@app.get("/api/v1/events")
async def get_events(limit: int = Query(50, ge=1, le=200)):
    async with get_db_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, time, server_id, event_type, root_cause, label_source, message,
                   anomaly_score, anomaly_reasons, diagnosis
            FROM server_events
            ORDER BY time DESC
            LIMIT $1;
        """, limit)
        return [dict(r) for r in rows]

@app.get("/api/v1/analytics/ping-buckets")
async def get_ping_analytics(minutes: int = Query(10, ge=1, le=60)):
    async with get_db_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                time_bucket('1 minute', time) AS bucket,
                server_id,
                ROUND(AVG(ping_ms) FILTER (WHERE ping_ms > 0)::numeric, 2) AS avg_ping,
                ROUND(AVG(player_count)::numeric, 1) AS avg_players
            FROM server_metrics
            WHERE time > NOW() - (INTERVAL '1 minute' * $1)
            GROUP BY bucket, server_id
            ORDER BY bucket DESC;
        """, minutes)
        return [dict(r) for r in rows]

@app.get("/api/v1/analytics/daily-restarts")
async def get_daily_restarts():
    """How many times each server went offline in the last 24 hours."""
    async with get_db_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                ms.server_id,
                ms.server_name,
                ms.region,
                COUNT(se.id) FILTER (WHERE se.event_type ILIKE 'OFFLINE') AS restart_count
            FROM monitored_servers ms
            LEFT JOIN server_events se
                ON se.server_id = ms.server_id
                AND se.time >= NOW() - INTERVAL '24 hours'
            GROUP BY ms.server_id, ms.server_name, ms.region
            ORDER BY restart_count DESC;
        """)
        return [dict(r) for r in rows]

@app.get("/api/v1/analytics/daily-busy")
async def get_daily_busy():
    """Average and peak player counts per server over the last 24 hours."""
    async with get_db_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                ms.server_id,
                ms.server_name,
                ms.region,
                COALESCE(ROUND(AVG(sm.player_count)::numeric, 1), 0) AS avg_players,
                COALESCE(MAX(sm.player_count), 0) AS peak_players,
                COALESCE(MAX(sm.max_players), 0) AS max_slots
            FROM monitored_servers ms
            LEFT JOIN server_metrics sm
                ON sm.server_id = ms.server_id
                AND sm.time >= NOW() - INTERVAL '24 hours'
            GROUP BY ms.server_id, ms.server_name, ms.region
            ORDER BY avg_players DESC;
        """)
        return [dict(r) for r in rows]

@app.get("/api/v1/analytics/daily-ping")
async def get_daily_ping():
    """Average and best ping per server over the last 24 hours (only servers with data)."""
    async with get_db_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                ms.server_id,
                ms.server_name,
                ms.region,
                ROUND(AVG(sm.ping_ms) FILTER (WHERE sm.ping_ms > 0)::numeric, 1) AS avg_ping,
                ROUND(MIN(sm.ping_ms) FILTER (WHERE sm.ping_ms > 0)::numeric, 1) AS best_ping,
                COUNT(sm.time) AS sample_count
            FROM monitored_servers ms
            JOIN server_metrics sm
                ON sm.server_id = ms.server_id
                AND sm.time >= NOW() - INTERVAL '24 hours'
            GROUP BY ms.server_id, ms.server_name, ms.region
            HAVING AVG(sm.ping_ms) FILTER (WHERE sm.ping_ms > 0) IS NOT NULL
            ORDER BY avg_ping ASC;
        """)
        return [dict(r) for r in rows]

from datetime import date
@app.get("/api/v1/insights/daily")
async def get_daily_insights(target_date: date = Query(..., description="Target date in YYYY-MM-DD format")):
    """Get the cached daily report data for the specified date."""
    async with get_db_pool().acquire() as conn:
        # Check daily_reports
        row = await conn.fetchrow("""
            SELECT json_data 
            FROM daily_reports 
            WHERE report_date = $1
        """, target_date)
        
        if row and row["json_data"]:
            import json
            return json.loads(row["json_data"])
        
        # If not found, check the oldest metric date
        oldest_row = await conn.fetchrow("SELECT MIN(time) as oldest FROM server_metrics")
        if oldest_row and oldest_row["oldest"]:
            oldest_date = oldest_row["oldest"].date()
            if target_date < oldest_date:
                raise HTTPException(status_code=404, detail=f"No data. Collection started on {oldest_date.isoformat()}")
            else:
                raise HTTPException(status_code=404, detail="No report found for the requested date.")
        else:
            raise HTTPException(status_code=404, detail="No metric data available in the system yet.")

PAGE_SIZE = 9  # Used by client for display slicing only

# --- REALTIME WEBSOCKET ---

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            async with get_db_pool().acquire() as conn:
                servers = await conn.fetch(LATEST_SERVERS_QUERY)
                events = await conn.fetch(
                    "SELECT * FROM server_events ORDER BY time DESC LIMIT 5;"
                )
                payload = {
                    "servers": [dict(s) for s in servers],
                    "events": [dict(e) for e in events],
                }
                await websocket.send_json(jsonable_encoder(payload))
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass

@app.post("/api/v1/events/{event_id}/label")
async def update_event_label(event_id: int, payload: EventLabelRequest, api_key: str = Depends(verify_api_key)):
    """Update or verify the root cause label of an incident (Active Learning)."""
    async with get_db_pool().acquire() as conn:
        result = await conn.execute("""
            UPDATE server_events
            SET root_cause = $1, label_source = 'manual'
            WHERE id = $2;
        """, payload.root_cause, event_id)
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Incident not found")
    return {"status": "success", "event_id": event_id, "root_cause": payload.root_cause, "label_source": "manual"}

@app.put("/api/v1/servers/{server_id:path}")
async def update_monitored_server(server_id: str, data: ServerCreate, api_key: str = Depends(verify_api_key)):
    """Update a monitored CS2 server."""
    async with get_db_pool().acquire() as conn:
        result = await conn.execute("""
            UPDATE monitored_servers
            SET server_id = $1, server_name = $2, region = $3
            WHERE server_id = $4;
        """, data.server_id, data.server_name, data.region, server_id)
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Server not found")
    return {"status": "success", "message": f"Server {server_id} updated successfully"}

@app.delete("/api/v1/servers/{server_id:path}")
async def delete_monitored_server(server_id: str, api_key: str = Depends(verify_api_key)):
    """Delete a monitored CS2 server."""
    async with get_db_pool().acquire() as conn:
        result = await conn.execute("""
            DELETE FROM monitored_servers
            WHERE server_id = $1;
        """, server_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Server not found")
    return {"status": "success", "message": f"Server {server_id} deleted successfully"}
