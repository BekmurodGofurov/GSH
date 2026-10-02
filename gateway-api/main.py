import os
import sys
import logging
from pathlib import Path
import asyncio
import asyncpg
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder

# Logging has to be configured before the agent router is imported, and
# the service has to configure it at all: uvicorn sets up its own loggers
# and leaves the root logger without a handler, so every logger.info()
# in this service was being dropped. That included the [AUDIT] line for
# P2 actions, which AGENTS.md requires -- muting a server left no trace
# anywhere outside the database row it wrote. Matches the pattern in
# voice-agent/worker.py so both halves of the agent log the same way.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Agent harness router — mounted at /api/v1/agent/ask
# Import is deferred here; the module validates AGENT_LLM_API_KEY at load time.
from app.agent import router as agent_module
from app.agent import tools as agent_tools
from app.agent.schemas import UnmuteAlertsRequest

# Support standalone and container imports for shared_schemas
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared_schemas.models import ServerMetric, ProbeRequest

# SQL constants shared with the agent tools (see queries.py for why they
# live outside this module).
from queries import LATEST_SERVERS_QUERY

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
import time
from fastapi import Request, Response

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

if not ADMIN_USERNAME or not ADMIN_PASSWORD:
    raise ValueError("ADMIN_USERNAME and ADMIN_PASSWORD environment variables are not set. Please provide them in the .env file.")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
active_sessions = {}

async def verify_api_key(request: Request, api_key: str = Security(api_key_header)):
    now = time.time()
    expired = [k for k, v in active_sessions.items() if now > v]
    for k in expired:
        del active_sessions[k]
        
    if ADMIN_API_KEY and api_key:
        if secrets.compare_digest(api_key, ADMIN_API_KEY):
            return api_key
            
    session_token = request.cookies.get("admin_session")
    if session_token and session_token in active_sessions:
        # Refresh session TTL on use
        active_sessions[session_token] = now + 86400
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

FRONTEND_URLS = os.environ.get("FRONTEND_URL")
if not FRONTEND_URLS:
    raise ValueError("FRONTEND_URL environment variable is not set. Please provide it in the .env file.")
origins = [url.strip().rstrip("/") for url in FRONTEND_URLS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_module.router)

@app.get("/")
async def root():
    return {"status": "ok", "service": "gateway-api", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "gateway-api"}

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
        active_sessions[session_token] = time.time() + 86400
        response.set_cookie(key="admin_session", value=session_token, httponly=True, samesite="lax", secure=True, max_age=86400)
        return {"status": "success"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/v1/admin/me")
async def admin_me(api_key: str = Depends(verify_api_key)):
    return {"status": "authenticated"}

@app.post("/api/v1/admin/logout")
async def admin_logout(request: Request, response: Response):
    session_token = request.cookies.get("admin_session")
    if session_token in active_sessions:
        del active_sessions[session_token]
    response.delete_cookie("admin_session")
    return {"status": "success"}

@app.post("/api/v1/servers", status_code=201)
async def add_monitored_server(data: ServerCreate, api_key: str = Depends(verify_api_key)):
    """Add or update a monitored CS2 server (requires admin authentication)."""
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


# ---------------------------------------------------------------------------
# Alert controls
# ---------------------------------------------------------------------------

class MuteRequest(BaseModel):
    minutes: int = Field(..., ge=1, le=10080, description="Duration in minutes (max 7 days)")
    reason: str | None = None

@app.post("/api/v1/events/{event_id}/acknowledge")
async def acknowledge_event(event_id: int, api_key: str = Depends(verify_api_key), request: Request = None):
    """Mark an incident as acknowledged so repeated alert sending stops."""
    acked_by = request.headers.get("X-Admin-Name", "admin") if request else "admin"
    async with get_db_pool().acquire() as conn:
        result = await conn.execute(
            """
            UPDATE server_events
            SET is_acknowledged = TRUE,
                acknowledged_by = $1,
                acknowledged_at = NOW()
            WHERE id = $2;
            """,
            acked_by,
            event_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Event not found")
    return {"status": "acknowledged", "event_id": event_id}

@app.post("/api/v1/servers/{server_id:path}/mute")
async def mute_server_alerts(server_id: str, body: MuteRequest, api_key: str = Depends(verify_api_key)):
    """Temporarily silence alerts for a server."""
    from datetime import timedelta
    async with get_db_pool().acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM monitored_servers WHERE server_id = $1;", server_id
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Server not found")
        muted_until = __import__("datetime").datetime.now(__import__("datetime").timezone.utc) + timedelta(minutes=body.minutes)
        row = await conn.fetchrow(
            """
            INSERT INTO alert_silences (server_id, muted_until, muted_by, reason)
            VALUES ($1, $2, 'admin', $3)
            RETURNING id, muted_until;
            """,
            server_id,
            muted_until,
            body.reason,
        )
    return {"status": "muted", "server_id": server_id, "muted_until": row["muted_until"].isoformat(), "silence_id": row["id"]}

@app.post("/api/v1/alerts/unmute")
async def unmute_many_alerts(body: UnmuteAlertsRequest, api_key: str = Depends(verify_api_key)):
    """Cancel active mutes for several servers, or all of them, in one call."""
    return await agent_tools.unmute_server_alerts(
        get_db_pool(), server_id=body.server_id, server_ids=body.server_ids,
        all_servers=body.all_servers,
    )

@app.post("/api/v1/servers/{server_id:path}/unmute")
async def unmute_server_alerts(server_id: str, api_key: str = Depends(verify_api_key)):
    """Cancel any active mute for a server."""
    async with get_db_pool().acquire() as conn:
        result = await conn.execute(
            "UPDATE alert_silences SET muted_until = NOW() WHERE server_id = $1 AND muted_until > NOW();",
            server_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="No active mute found for this server")
    return {"status": "unmuted", "server_id": server_id}

# ---------------------------------------------------------------------------
# On-demand poll (proxied to ingestion-service)
# ---------------------------------------------------------------------------

import httpx

_INGESTION_URL = os.getenv("INGESTION_INTERNAL_URL", "http://ingestion-service:8001")

@app.post("/api/v1/servers/{server_id:path}/poll")
async def poll_server_now(server_id: str, api_key: str = Depends(verify_api_key)):
    """Immediately trigger a fresh health check for a server via ingestion-service."""
    url = f"{_INGESTION_URL}/api/v1/servers/{server_id}/poll"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Ingestion service unreachable: {exc}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Server not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Unexpected response from ingestion-service")
    return resp.json()

# ---------------------------------------------------------------------------
# One-off probe of any address (admin console, proxied to ingestion-service)
# ---------------------------------------------------------------------------

@app.post("/api/v1/probe")
async def probe_address(body: ProbeRequest, api_key: str = Depends(verify_api_key)):
    """Ask one address for ping, players and capacity. Nothing is stored."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{_INGESTION_URL}/api/v1/probe", json=body.model_dump())
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Ingestion service unreachable: {exc}")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Unexpected response from ingestion-service")
    return resp.json()

# ---------------------------------------------------------------------------
# On-demand daily report
# ---------------------------------------------------------------------------

import json as _json

@app.post("/api/v1/reports/daily")
async def generate_daily_report(api_key: str = Depends(verify_api_key)):
    """Return today's cached daily report JSON, or 404 if not yet generated."""
    import datetime as _dt
    today = _dt.date.today()
    async with get_db_pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT report_text, html_content, json_data FROM daily_reports WHERE report_date = $1;",
            today,
        )
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Today's report has not been generated yet. It is created automatically at the scheduled time, or use /report in Telegram to trigger it now.",
        )
    return {
        "report_date": today.isoformat(),
        "report_text": row["report_text"],
        "json_data": _json.loads(row["json_data"]) if row["json_data"] else None,
    }

# ---------------------------------------------------------------------------
# LiveKit token
# ---------------------------------------------------------------------------

_LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
_LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
_LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")

# Which worker is allowed to answer this stack's voice rooms.
#
# Without a name, every worker registered against the LiveKit project takes
# rooms from a shared pool -- so a dev stack, or a laptop left running
# `docker compose up`, could pick up a production call and answer it in a
# different voice with a different build of the prompt. The room asks for
# this exact agent by name, and the worker registers under it, so only the
# matching worker is dispatched. Dev and prod must not share the value.
_VOICE_AGENT_NAME = os.getenv("VOICE_AGENT_NAME", "gsh-voice")

@app.get("/api/v1/agent/livekit/token")
async def get_livekit_token(request: Request):
    """Return a short-lived LiveKit room access token for dashboard voice sessions."""
    if not _LIVEKIT_API_KEY or not _LIVEKIT_API_SECRET or not _LIVEKIT_URL:
        raise HTTPException(status_code=503, detail="LiveKit is not configured on this server.")
    try:
        from livekit.api import AccessToken, VideoGrants, RoomAgentDispatch, RoomConfiguration
        from datetime import timedelta
        import time as _time

        session_token = request.cookies.get("admin_session")
        is_admin = bool(session_token and session_token in active_sessions)
        role_label = "Admin" if is_admin else "User"

        import uuid as _uuid
        room_name = f"gsh-agent-{_uuid.uuid4().hex[:8]}"
        grants = VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True)
        token = (
            AccessToken(_LIVEKIT_API_KEY, _LIVEKIT_API_SECRET)
            .with_identity(f"{role_label.lower()}-{int(_time.time())}")
            .with_name(f"GSH {role_label}")
            # Who is in the room, decided here and signed into the token.
            #
            # The voice worker holds a service-wide admin key, so without
            # this it would run a P2 action for whoever happened to be
            # speaking. The browser cannot forge this: it is inside the
            # JWT the server signs, and the worker reads it off the
            # participant rather than trusting anything said out loud.
            .with_attributes({"gsh_role": "admin" if is_admin else "viewer"})
            .with_grants(grants)
            .with_room_config(
                RoomConfiguration(
                    agents=[RoomAgentDispatch(agent_name=_VOICE_AGENT_NAME)],
                )
            )
            .with_ttl(timedelta(minutes=10))
            .to_jwt()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Token generation failed: {exc}")
    return {"token": token, "url": _LIVEKIT_URL, "room": room_name, "agent": _VOICE_AGENT_NAME}




if __name__ == "__main__":
    import uvicorn
    port_env = os.getenv("PORT") or os.getenv("GATEWAY_CONTAINER_PORT") or os.getenv("GATEWAY_PORT")
    if not port_env:
        raise ValueError("PORT (or GATEWAY_PORT / GATEWAY_CONTAINER_PORT) environment variable is not set. Please provide it in the .env file.")
    uvicorn.run("main:app", host="0.0.0.0", port=int(port_env))
