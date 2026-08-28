import asyncio
import time
from datetime import datetime, timezone
import a2s
from db import get_db_pool

async def get_active_servers():
    pool = get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT server_id, server_name, region FROM monitored_servers;")

async def poll_single_server(server_row, timeout: float = 1.5):
    pool = get_db_pool()
    server_id = server_row["server_id"]
    fallback_name = server_row["server_name"]
    
    try:
        ip, port_str = server_id.split(":")
        port = int(port_str)
    except ValueError:
        return

    now = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    
    try:
        info = await a2s.ainfo((ip, port), timeout=timeout)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        server_name = info.server_name or fallback_name
        player_count = info.player_count
        max_players = info.max_players
        status = "ONLINE"
    except Exception:
        latency_ms = 0.0
        server_name = fallback_name
        player_count = 0
        max_players = 0
        status = "OFFLINE"
        
    async with pool.acquire() as conn:
        # 1. Metrikani TimescaleDB giperjadvaliga yozish
        await conn.execute("""
            INSERT INTO server_metrics (time, server_id, player_count, max_players, ping_ms)
            VALUES ($1, $2, $3, $4, $5);
        """, now, server_id, player_count, max_players, latency_ms)

        # 2. Server holatini va vaqtlarini yangilash
        await conn.execute("""
            UPDATE monitored_servers 
            SET status = $1::varchar, 
                server_name = $4::varchar,
                last_online_at = CASE WHEN $1::varchar = 'ONLINE' THEN $2::timestamptz ELSE last_online_at END,
                last_offline_at = CASE WHEN $1::varchar = 'OFFLINE' THEN $2::timestamptz ELSE last_offline_at END
            WHERE server_id = $3::varchar;
        """, status, now, server_id, server_name)

async def start_polling_loop():
    print("🚀 Dinamik UDP A2S Monitoring background taski ishga tushdi...")
    while True:
        try:
            pool = get_db_pool()
            if pool:
                servers = await get_active_servers()
                if servers:
                    tasks = [poll_single_server(srv) for srv in servers]
                    await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"⚠️ Monitoring siklida xatolik: {e}")
            
        await asyncio.sleep(3)