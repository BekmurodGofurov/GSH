from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel

class ServerMetric(BaseModel):
    id: str                            # Server IP:Port (masalan: "185.25.180.1:27015")
    game: Literal["cs2", "dota2", "pubg"] = "cs2"
    region: str                        # Region ("Vienna" yoki "Warsaw")
    player_count: int
    max_players: Optional[int] = 24
    tick_rate: Optional[float] = 128.0  # CS2 uchun default tickrate
    ping_ms: Optional[float] = None
    map: Optional[str] = "de_mirage"    # CS2 xaritasi
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
    anomaly_score: float               # 0.0 dan 1.0 gacha
    is_anomaly: bool

class AlertPayload(BaseModel):
    metric: ServerMetric
    anomaly_score: float
    root_cause: str                    # "SERVER_CRASH", "DDOS_ATTACK", "REGIONAL_ISP_OUTAGE"