import os
import sys
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Support standalone and container imports for shared_schemas
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import init_db, close_db, get_db_pool
from shared_schemas.models import MetricPayload, EventPayload, ProbeRequest
from poller import start_polling_loop, init_redis, close_redis, poll_single_server, probe_address

poller_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global poller_task
    await init_db()
    await init_redis()
    poller_task = asyncio.create_task(start_polling_loop())
    yield
    if poller_task:
        poller_task.cancel()
    await close_redis()
    await close_db()

app = FastAPI(
    title="CS2 Ingestion Service",
    version="2.0.0",
    lifespan=lifespan
)

FRONTEND_URL = os.getenv("FRONTEND_URL")
if not FRONTEND_URL:
    raise ValueError("FRONTEND_URL environment variable is not set. Please provide it in the .env file.")
FRONTEND_URL = FRONTEND_URL.rstrip("/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ingestion-service"}

# Internal endpoints for services or webhooks to push metrics and events
@app.post("/api/v1/ingest/metric")
async def ingest_metric(data: MetricPayload):
    pool = get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO server_metrics (time, server_id, player_count, max_players, ping_ms)
            VALUES (NOW(), $1, $2, $3, $4);
        """, data.server_id, data.player_count, data.max_players, data.ping_ms)
    return {"status": "metric_inserted"}

@app.post("/api/v1/ingest/event")
async def ingest_event(data: EventPayload):
    pool = get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO server_events (time, server_id, event_type, root_cause, message)
            VALUES (NOW(), $1, $2, $3, $4);
        """, data.server_id, data.event_type, data.root_cause, data.message)
    return {"status": "event_inserted"}

@app.post("/api/v1/servers/{server_id}/poll")
async def poll_server_now(server_id: str):
    """Immediately poll a single server and persist the fresh metric."""
    pool = get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT server_id, server_name, region FROM monitored_servers WHERE server_id = $1;",
            server_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")
    result = await poll_single_server(dict(row))
    return result

@app.post("/api/v1/probe")
async def probe(data: ProbeRequest):
    """Query an arbitrary address once. Nothing is stored."""
    return await probe_address(data.address)


if __name__ == "__main__":
    import uvicorn
    port_env = os.getenv("PORT") or os.getenv("INGESTION_CONTAINER_PORT") or os.getenv("INGESTION_PORT")
    if not port_env:
        raise ValueError("PORT (or INGESTION_PORT / INGESTION_CONTAINER_PORT) environment variable is not set. Please provide it in the .env file.")
    uvicorn.run("main:app", host="0.0.0.0", port=int(port_env))