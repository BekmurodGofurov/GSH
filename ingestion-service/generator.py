import asyncio
import random
import sys
import os
from datetime import datetime, timezone
import asyncpg
from redis.asyncio import Redis

DB_URL = os.getenv("DB_URL", "postgresql://postgres:postgrespassword@localhost:5433/game_monitor")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

SERVERS = [
    # Vienna Datacenter
    {"id": "185.25.180.1:27015", "name": "Vienna Valve Server #1", "region": "Vienna", "max_players": 24},
    {"id": "185.25.180.2:27015", "name": "Vienna Valve Server #2", "region": "Vienna", "max_players": 24},
    {"id": "185.25.180.3:27015", "name": "Vienna Valve Server #3", "region": "Vienna", "max_players": 32},
    {"id": "185.25.180.4:27015", "name": "Vienna Community Server #1", "region": "Vienna", "max_players": 32},
    {"id": "185.25.180.5:27015", "name": "Vienna Retake Server #1", "region": "Vienna", "max_players": 16},
    # Warsaw Datacenter
    {"id": "155.133.230.1:27015", "name": "Warsaw Valve Server #1", "region": "Warsaw", "max_players": 24},
    {"id": "155.133.230.2:27015", "name": "Warsaw Valve Server #2", "region": "Warsaw", "max_players": 24},
    {"id": "155.133.230.3:27015", "name": "Warsaw Valve Server #3", "region": "Warsaw", "max_players": 32},
    {"id": "155.133.230.4:27015", "name": "Warsaw Community Server #1", "region": "Warsaw", "max_players": 32},
    {"id": "155.133.230.5:27015", "name": "Warsaw Deathmatch Server", "region": "Warsaw", "max_players": 20},
]

async def init_servers(db_pool):
    async with db_pool.acquire() as conn:
        for s in SERVERS:
            await conn.execute("""
                INSERT INTO monitored_servers (server_id, server_name, region, status, last_online_at)
                VALUES ($1::varchar, $2::varchar, $3::varchar, 'ONLINE', NOW())
                ON CONFLICT (server_id) DO NOTHING;
            """, s["id"], s["name"], s["region"])

async def start_generator():
    db_pool = await asyncpg.create_pool(DB_URL)
    redis = Redis.from_url(REDIS_URL)

    await init_servers(db_pool)
    print("🚀 CS2 Raw Metrics Generator ishga tushdi (Faqat xom metrikalar yozilmoqda)...")

    try:
        while True:
            now = datetime.now(timezone.utc)
            scenario_roll = random.random()

            for s in SERVERS:
                server_id = s["id"]
                region = s["region"]
                max_p = s["max_players"]

                # Normal holat ko'rsatkichlari
                ping = round(random.uniform(15.0, 35.0), 2)
                players = random.randint(8, max_p)
                status = "ONLINE"

                # Xom anomaliyalar simulyatsiyasi (Metrika darajasida)
                if scenario_roll < 0.04 and region == "Vienna":
                    ping = round(random.uniform(220.0, 380.0), 2)
                    players = random.randint(5, max_p)

                elif 0.04 <= scenario_roll < 0.07 and server_id == "155.133.230.1:27015":
                    ping = round(random.uniform(400.0, 750.0), 2)
                    players = max(0, players - random.randint(3, 8))

                elif 0.07 <= scenario_roll < 0.10 and server_id in ["185.25.180.2:27015", "155.133.230.3:27015"]:
                    ping = 0.0
                    players = 0
                    status = "OFFLINE"

                async with db_pool.acquire() as conn:
                    # 1. Faqat xom vaqtli metrikalarni yozish
                    await conn.execute("""
                        INSERT INTO server_metrics (time, server_id, player_count, max_players, ping_ms)
                        VALUES ($1, $2, $3, $4, $5);
                    """, now, server_id, players, max_p, ping)

                    # 2. Serverning joriy holatini yangilash
                    await conn.execute("""
                        UPDATE monitored_servers 
                        SET status = $1::varchar, 
                            last_online_at = CASE WHEN $1::varchar = 'ONLINE' THEN $2::timestamptz ELSE last_online_at END,
                            last_offline_at = CASE WHEN $1::varchar = 'OFFLINE' THEN $2::timestamptz ELSE last_offline_at END
                        WHERE server_id = $3::varchar;
                    """, status, now, server_id)

                print(f"[{now.strftime('%H:%M:%S')}] {server_id} ({region}) | Status: {status} | Players: {players}/{max_p} | Ping: {ping}ms")

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