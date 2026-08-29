from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import joblib
import numpy as np
import pandas as pd
from scipy.sparse import hstack

ROOT_DIR = Path(__file__).resolve().parent
MODELS_DIR = ROOT_DIR / "models"
MODEL_PATH = MODELS_DIR / "root_cause_model.pkl"

_artifact: Optional[dict[str, Any]] = None


def load_model() -> Optional[dict[str, Any]]:
    global _artifact
    if _artifact is None and MODEL_PATH.exists():
        try:
            _artifact = joblib.load(MODEL_PATH)
        except Exception:
            _artifact = None
    return _artifact


def rule_based_labeler(
    player_count: int,
    ping_ms: float,
    anomaly_score: float,
    ping_delta: float,
    player_delta: int,
    servers_affected_same_region: int,
) -> list[dict[str, Any]]:
    """Heuristic labeling rules used during cold-start or low ML confidence."""
    # 1. Multiple servers in region degraded at the same time
    if servers_affected_same_region >= 2:
        return [
            {"rank": 1, "root_cause": "REGIONAL_OUTAGE", "probability": 0.94, "confidence": "HIGH"},
            {"rank": 2, "root_cause": "NETWORK_ISSUE", "probability": 0.04, "confidence": "LOW"},
            {"rank": 3, "root_cause": "DDOS_ATTACK", "probability": 0.02, "confidence": "LOW"},
        ]

    # 2. Server crashed (all players instantly dropped)
    if player_count == 0 and player_delta <= -3:
        return [
            {"rank": 1, "root_cause": "SERVER_CRASH", "probability": 0.95, "confidence": "HIGH"},
            {"rank": 2, "root_cause": "PLAYER_DROP", "probability": 0.03, "confidence": "LOW"},
            {"rank": 3, "root_cause": "MAINTENANCE", "probability": 0.02, "confidence": "LOW"},
        ]

    # 3. DDoS Attack (Extreme latency spike + rapid player disconnects)
    if ping_delta > 140.0 and player_delta < -2:
        return [
            {"rank": 1, "root_cause": "DDOS_ATTACK", "probability": 0.89, "confidence": "HIGH"},
            {"rank": 2, "root_cause": "HIGH_LATENCY", "probability": 0.07, "confidence": "LOW"},
            {"rank": 3, "root_cause": "NETWORK_ISSUE", "probability": 0.04, "confidence": "LOW"},
        ]

    # 4. Latency Spike / ISP congestion
    if ping_ms > 160.0 or ping_delta > 75.0:
        return [
            {"rank": 1, "root_cause": "HIGH_LATENCY", "probability": 0.88, "confidence": "HIGH"},
            {"rank": 2, "root_cause": "NETWORK_ISSUE", "probability": 0.08, "confidence": "LOW"},
            {"rank": 3, "root_cause": "DDOS_ATTACK", "probability": 0.04, "confidence": "LOW"},
        ]

    # 5. Normal match end / player departure
    if player_delta < -4 and ping_ms < 80.0:
        return [
            {"rank": 1, "root_cause": "PLAYER_DROP", "probability": 0.84, "confidence": "HIGH"},
            {"rank": 2, "root_cause": "MAINTENANCE", "probability": 0.10, "confidence": "LOW"},
            {"rank": 3, "root_cause": "SERVER_CRASH", "probability": 0.06, "confidence": "LOW"},
        ]

    return [
        {"rank": 1, "root_cause": "UNKNOWN_ANOMALY", "probability": 0.50, "confidence": "LOW"},
        {"rank": 2, "root_cause": "NETWORK_ISSUE", "probability": 0.30, "confidence": "LOW"},
        {"rank": 3, "root_cause": "HIGH_LATENCY", "probability": 0.20, "confidence": "LOW"},
    ]


def create_feature_vector(
    player_count: int,
    max_players: int,
    ping_ms: float,
    anomaly_score: float,
    ping_delta: float,
    player_delta: int,
    servers_affected_same_region: int,
    region: str,
    timestamp: Optional[datetime],
    scaler,
    encoder,
):
    timestamp = timestamp or datetime.now(timezone.utc)
    hour = timestamp.hour
    minute = timestamp.minute
    day = timestamp.weekday()

    time_feats = np.array([
        np.sin(2 * np.pi * hour / 24),
        np.cos(2 * np.pi * hour / 24),
        np.sin(2 * np.pi * minute / 60),
        np.cos(2 * np.pi * minute / 60),
        np.sin(2 * np.pi * day / 7),
        np.cos(2 * np.pi * day / 7),
    ]).reshape(1, -1)

    safe_max = max(max_players, 1)
    player_ratio = np.clip(player_count / safe_max, 0, 1)
    is_empty = 1.0 if player_count == 0 else 0.0
    is_high_ping = 1.0 if ping_ms > 200 else 0.0

    raw_numeric = np.array([
        player_count,
        safe_max,
        ping_ms,
        anomaly_score,
        ping_delta,
        player_delta,
        servers_affected_same_region,
        player_ratio,
        is_empty,
        is_high_ping,
    ]).reshape(1, -1)

    numeric_scaled = scaler.transform(raw_numeric)
    region_encoded = encoder.transform(pd.DataFrame([{"region": region}]))
    return hstack([numeric_scaled, time_feats, region_encoded]).tocsr()


def predict_root_cause(
    player_count: int,
    server_id: str = "unknown",
    max_players: int = 32,
    ping_ms: float = 50.0,
    anomaly_score: float = 0.0,
    ping_delta: float = 0.0,
    player_delta: int = 0,
    servers_affected_same_region: int = 1,
    region: str = "EU-East",
    timestamp: Optional[datetime] = None,
    top_k: int = 3,
) -> dict[str, Any]:
    artifact = load_model()

    # 1. Model bo'lmasa yoki scaler bo'lmasa qoidalardan foydalanish
    if artifact is None or "scaler" not in artifact:
        results = rule_based_labeler(
            player_count, ping_ms, anomaly_score, ping_delta, player_delta, servers_affected_same_region
        )
    else:
        try:
            model = artifact["model"]
            classes = artifact["classes"]

            X = create_feature_vector(
                player_count=player_count,
                max_players=max_players,
                ping_ms=ping_ms,
                anomaly_score=anomaly_score,
                ping_delta=ping_delta,
                player_delta=player_delta,
                servers_affected_same_region=servers_affected_same_region,
                region=region,
                timestamp=timestamp,
                scaler=artifact["scaler"],
                encoder=artifact["encoder"],
            )

            # ML Ehtimolliklarini hisoblash
            probabilities = model.predict_proba(X)[0]
            ranked_indices = np.argsort(probabilities)[::-1]

            results = []
            for rank, idx in enumerate(ranked_indices[:top_k], start=1):
                prob = float(probabilities[idx])
                cls_name = str(classes[idx])
                conf = "HIGH" if prob > 0.65 else ("MEDIUM" if prob > 0.35 else "LOW")
                results.append({
                    "rank": rank,
                    "root_cause": cls_name,
                    "probability": round(prob, 4),
                    "confidence": conf,
                })

            if results and results[0]["probability"] < 0.40:
                results = rule_based_labeler(
                    player_count, ping_ms, anomaly_score, ping_delta, player_delta, servers_affected_same_region
                )
        except Exception:
            results = rule_based_labeler(
                player_count, ping_ms, anomaly_score, ping_delta, player_delta, servers_affected_same_region
            )

    top_cause = results[0]["root_cause"] if results else "UNKNOWN"
    top_conf = results[0]["confidence"] if results else "LOW"

    # Chuqur tushuntirish generatsiyasi
    narrative = generate_real_world_narrative(
        root_cause=top_cause,
        region=region,
        ping_ms=ping_ms,
        ping_delta=ping_delta,
        player_count=player_count,
        player_delta=player_delta,
        servers_affected_same_region=servers_affected_same_region,
    )

    return {
        "primary_cause": top_cause,
        "confidence": top_conf,
        "explanation": narrative["explanation"],
        "recommendation": narrative["recommendation"],
        "predictions": results,
    }

def generate_real_world_narrative(
    root_cause: str,
    region: str,
    ping_ms: float,
    ping_delta: float,
    player_count: int,
    player_delta: int,
    servers_affected_same_region: int,
) -> dict[str, str]:
    """Generates deep, human-understandable real-world explanations and action items in English."""
    cause = (root_cause or "UNKNOWN").upper()

    if cause == "REGIONAL_OUTAGE":
        return {
            "explanation": f"Major datacenter / upstream ISP outage in {region}. {servers_affected_same_region} servers degraded simultaneously.",
            "recommendation": "Check regional BGP routing status or failover active traffic to an adjacent cluster."
        }

    if cause == "DDOS_ATTACK":
        return {
            "explanation": f"High-volume DDoS / UDP packet flood detected. Latency spiked by +{round(ping_delta, 1)}ms causing {abs(player_delta)} player disconnects due to packet saturation.",
            "recommendation": "Enable Anti-DDoS rate-limiting filters on the target port and inspect inbound traffic."
        }

    if cause == "SERVER_CRASH":
        return {
            "explanation": f"Server process crashed unexpectedly (Segmentation fault / Fatal Error). All players were disconnected immediately while host network and other {region} servers remain healthy.",
            "recommendation": "Inspect server crash dump files and restart the server instance."
        }

    if cause == "HIGH_LATENCY":
        return {
            "explanation": f"Upstream network congestion or suboptimal routing path detected. Server latency is elevated ({round(ping_ms, 1)}ms), but players remain connected.",
            "recommendation": "Analyze packet loss and hops using traceroute to isolate network bottleneck."
        }

    if cause == "PLAYER_DROP":
        return {
            "explanation": "Natural player disconnects due to match completion or map rotation. Server engine and network latency remain stable.",
            "recommendation": "No action required (Normal match flow)."
        }

    if cause == "MAINTENANCE":
        return {
            "explanation": "Scheduled server maintenance or graceful shutdown executed by administrator.",
            "recommendation": "Wait for the scheduled maintenance window to complete."
        }

    return {
        "explanation": "Unclassified telemetry deviation detected.",
        "recommendation": "Inspect live server logs manually."
    }