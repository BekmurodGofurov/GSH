import asyncio
import json
import os
import logging
from datetime import datetime, timedelta, timezone

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DB_URL")
ANOMALY_API_URL = os.getenv("ANOMALY_API_URL", "http://localhost:8002/predict/anomaly")
ROOT_CAUSE_API_URL = os.getenv("ROOT_CAUSE_API_URL", "http://localhost:8003/predict/root-cause")
POLL_INTERVAL_SECONDS = float(os.getenv("BRIDGE_POLL_INTERVAL", "5"))
REGIONAL_INCIDENT_WINDOW = timedelta(minutes=1)


async def fetch_new_metrics(pool: asyncpg.Pool, last_seen_time: datetime, last_seen_server_id: str):
    """Fetch each metric with its preceding measurement for delta features."""
    query = """
        SELECT sm.time, sm.server_id, sm.player_count, sm.max_players, sm.ping_ms,
               ms.region, previous.player_count AS previous_player_count,
               previous.ping_ms AS previous_ping_ms
        FROM server_metrics sm
        JOIN monitored_servers ms ON ms.server_id = sm.server_id
        LEFT JOIN LATERAL (
            SELECT player_count, ping_ms
            FROM server_metrics previous_metric
            WHERE previous_metric.server_id = sm.server_id
              AND previous_metric.time < sm.time
            ORDER BY previous_metric.time DESC
            LIMIT 1
        ) previous ON TRUE
        WHERE (sm.time, sm.server_id) > ($1, $2)
        ORDER BY sm.time ASC, sm.server_id ASC;
    """
    async with pool.acquire() as conn:
        return await conn.fetch(query, last_seen_time, last_seen_server_id)


def build_anomaly_payload(row: asyncpg.Record) -> dict:
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


def build_root_cause_payload(row: asyncpg.Record, anomaly: dict, affected_count: int) -> dict:
    previous_ping = row["previous_ping_ms"]
    previous_players = row["previous_player_count"]
    curr_players = row["player_count"] or 0
    curr_ping = float(row["ping_ms"] or 0.0)

    return {
        "server_id": row["server_id"],
        "region": row["region"] or "unknown",
        "player_count": curr_players,
        "max_players": row["max_players"] if row["max_players"] is not None else None,
        "ping_ms": curr_ping,
        "anomaly_score": float(anomaly.get("anomaly_score", 0.8)),
        "ping_delta": curr_ping - float(previous_ping) if previous_ping is not None else 0.0,
        "player_delta": curr_players - int(previous_players) if previous_players is not None else 0,
        "servers_affected_same_region": max(int(affected_count), 1),
        "timestamp": row["time"].isoformat(),
    }


async def post_json(client: httpx.AsyncClient, url: str, payload: dict, service: str):
    try:
        response = await client.post(url, json=payload, timeout=5.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        logger.error(f"{service} request failed: {exc}")
        return None


def classify_event_type(reasons: list[str]) -> str:
    reasons_text = " ".join(reasons).lower()
    if "dropped to zero" in reasons_text:
        return "OFFLINE"
    if "ping_ms" in reasons_text:
        return "HIGH_PING"
    return "CRASH"


async def record_labeled_event(
    pool: asyncpg.Pool,
    row: asyncpg.Record,
    anomaly: dict,
    diagnosis: dict | None,
    event_type: str,
    message: str,
    affected_count: int,
):
    payload = build_root_cause_payload(row, anomaly, affected_count)
    root_cause_label = diagnosis.get("primary_cause", "UNKNOWN") if diagnosis else "UNKNOWN"

    query = """
        INSERT INTO server_events (
            time, server_id, event_type, root_cause, label_source, message,
            anomaly_score, anomaly_reasons, player_count, max_players, ping_ms,
            ping_delta, player_delta, servers_affected_same_region, diagnosis
        ) VALUES ($1, $2, $3, $4, 'model', $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb);
    """
    async with pool.acquire() as conn:
        await conn.execute(
            query,
            row["time"],
            row["server_id"],
            event_type,
            root_cause_label,
            message,
            anomaly["anomaly_score"],
            anomaly["reasons"],
            row["player_count"],
            row["max_players"],
            row["ping_ms"],
            payload["ping_delta"],
            payload["player_delta"],
            affected_count,
            json.dumps(diagnosis) if diagnosis else None,
        )


async def run_bridge():
    pool = await asyncpg.create_pool(DB_URL)
    last_seen_time = datetime.now(timezone.utc)
    last_seen_server_id = ""
    regional_incidents: dict[str, dict[str, datetime]] = {}

    logger.info(f"Bridge Auto-Labeler started. Anomaly API: {ANOMALY_API_URL} | Root-Cause API: {ROOT_CAUSE_API_URL}")

    async with httpx.AsyncClient() as client:
        while True:
            try:
                rows = await fetch_new_metrics(pool, last_seen_time, last_seen_server_id)
                for row in rows:
                    anomaly = await post_json(client, ANOMALY_API_URL, build_anomaly_payload(row), "Anomaly API")
                    if anomaly is None:
                        continue

                    if anomaly.get("is_anomaly"):
                        region = row["region"] or "unknown"
                        cutoff = row["time"] - REGIONAL_INCIDENT_WINDOW

                        active = {
                            s_id: t
                            for s_id, t in regional_incidents.get(region, {}).items()
                            if t >= cutoff
                        }
                        active[row["server_id"]] = row["time"]
                        regional_incidents[region] = active
                        affected_count = len(active)

                        diagnosis = await post_json(
                            client,
                            ROOT_CAUSE_API_URL,
                            build_root_cause_payload(row, anomaly, affected_count),
                            "Root-cause API",
                        )

                        try:
                            deep_msg = (diagnosis.get("explanation") if diagnosis else None) or "; ".join(anomaly["reasons"]) or "Anomaly detected"
                            await record_labeled_event(
                                pool,
                                row,
                                anomaly,
                                diagnosis,
                                classify_event_type(anomaly["reasons"]),
                                deep_msg,
                                affected_count,
                            )
                        except Exception as exc:
                            logger.error(f"Could not persist labeled event: {exc}")

                        cause = diagnosis["primary_cause"] if diagnosis else "UNKNOWN"
                        logger.info(f"[LABELED] server={row['server_id']} score={anomaly['anomaly_score']} root_cause={cause}")

                    last_seen_time = row["time"]
                    last_seen_server_id = row["server_id"]
            except Exception as e:
                logger.error(f"Bridge poll error: {e}")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_bridge())