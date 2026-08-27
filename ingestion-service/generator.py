import asyncio
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
import a2s
import asyncpg
from redis.asyncio import Redis

DB_URL = os.getenv("DB_URL")
REDIS_URL = os.getenv("REDIS_URL")

@dataclass
class CS2Server:
    ip: str
    port: int
    region: str
    name: str

# Real CS2 Serverlar Ro'yxati
SEED_SERVERS: list[CS2Server] = [
    # --- Warsaw / Poland Region ---
    CS2Server(ip="51.77.47.223", port=27015, region="Warsaw", name="uwujka.pl [CS2 DM]"),
    CS2Server(ip="51.77.47.216", port=27015, region="Warsaw", name="uwujka.pl [CS2 ARENA]"),
    CS2Server(ip="51.77.47.223", port=27020, region="Warsaw", name="uwujka.pl [CS2 DM #2]"),
    CS2Server(ip="91.211.118.96", port=27015, region="Warsaw", name="CYBERSHOKE.NET 5v5 #98"),
    CS2Server(ip="91.211.118.96", port=27018, region="Warsaw", name="CYBERSHOKE.NET 1v1 #12"),
    CS2Server(ip="91.211.118.96", port=27028, region="Warsaw", name="CYBERSHOKE.NET DM FFA #128"),
    CS2Server(ip="91.211.118.96", port=27022, region="Warsaw", name="CYBERSHOKE.NET Custom Match"),
    CS2Server(ip="91.211.118.96", port=27026, region="Warsaw", name="CYBERSHOKE.NET HSDM FFA #23"),
    CS2Server(ip="91.211.118.96", port=27032, region="Warsaw", name="CYBERSHOKE.NET Pistol DM #31"),
    CS2Server(ip="91.211.118.96", port=27029, region="Warsaw", name="CYBERSHOKE.NET DM FFA #129"),

    # --- Vienna / Central Europe Region ---
    CS2Server(ip="54.36.173.60", port=28015, region="Vienna", name="CYBERSHOKE.NET DM FFA #228"),
    CS2Server(ip="54.36.173.60", port=28016, region="Vienna", name="CYBERSHOKE.NET DM FFA #229"),
    CS2Server(ip="54.36.173.60", port=28017, region="Vienna", name="CYBERSHOKE.NET DM FFA #230"),
    CS2Server(ip="54.36.173.60", port=28018, region="Vienna", name="CYBERSHOKE.NET Duels 1v1 #233"),
    CS2Server(ip="54.36.173.60", port=28019, region="Vienna", name="CYBERSHOKE.NET Duels 1v1 #234"),
    CS2Server(ip="54.36.173.60", port=28020, region="Vienna", name="CYBERSHOKE.NET Duels 1v1 #235"),
    CS2Server(ip="54.36.173.60", port=28024, region="Vienna", name="CYBERSHOKE.NET Retake #379"),
    CS2Server(ip="54.36.173.60", port=28029, region="Vienna", name="CYBERSHOKE.NET 5v5 #263"),
    CS2Server(ip="54.36.173.60", port=28035, region="Vienna", name="CYBERSHOKE.NET Custom Match"),

    # --- Eastern Europe (Romania / Balkans) ---
    CS2Server(ip="188.212.101.109", port=27015, region="EU-East", name="FANGAMES.RO CS2"),
    CS2Server(ip="188.212.102.67", port=27015, region="EU-East", name="FAIRSIDE.RO CS2"),
    CS2Server(ip="62.122.215.45", port=27015, region="EU-East", name="yooma.su CS2 Mirage"),
    CS2Server(ip="82.29.125.132", port=27015, region="EU-East", name="Ludomanija Balkan CS2"),
]

async def init_servers(db_pool):
    async with db_pool.acquire() as conn:
        for s in SEED_SERVERS:
            server_id = f"{s.ip}:{s.port}"
            await conn.execute("""
                INSERT INTO monitored_servers (server_id, server_name, region, status, last_online_at)
                VALUES ($1::varchar, $2::varchar, $3::varchar, 'ONLINE', NOW())
                ON CONFLICT (server_id) DO UPDATE 
                SET server_name = EXCLUDED.server_name, region = EXCLUDED.region;
            """, server_id, s.name, s.region)

async def poll_and_save_server(server: CS2Server, db_pool, timeout: float = 1.5):
    server_id = f"{server.ip}:{server.port}"
    now = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    
    try:
        info = await a2s.ainfo((server.ip, server.port), timeout=timeout)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        
        server_name = info.server_name or server.name
        player_count = info.player_count
        max_players = info.max_players
        status = "ONLINE"
        
    except asyncio.TimeoutError:
        # Server vaqtida javob bermasa (Timeout)
        latency_ms = 0.0
        server_name = server.name
        player_count = 0
        max_players = 0
        status = "OFFLINE"
        
    except Exception as e:
        # Boshqa kutilmagan xatoliklar uchun
        print(f"⚠️ [{server_id}] {type(e).__name__}")
        latency_ms = 0.0
        server_name = server.name
        player_count = 0
        max_players = 0
        status = "OFFLINE"
        
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO server_metrics (time, server_id, player_count, max_players, ping_ms)
            VALUES ($1, $2, $3, $4, $5);
        """, now, server_id, player_count, max_players, latency_ms)

        await conn.execute("""
            UPDATE monitored_servers 
            SET status = $1::varchar, 
                server_name = $4::varchar,
                last_online_at = CASE WHEN $1::varchar = 'ONLINE' THEN $2::timestamptz ELSE last_online_at END,
                last_offline_at = CASE WHEN $1::varchar = 'OFFLINE' THEN $2::timestamptz ELSE last_offline_at END
            WHERE server_id = $3::varchar;
        """, status, now, server_id, server_name)

    return {"server_id": server_id, "status": status, "ping": latency_ms, "players": player_count}

async def start_generator():
    db_pool = await asyncpg.create_pool(DB_URL)
    redis = Redis.from_url(REDIS_URL)

    await init_servers(db_pool)
    print(f"🚀 {len(SEED_SERVERS)} ta real CS2 serverlariga asinxron UDP monitoring boshlandi...\n")

    try:
        while True:
            batch_start = time.perf_counter()
            
            # Barcha 23 ta serverga bir vaqtning o'zida parallel request yuborish
            tasks = [poll_and_save_server(srv, db_pool) for srv in SEED_SERVERS]
            results = await asyncio.gather(*tasks)
            
            total_time = round((time.perf_counter() - batch_start) * 1000, 2)
            online_count = sum(1 for r in results if r["status"] == "ONLINE")
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 Batch bajarildi: {total_time} ms | Online: {online_count}/{len(SEED_SERVERS)}")
            
            await asyncio.sleep(3)
    except asyncio.CancelledError:
        pass
    finally:
        await redis.aclose()
        await db_pool.close()

if __name__ == "__main__":
    try:
        asyncio.run(start_generator())
    except KeyboardInterrupt:
        sys.exit(0)