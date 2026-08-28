import os
import sys
from pathlib import Path
import asyncpg

# Support standalone and container imports for shared_schemas
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_URL = os.getenv("DB_URL",)
db_pool: asyncpg.Pool | None = None

DEFAULT_SERVERS = [
    # --- Vienna / Central Europe Region ---
    {"server_id": "54.36.173.60:28029", "server_name": "CS2 5X5 | 5v5 #263 [PL] — CYBERSHOKE.NET", "region": "Vienna"},
    {"server_id": "54.36.173.60:28035", "server_name": "CS2 CUSTOM MATCHES [PL] — CYBERSHOKE.NET", "region": "Vienna"},
    {"server_id": "54.36.173.60:28015", "server_name": "CS2 DM | FFA #228 [PL] — CYBERSHOKE.NET (20 SLOTS)", "region": "Vienna"},
    {"server_id": "54.36.173.60:28016", "server_name": "CS2 DM | FFA #229 [PL] — CYBERSHOKE.NET (20 SLOTS)", "region": "Vienna"},
    {"server_id": "54.36.173.60:28017", "server_name": "CS2 DM | FFA #230 [PL] — CYBERSHOKE.NET (20 SLOTS)", "region": "Vienna"},
    {"server_id": "54.36.173.60:28018", "server_name": "CS2 DUELS | 1v1 #233 [PL] — CYBERSHOKE.NET (ARENA MAPS)", "region": "Vienna"},
    {"server_id": "54.36.173.60:28019", "server_name": "CS2 DUELS | 1v1 #234 [PL] — CYBERSHOKE.NET (ARENA MAPS)", "region": "Vienna"},
    {"server_id": "54.36.173.60:28020", "server_name": "CS2 DUELS | 1v1 #235 [PL] — CYBERSHOKE.NET (ARENA MAPS)", "region": "Vienna"},
    {"server_id": "54.36.173.60:28024", "server_name": "CS2 RETAKE #379 [PL] — CYBERSHOKE.NET (9 SLOTS)", "region": "Vienna"},
    {"server_id": "185.25.180.1:27015", "server_name": "Vienna Valve Server #1", "region": "Vienna"},
    {"server_id": "185.25.180.2:27015", "server_name": "Vienna Valve Server #2", "region": "Vienna"},
    {"server_id": "185.25.180.3:27015", "server_name": "Vienna Valve Server #3", "region": "Vienna"},
    {"server_id": "185.25.180.4:27015", "server_name": "Vienna Community Server #1", "region": "Vienna"},
    {"server_id": "185.25.180.5:27015", "server_name": "Vienna Retake Server #1", "region": "Vienna"},

    # --- Warsaw / Poland Region ---
    {"server_id": "91.211.118.96:27018", "server_name": "CS2 ARENA | 1v1 #12 [UA] — CYBERSHOKE.NET", "region": "Warsaw"},
    {"server_id": "91.211.118.96:27028", "server_name": "CS2 DM | FFA #128 [UA] — CYBERSHOKE.NET (20 SLOTS)", "region": "Warsaw"},
    {"server_id": "155.133.230.1:27015", "server_name": "Warsaw Valve Server #1", "region": "Warsaw"},
    {"server_id": "155.133.230.2:27015", "server_name": "Warsaw Valve Server #2", "region": "Warsaw"},
    {"server_id": "155.133.230.3:27015", "server_name": "Warsaw Valve Server #3", "region": "Warsaw"},
    {"server_id": "155.133.230.4:27015", "server_name": "Warsaw Community Server #1", "region": "Warsaw"},
    {"server_id": "155.133.230.5:27015", "server_name": "Warsaw Deathmatch Server", "region": "Warsaw"},
    {"server_id": "51.77.47.216:27015", "server_name": "uwujka.pl [CS2 ARENA]", "region": "Warsaw"},
    {"server_id": "51.77.47.223:27015", "server_name": "uwujka.pl [CS2 DM] #1", "region": "Warsaw"},
    {"server_id": "51.77.47.223:27020", "server_name": "uwujka.pl [CS2 DM] #2", "region": "Warsaw"},

    # --- EU-East Region ---
    {"server_id": "188.212.101.109:27015", "server_name": "CS2.FANGAMES.RO | BHOP SHOP AGENTS MUSIC SKINS", "region": "EU-East"},
    {"server_id": "82.29.125.132:27015", "server_name": "Ludomanija Public [BALKAN] !skins !kinife !agent", "region": "EU-East"},
    {"server_id": "62.122.215.45:27015", "server_name": "yooma.su (CS2) / FREE MIRAGE", "region": "EU-East"},
    {"server_id": "188.212.102.67:27015", "server_name": "ROMANIA.FAIRSIDE.RO", "region": "EU-East"},
]

async def seed_servers_if_needed(pool: asyncpg.Pool):
    """Seed initial servers into monitored_servers table if not already present"""
    async with pool.acquire() as conn:
        for s in DEFAULT_SERVERS:
            await conn.execute("""
                INSERT INTO monitored_servers (server_id, server_name, region, status)
                VALUES ($1, $2, $3, 'ONLINE')
                ON CONFLICT (server_id) DO NOTHING;
            """, s["server_id"], s["server_name"], s["region"])
    print(f"✅ {len(DEFAULT_SERVERS)} CS2 servers verified/seeded in monitored_servers table.")

async def init_db() -> asyncpg.Pool:
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DB_URL)
        await seed_servers_if_needed(db_pool)
    return db_pool

async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None

def get_db_pool() -> asyncpg.Pool:
    if db_pool is None:
        raise RuntimeError("Database pool has not been initialized!")
    return db_pool