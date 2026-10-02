from pydantic import BaseModel, Field, model_validator
from typing import Annotated, Literal

# What the browser sends to POST /api/v1/agent/ask

class AskRequest(BaseModel):
    """The user's question, sent from the AskPanel in the frontend."""
    question: str = Field(..., min_length=1, max_length=500)


# What the endpoint returns to the browser

class ChartRow(BaseModel):
    """One bar in an inline chart."""
    label: str
    value: float
    status: str | None = None
    note: str | None = None
    # The server the chart is about -- the best one, or the worst one when
    # the question asked for the worst. The panel draws it apart from the rest.
    highlight: bool = False


class ChartPayload(BaseModel):
    """An inline chart the panel draws underneath the answer.

    Only sent when the question actually asks to compare or rank
    something. A chart attached to "how many servers are online?" answers
    a question nobody asked and buries the number the user wanted.
    """
    chartType: Literal["bar"] = "bar"
    title: str
    # "overview" is the whole-fleet status chart: bars coloured by status
    # rather than a best/worst ranking.
    order: Literal["best", "worst", "overview"] = "best"
    unit: str = "ms"
    rows: list[ChartRow]


class AskResponse(BaseModel):
    """The agent's grounded answer, plus which tool it used (if any)."""
    answer: str
    tool_used: str | None = None
    chart: ChartPayload | None = None


#Tool input schemas

class EventQuery(BaseModel):
    """Input for get_recent_events."""
    limit: int = Field(default=10, ge=1, le=50)


class LatencyQuery(BaseModel):
    """Input for get_average_latency."""
    minutes: int = Field(default=10, ge=1, le=60)
    server_id: str | None = Field(default=None)


class RankingQuery(BaseModel):
    """Input for get_server_ranking."""
    # A day is the longest window worth ranking on: beyond that a server
    # that was fixed this morning still carries last night's crashes.
    hours: int = Field(default=1, ge=1, le=24)
    # How many servers the user asked to see. Deliberately unbounded: a
    # request for 0, -3 or 50 must reach the tool so it can explain itself
    # ("there are only 23") instead of failing validation with a bare 422.
    count: int | None = None
    order: Literal["best", "worst"] = "best"


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


class UnmuteAlertsRequest(BaseModel):
    """Input for unmute_server_alerts: one server, a list, or everything."""
    server_id: str | None = Field(default=None, min_length=1, max_length=100)
    server_ids: list[Annotated[str, Field(min_length=1, max_length=100)]] | None = Field(
        default=None, max_length=100
    )
    all_servers: bool = False

    @model_validator(mode="after")
    def _needs_a_target(self):
        if not (self.server_id or self.server_ids or self.all_servers):
            raise ValueError("Give server_id, server_ids, or all_servers=true")
        return self


class PollRequest(BaseModel):
    """Input for poll_server_now."""
    server_id: str = Field(..., min_length=1, max_length=100)


class DailyReportRequest(BaseModel):
    """Input for generate_daily_report (no arguments required)."""
    pass