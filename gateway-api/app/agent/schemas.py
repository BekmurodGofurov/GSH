from pydantic import BaseModel, Field
from typing import Literal

# What the browser sends to POST /api/v1/agent/ask

class AskRequest(BaseModel):
    """The user's question, sent from the AskPanel in the frontend."""
    question: str = Field(..., min_length=1, max_length=500)


# What the endpoint returns to the browser

class AskResponse(BaseModel):
    """The agent's grounded answer, plus which tool it used (if any)."""
    answer: str
    tool_used: str | None = None


#Tool input schemas

class EventQuery(BaseModel):
    """Input for get_recent_events."""
    limit: int = Field(default=10, ge=1, le=50)


class LatencyQuery(BaseModel):
    """Input for get_average_latency."""
    minutes: int = Field(default=10, ge=1, le=60)
    server_id: str | None = Field(default=None)


class RelabelRequest(BaseModel):
    """Input for relabel_event — the one write action."""
    # int, matching server_events.id (SERIAL) and the "integer" type the
    # tool declaration advertises to the model. It was str here, which made
    # every relabel request fail validation before it reached the database.
    event_id: int = Field(..., gt=0)
    root_cause: Literal[
        "SERVER_CRASH",
        "HIGH_LATENCY",
        "DDOS_ATTACK",
        "REGIONAL_OUTAGE",
        "PLAYER_DROP",
        "MAINTENANCE",
    ]


class AcknowledgeRequest(BaseModel):
    """Input for acknowledge_event."""
    event_id: int = Field(..., gt=0)


class MuteAlertsRequest(BaseModel):
    """Input for mute_server_alerts."""
    server_id: str = Field(..., min_length=1, max_length=100)
    minutes: int = Field(..., ge=1, le=10080)
    reason: str | None = Field(default=None, max_length=500)


class PollRequest(BaseModel):
    """Input for poll_server_now."""
    server_id: str = Field(..., min_length=1, max_length=100)


class DailyReportRequest(BaseModel):
    """Input for generate_daily_report (no arguments required)."""
    pass