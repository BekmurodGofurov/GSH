import asyncio
import os
from datetime import datetime, timezone

import asyncpg
import httpx

DB_URL = os.getenv("DB_URL")
ANOMALY_API_URL = os.getenv("ANOMALY_API_URL", "http://localhost:8002/predict/anomaly")
POLL_INTERVAL_SECONDS = float(os.getenv("BRIDGE_POLL_INTERVAL", "5"))


async def fetch_new_metrics(pool: asyncpg.Pool, last_seen: datetime):
    query = """
        SELECT
            sm.time,
            sm.server_id,
            sm.player_count,
            sm.max_players,
            sm.ping_ms,
            ms.region
        FROM server_metrics sm
        JOIN monitored_servers ms ON ms.server_id = sm.server_id
        WHERE sm.time > $1
        ORDER BY sm.time ASC;
    """
    async with pool.acquire() as conn:
        return await conn.fetch(query, last_seen)


def build_payload(row: asyncpg.Record) -> dict:
    return {
        "metric": {
            "id": row["server_id"],
            "game": "cs2",
            "region": row["region"] or "unknown",
            "player_count": row["player_count"],
            "max_players": row["max_players"],
            "ping_ms": float(row["ping_ms"]),
            "timestamp": row["time"].isoformat(),
        }
    }


async def send_to_anomaly_api(client: httpx.AsyncClient, payload: dict):
    try:
        response = await client.post(ANOMALY_API_URL, json=payload, timeout=5.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        print(f"⚠️  Anomaly API so'rovi muvaffaqiyatsiz: {exc}")
        return None


def classify_event_type(reasons: list[str]) -> str:
    reasons_text = " ".join(reasons).lower()

    if "dropped to zero" in reasons_text:
        return "OFFLINE"
    if "ping_ms" in reasons_text:
        return "HIGH_PING"
    return "CRASH"


async def record_event(pool: asyncpg.Pool, event_time, server_id: str, event_type: str, message: str):
    query = """
        INSERT INTO server_events (time, server_id, event_type, root_cause, message)
        VALUES ($1, $2, $3, 'UNKNOWN', $4);
    """
    async with pool.acquire() as conn:
        await conn.execute(query, event_time, server_id, event_type, message)


async def run_bridge():
    pool = await asyncpg.create_pool(DB_URL)
    last_seen = datetime.now(timezone.utc)

    print(f"🔗 Bridge ishga tushdi. Anomaly API: {ANOMALY_API_URL}")
    print(f"⏱️  Har {POLL_INTERVAL_SECONDS} soniyada yangi yozuvlar tekshiriladi.\n")

    async with httpx.AsyncClient() as client:
        while True:
            rows = await fetch_new_metrics(pool, last_seen)

            for row in rows:
                payload = build_payload(row)
                result = await send_to_anomaly_api(client, payload)

                if result is None:
                    continue

                if result.get("is_anomaly"):
                    print(
                        f"🚨 ANOMALIYA! server={result['server_id']} "
                        f"score={result['anomaly_score']} "
                        f"sabab={result['reasons']}"
                    )

                    event_type = classify_event_type(result["reasons"])
                    message = "; ".join(result["reasons"]) or "Anomaliya aniqlandi"
                    try:
                        await record_event(
                            pool, row["time"], result["server_id"], event_type, message
                        )
                    except Exception as exc:
                        print(f"⚠️  server_events yozishda xatolik: {exc}")
                else:
                    print(
                        f"✅ {result['server_id']}: normal "
                        f"(score={result['anomaly_score']}, "
                        f"baseline={result['baseline_samples']})"
                    )

                last_seen = row["time"]

            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_bridge())