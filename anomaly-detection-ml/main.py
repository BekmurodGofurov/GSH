from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import datetime
from threading import Lock
from typing import Literal, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field


class ServerMetric(BaseModel):
    id: str
    game: Literal["cs2", "dota2", "pubg"] = "cs2"
    region: str
    player_count: int = Field(ge=0)
    max_players: Optional[int] = Field(default=None, ge=0)
    tick_rate: Optional[float] = Field(default=None, ge=0)
    ping_ms: Optional[float] = Field(default=None, ge=0)
    map: Optional[str] = None
    match_duration_s: Optional[int] = Field(default=None, ge=0)
    timestamp: datetime


class AnomalyRequest(BaseModel):
    metric: ServerMetric


class AnomalyResponse(BaseModel):
    server_id: str
    anomaly_score: float = Field(ge=0.0, le=1.0)
    is_anomaly: bool
    reasons: list[str]
    baseline_samples: int


app = FastAPI(
    title="Game Server Anomaly Detection Service",
    version="1.0.0",
)

# One short history per server. The baseline is deliberately kept in memory for
# this first version; Redis or TimescaleDB can replace it in production.
WINDOW_SIZE = 30
MINIMUM_BASELINE_SAMPLES = 5
ANOMALY_THRESHOLD = 0.75
histories: dict[str, deque[dict[str, float]]] = defaultdict(
    lambda: deque(maxlen=WINDOW_SIZE)
)
history_lock = Lock()


def _mean_and_std(values: list[float]) -> tuple[float, float]:
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, 0.0
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return mean, math.sqrt(variance)


def _feature_score(value: float, previous_values: list[float]) -> float:
    """Convert deviation from the recent baseline into a 0..1 score."""
    mean, std = _mean_and_std(previous_values)
    # A small floor prevents an almost-constant metric from producing huge
    # z-scores because of harmless floating-point noise.
    scale = max(std, abs(mean) * 0.05, 1.0)
    z_score = abs(value - mean) / scale
    return min(z_score / 6.0, 1.0)


def _analyse(metric: ServerMetric) -> AnomalyResponse:
    server_key = f"{metric.game}:{metric.id}"
    current = {
        "player_count": float(metric.player_count),
    }
    if metric.ping_ms is not None:
        current["ping_ms"] = metric.ping_ms
    if metric.tick_rate is not None:
        current["tick_rate"] = metric.tick_rate
    if metric.match_duration_s is not None:
        current["match_duration_s"] = float(metric.match_duration_s)

    with history_lock:
        history = histories[server_key]
        baseline_samples = len(history)
        reasons: list[str] = []
        scores: list[float] = []

        if baseline_samples >= MINIMUM_BASELINE_SAMPLES:
            for feature, value in current.items():
                previous_values = [row[feature] for row in history if feature in row]
                if len(previous_values) >= MINIMUM_BASELINE_SAMPLES:
                    score = _feature_score(value, previous_values)
                    scores.append(score)
                    if score >= 0.75:
                        reasons.append(f"{feature} deviates strongly from its recent baseline")

            # A drop to zero is especially meaningful for a live server and
            # should not be hidden by a moderate score on another feature.
            previous_players = [row["player_count"] for row in history]
            average_players, _ = _mean_and_std(previous_players)
            if metric.player_count == 0 and average_players >= 3:
                scores.append(1.0)
                reasons.append("player_count dropped to zero")

        # Do not add the current observation until after scoring it. Otherwise
        # the anomaly would contaminate its own baseline.
        history.append(current)

    score = max(scores, default=0.0)
    score = round(score, 4)
    return AnomalyResponse(
        server_id=metric.id,
        anomaly_score=score,
        is_anomaly=score >= ANOMALY_THRESHOLD,
        reasons=reasons,
        baseline_samples=baseline_samples,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "anomaly-detection-ml"}


@app.post("/predict/anomaly", response_model=AnomalyResponse)
def predict_anomaly(request: AnomalyRequest) -> AnomalyResponse:
    return _analyse(request.metric)


@app.delete("/baseline/{game}/{server_id}")
def clear_baseline(game: str, server_id: str) -> dict[str, str]:
    histories.pop(f"{game}:{server_id}", None)
    return {"status": "baseline_cleared", "server_id": server_id}
