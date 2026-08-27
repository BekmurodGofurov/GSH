from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncpg
import os

app = FastAPI(
    title="CS2 Ingestion Service",
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

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DB_URL)

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

class MetricPayload(BaseModel):
    server_id: str
    player_count: int
    max_players: int
    ping_ms: float

class EventPayload(BaseModel):
    server_id: str
    event_type: str
    root_cause: Optional[str] = "NORMAL"
    message: str

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ingestion-service"}

@app.post("/api/v1/ingest/metric")
async def ingest_metric(data: MetricPayload):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO server_metrics (time, server_id, player_count, max_players, ping_ms)
            VALUES (NOW(), $1, $2, $3, $4);
        """, data.server_id, data.player_count, data.max_players, data.ping_ms)
    return {"status": "metric_inserted"}

@app.post("/api/v1/ingest/event")
async def ingest_event(data: EventPayload):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO server_events (time, server_id, event_type, root_cause, message)
            VALUES (NOW(), $1, $2, $3, $4);
        """, data.server_id, data.event_type, data.root_cause, data.message)
    return {"status": "event_inserted"}