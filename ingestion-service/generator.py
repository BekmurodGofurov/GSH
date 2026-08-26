import asyncio
import random
import sys
from datetime import datetime, timezone
import asyncpg
from redis.asyncio import Redis

DB_URL = "postgresql://postgres:postgrespassword@localhost:5433/game_monitor"
REDIS_URL = "redis://localhost:6379"

SERVERS = [
    {"id": "185.25.180.1:27015", "name": "Vienna Valve Server", "region": "Vienna", "max_players": 24},
    {"id": "185.25.180.2:27015", "name": "Warsaw Valve Server", "region": "Warsaw", "max_players": 32},
]

async def init_servers(db_pool):
    async with db_pool.acquire() as conn:
        for s in SERVERS:
            await conn.execute("""
                INSERT INTO monitored_servers (server_id, server_name, region, status, last_online_at)
                VALUES ($1, $2, $3, 'ONLINE', NOW())
                ON CONFLICT (server_id) DO NOTHING;
            """, s["id"], s["name"], s["region"])

async def start_generator():
    db_pool = await asyncpg.create_pool(DB_URL)
    redis = Redis.from_url(REDIS_URL)

    await init_servers(db_pool)
    print("🚀 CS2 Demo Data Generator ishga tushdi (3 ta jadval to'ldirilmoqda)...")

    # Har bir serverning oldingi statusini saqlab turish uchun
    previous_states = {s["id"]: "ONLINE" for s in SERVERS}

    try:
        while True:
            now = datetime.now(timezone.utc)
            
            for s in SERVERS:
                server_id = s["id"]
                max_p = s["max_players"]

                # Tasodifiy simulyatsiya
                is_offline = random.random() < 0.08  # 8% ehtimollik bilan server crash/offline
                ping = round(random.uniform(15.0, 40.0) if not random.random() < 0.1 else random.uniform(150.0, 300.0), 2)
                players = 0 if is_offline else random.randint(10, max_p)
                current_status = "OFFLINE" if is_offline else "ONLINE"

                async with db_pool.acquire() as conn:
                    # 1. Metriklarni yozish (server_metrics)
                    await conn.execute("""
                        INSERT INTO server_metrics (time, server_id, player_count, max_players, ping_ms)
                        VALUES ($1, $2, $3, $4, $5);
                    """, now, server_id, players, max_p, ping)

                    # 2. Server statusini va vaqtlarini yangilash (monitored_servers)
                    if current_status == 'ONLINE':
                        await conn.execute("""
                            UPDATE monitored_servers 
                            SET status = 'ONLINE', last_online_at = $1 
                            WHERE server_id = $2;
                        """, now, server_id)
                    else:
                        await conn.execute("""
                            UPDATE monitored_servers 
                            SET status = 'OFFLINE', last_offline_at = $1 
                            WHERE server_id = $2;
                        """, now, server_id)

                    # 3. Hodisalarni yozish (server_events)
                    # A) Server crash bo'lsa yoki qayta yonsa
                    if previous_states[server_id] == "ONLINE" and current_status == "OFFLINE":
                        await conn.execute("""
                            INSERT INTO server_events (time, server_id, event_type, message)
                            VALUES ($1, $2, 'CRASH', 'Server javob bermadi va OFFLINE holatga o`tdi');
                        """, now, server_id)
                        print(f"⚠️ [EVENT CRASH] {server_id} o'chib qoldi!")

                    elif previous_states[server_id] == "OFFLINE" and current_status == "ONLINE":
                        await conn.execute("""
                            INSERT INTO server_events (time, server_id, event_type, message)
                            VALUES ($1, $2, 'RECOVERY', 'Server qayta ishga tushdi (ONLINE)');
                        """, now, server_id)
                        print(f"✅ [EVENT RECOVERY] {server_id} qayta yondi!")

                    # B) High Ping hodisasi
                    if current_status == "ONLINE" and ping > 200:
                        await conn.execute("""
                            INSERT INTO server_events (time, server_id, event_type, message)
                            VALUES ($1, $2, 'HIGH_PING', $3);
                        """, now, server_id, f"Yuqori lag aniqlandi: {ping}ms")

                previous_states[server_id] = current_status
                print(f"[{now.strftime('%H:%M:%S')}] {server_id} ({s['region']}) | Status: {current_status} | Players: {players}/{max_p} | Ping: {ping}ms")

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