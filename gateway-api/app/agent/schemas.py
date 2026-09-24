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
    event_id: str = Field(..., gt=0)
    root_cause: Literal[
        "SERVER_CRASH",
        "HIGH_LATENCY",
        "DDOS_ATTACK",
        "REGIONAL_OUTAGE",
        "PLAYER_DROP",
        "MAINTENANCE",
    ]