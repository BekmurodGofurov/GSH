import os
import sys
import time
import asyncio
from pathlib import Path
from datetime import datetime, timezone
import a2s
from redis.asyncio import Redis

# Support standalone and container imports for shared_schemas
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import init_db, close_db, get_db_pool

REDIS_URL = os.getenv("REDIS_URL") or "redis://localhost:6379"
redis_client: Redis | None = None

async def init_redis():
    global redis_client
    try:
        redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        print(" Connected to Redis Streams for metric publishing.")
    except Exception as e:
        print(f" Redis connection unavailable (metrics stored in DB only): {e}")
        redis_client = None

async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None

async def get_active_servers():
    pool = get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT server_id, server_name, region FROM monitored_servers;")

async def poll_single_server(server_row, timeout: float = 1.5):
    pool = get_db_pool()
    server_id = server_row["server_id"]
    fallback_name = server_row["server_name"]
    region = server_row["region"]
    
    try:
        ip, port_str = server_id.split(":")
        port = int(port_str)
    except ValueError:
        return {"server_id": server_id, "status": "OFFLINE", "ping": 0.0, "players": 0}

    now = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    
    try:
        info = await a2s.ainfo((ip, port), timeout=timeout)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        server_name = info.server_name or fallback_name
        player_count = info.player_count
        max_players = info.max_players
        map_name = getattr(info, "map_name", None) or "de_mirage"
        
        # Calculate tick rate from keywords or default CS2 value
        tick_rate = 128.0
        keywords = getattr(info, "keywords", "") or ""
        if "64" in keywords:
            tick_rate = 64.0
        elif "128" in keywords:
            tick_rate = 128.0
            
        status = "ONLINE"
    except Exception:
        latency_ms = 0.0
        server_name = fallback_name
        player_count = 0
        max_players = 0
        map_name = "unknown"
        tick_rate = 0.0
        status = "NO_RESPONSE"
        
    # 1. Write metric to TimescaleDB hypertable
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO server_metrics (time, server_id, player_count, max_players, ping_ms)
            VALUES ($1, $2, $3, $4, $5);
        """, now, server_id, player_count, max_players, latency_ms)

        # 2. Update monitored_servers status and last online/offline timestamp
        await conn.execute("""
            UPDATE monitored_servers 
            SET status = $1::varchar, 
                server_name = $4::varchar,
                last_online_at = CASE WHEN $1::varchar = 'ONLINE' THEN $2::timestamptz ELSE last_online_at END,
                last_offline_at = CASE WHEN $1::varchar != 'ONLINE' AND last_online_at IS NOT NULL THEN $2::timestamptz ELSE last_offline_at END
            WHERE server_id = $3::varchar;
        """, status, now, server_id, server_name)

    # 3. Publish to Redis Streams for downstream ML services
    if redis_client:
        try:
            await redis_client.xadd(
                "server_metrics_stream",
                {
                    "server_id": server_id,
                    "game": "cs2",
                    "region": region,
                    "player_count": str(player_count),
                    "max_players": str(max_players),
                    "ping_ms": str(latency_ms),
                    "tick_rate": str(tick_rate),
                    "map": map_name,
                    "status": status,
                    "timestamp": now.isoformat(),
                },
                maxlen=10000,
            )
        except Exception:
            pass

    return {"server_id": server_id, "status": status, "ping": latency_ms, "players": player_count, "tick_rate": tick_rate}

async def start_polling_loop():
    print(" Dynamic UDP A2S Monitoring background task started...")
    while True:
        try:
            pool = get_db_pool()
            if pool:
                servers = await get_active_servers()
                if servers:
                    batch_start = time.perf_counter()
                    tasks = [poll_single_server(srv) for srv in servers]
                    results = await asyncio.gather(*tasks)
                    total_time = round((time.perf_counter() - batch_start) * 1000, 2)
                    online_count = sum(1 for r in results if r["status"] == "ONLINE")
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Batch completed: {total_time} ms | Online: {online_count}/{len(servers)}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f" Error in polling loop: {e}")
            
        await asyncio.sleep(3)

async def run_standalone_poller():
    """Entrypoint for running the poller standalone in CLI"""
    print(" Starting standalone CS2 poller...")
    await init_db()
    await init_redis()
    try:
        await start_polling_loop()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n Poller stopped.")
    finally:
        await close_redis()
        await close_db()

if __name__ == "__main__":
    try:
        asyncio.run(run_standalone_poller())
    except KeyboardInterrupt:
        sys.exit(0)