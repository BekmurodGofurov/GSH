from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel

class ServerMetric(BaseModel):
    id: str                            # Server IP:Port (masalan: "185.25.180.1:27015")
    game: Literal["cs2", "dota2", "pubg"] = "cs2"
    region: str                        # Region (masalan: "Vienna" yoki "Warsaw")
    player_count: int
    max_players: Optional[int] = None
    tick_rate: Optional[float] = None  # CS2 uchun (masalan: 64.0 yoki 128.0)
    ping_ms: Optional[float] = None
    map: Optional[str] = None          # CS2 xaritasi (masalan: "de_mirage")
    match_duration_s: Optional[int] = None
    timestamp: datetime

class AnomalyPayload(BaseModel):
    metric: ServerMetric
    anomaly_score: float               # 0.0 dan 1.0 gacha ball
    is_anomaly: bool

class AlertPayload(BaseModel):
    metric: ServerMetric
    anomaly_score: float
    root_cause: str                    # "server_crash", "ping_spike", "ddos_pattern"