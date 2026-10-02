import os
import sys
import time
import socket
import ipaddress
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
import a2s
from redis.asyncio import Redis

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Support standalone and container imports for shared_schemas
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import init_db, close_db, get_db_pool

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise ValueError("REDIS_URL environment variable is not set. Please provide it in the .env file.")
redis_client: Redis | None = None

async def init_redis():
    global redis_client
    try:
        redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info(" Connected to Redis Streams for metric publishing.")
    except Exception as e:
        logger.warning(f" Redis connection unavailable (metrics stored in DB only): {e}")
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
    info = None
    latency_ms = 0.0

    # Try query with 1 quick retry to absorb UDP network jitter.
    # Timer is started inside the try block so that retry delays and
    # asyncio.sleep() are NOT included in the measured latency.
    for attempt in range(2):
        try:
            _t0 = time.perf_counter()
            info = await a2s.ainfo((ip, port), timeout=timeout)
            latency_ms = round((time.perf_counter() - _t0) * 1000, 2)
            break
        except Exception:
            if attempt == 0:
                await asyncio.sleep(0.08)

    if info is not None:
        server_name = info.server_name or fallback_name
        player_count = info.player_count
        max_players = info.max_players
        map_name = getattr(info, "map_name", None)
        
        # Calculate tick rate from keywords or default CS2 value
        tick_rate = 128.0
        keywords = getattr(info, "keywords", "") or ""
        keyword_list = keywords.split(",")
        if "64" in keyword_list:
            tick_rate = 64.0
        elif "128" in keyword_list:
            tick_rate = 128.0
            
        status = "ONLINE"
    else:
        latency_ms = 0.0
        server_name = fallback_name
        player_count = 0
        max_players = 0
        map_name = "unknown"
        tick_rate = 0.0
        status = "OFFLINE"
        
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
                last_online_at  = CASE WHEN $1::varchar = 'ONLINE'  THEN $2::timestamptz ELSE last_online_at  END,
                last_offline_at = CASE WHEN $1::varchar = 'OFFLINE' THEN $2::timestamptz ELSE last_offline_at END
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
                    "map": map_name if map_name is not None else "",
                    "status": status,
                    "timestamp": now.isoformat(),
                },
                maxlen=10000,
            )
        except Exception:
            pass

    return {"server_id": server_id, "status": status, "ping": latency_ms, "players": player_count, "tick_rate": tick_rate}

async def probe_address(address: str, timeout: float = 3.0):
    """Query one address once and report what it says. Writes nothing.

    Used by the admin console to look at a server before (or without)
    adding it to monitoring, so it stays out of the database, Redis and
    the polling loop.
    """
    ip, port_str = address.rsplit(":", 1)
    # A hostname can resolve to an internal address; check where it really
    # points before sending anything.
    try:
        resolved = await asyncio.get_running_loop().getaddrinfo(ip, int(port_str), type=socket.SOCK_DGRAM)
    except Exception:
        return {"address": address, "reachable": False}
    for *_, sockaddr in resolved:
        target = ipaddress.ip_address(sockaddr[0])
        if target.is_loopback or target.is_unspecified or target.is_link_local or target.is_multicast:
            return {"address": address, "reachable": False}
    try:
        _t0 = time.perf_counter()
        info = await a2s.ainfo((ip, int(port_str)), timeout=timeout)
        latency_ms = round((time.perf_counter() - _t0) * 1000, 2)
    except Exception:
        return {"address": address, "reachable": False}
    return {
        "address": address,
        "reachable": True,
        "server_name": info.server_name,
        "map": getattr(info, "map_name", None),
        "ping_ms": latency_ms,
        "player_count": info.player_count,
        "max_players": info.max_players,
    }


async def start_polling_loop():
    logger.info(" Dynamic UDP A2S Monitoring background task started...")
    while True:
        try:
            pool = get_db_pool()
            if pool:
                servers = await get_active_servers()
                if servers:
                    batch_start = time.perf_counter()
                    tasks = []
                    for srv in servers:
                        tasks.append(asyncio.create_task(poll_single_server(srv)))
                        await asyncio.sleep(0.015) # 15ms stagger to prevent UDP flood drops
                        
                    results = await asyncio.gather(*tasks)
                    total_time = round((time.perf_counter() - batch_start) * 1000, 2)
                    online_count = sum(1 for r in results if r["status"] == "ONLINE")
                    logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Batch completed: {total_time} ms | Online: {online_count}/{len(servers)}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f" Error in polling loop: {e}")
            
        await asyncio.sleep(3)

async def run_standalone_poller():
    """Entrypoint for running the poller standalone in CLI"""
    logger.info(" Starting standalone CS2 poller...")
    await init_db()
    await init_redis()
    try:
        await start_polling_loop()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("\n Poller stopped.")
    finally:
        await close_redis()
        await close_db()

if __name__ == "__main__":
    try:
        asyncio.run(run_standalone_poller())
    except KeyboardInterrupt:
        sys.exit(0)