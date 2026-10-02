import ipaddress
import re
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

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

class ProbeRequest(BaseModel):
    """A one-off "what is on this address?" query from the admin console.

    Accepts `host` or `host:port` (port defaults to 27015, the CS2 default).
    The address is normalised to `host:port` so both services see one form.
    """
    address: str = Field(..., min_length=1, max_length=255)

    @field_validator("address")
    @classmethod
    def _normalise_address(cls, value: str) -> str:
        value = value.strip()
        host, sep, port_text = value.rpartition(":")
        if not sep:
            host, port_text = value, "27015"
        if not host or not re.fullmatch(r"[A-Za-z0-9.\-]{1,253}", host):
            raise ValueError("Enter an IP address or hostname, optionally followed by :port")
        if not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
            raise ValueError("Port must be a number between 1 and 65535")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None  # a hostname, not a literal IP
            # A bare name ("redis", "timescaledb", "localhost") resolves on
            # the container network, not the internet: it would let the probe
            # poke at the stack's own services.
            if "." not in host:
                raise ValueError("Use a public IP address or a full hostname (for example play.example.com)")
        if ip is not None and (ip.is_loopback or ip.is_unspecified or ip.is_link_local or ip.is_multicast):
            raise ValueError("That address cannot be probed")
        return f"{host}:{int(port_text)}"
