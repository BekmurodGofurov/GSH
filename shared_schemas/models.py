from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel

class ServerMetric(BaseModel):
    id: str                            # Server IP:Port (e.g., "185.25.180.1:27015")
    game: Literal["cs2", "dota2", "pubg"] = "cs2"
    region: str                        # Region ("Vienna", "Warsaw", "EU-East")
    player_count: int
    max_players: Optional[int] = 24
    tick_rate: Optional[float] = 128.0  # Default CS2 tickrate
    ping_ms: Optional[float] = None
    map: Optional[str] = "de_mirage"    # Active map
    match_duration_s: Optional[int] = None
    timestamp: datetime

class MetricPayload(BaseModel):
    server_id: str
    player_count: int
    max_players: int
    ping_ms: float

class EventPayload(BaseModel):
    server_id: str
    event_type: str
    root_cause: Optional[str] = "NORMAL"
    message: str

class AnomalyPayload(BaseModel):
    metric: ServerMetric
    anomaly_score: float               # Range from 0.0 to 1.0
    is_anomaly: bool

class AlertPayload(BaseModel):
    metric: ServerMetric
    anomaly_score: float
    root_cause: str                    # e.g., "SERVER_CRASH", "DDOS_ATTACK", "REGIONAL_ISP_OUTAGE"