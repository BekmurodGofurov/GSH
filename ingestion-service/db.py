import os
import asyncpg

DB_URL = os.getenv("DB_URL", "postgresql://postgres:postgrespassword@localhost:5433/game_monitor")
db_pool: asyncpg.Pool | None = None

async def init_db() -> asyncpg.Pool:
    global db_pool
    db_pool = await asyncpg.create_pool(DB_URL)
    return db_pool

async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()

def get_db_pool() -> asyncpg.Pool:
    if db_pool is None:
        raise RuntimeError("Database pool ishga tushirilmagan!")
    return db_pool