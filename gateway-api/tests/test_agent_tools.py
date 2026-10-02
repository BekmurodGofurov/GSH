"""
Agent tool tests — covers the 3 required categories from AGENTS.md:
  1. Success — valid input, expected output
  2. Invalid input — Pydantic rejects bad args before DB is touched
  3. DB failure — DB exception surfaces as a clean error, not a crash
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

# The env vars are seeded in conftest.py before this import.
import main as gw
from app.agent import tools, schemas
from tests.conftest import ADMIN_PASSWORD, ADMIN_USERNAME


# ══════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════

def make_pool(fetch_result=None, execute_result="UPDATE 1", error=None):
    """Build a minimal fake asyncpg pool for tool tests."""
    # Reuse the FakeConnection / FakePool already defined in conftest.py
    from tests.conftest import FakeConnection, FakePool
    conn = FakeConnection(fetch_result=fetch_result, execute_result=execute_result, error=error)
    return FakePool(conn), conn


# ══════════════════════════════════════════════════════
# Tool 1: get_server_summary
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_server_summary_success():
    """Returns a list of server dicts when DB has rows."""
    fake_rows = [
        {"server_id": "1.2.3.4:27015", "server_name": "Warsaw #1",
         "region": "Warsaw", "status": "ONLINE", "ping_ms": 42.0,
         "player_count": 10, "max_players": 20, "last_metric_at": None}
    ]
    pool, conn = make_pool(fetch_result=fake_rows)

    result = await tools.get_server_summary(pool)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["server_id"] == "1.2.3.4:27015"
    assert result[0]["status"] == "ONLINE"
    # Verify the correct fixed query was used (not some dynamic string)
    assert "monitored_servers" in conn.queries[0][0]


@pytest.mark.asyncio
async def test_get_server_summary_empty():
    """Returns empty list when no servers are registered."""
    pool, _ = make_pool(fetch_result=[])
    result = await tools.get_server_summary(pool)
    assert result == []


@pytest.mark.asyncio
async def test_get_server_summary_db_failure():
    """DB error surfaces as an exception, not a silent failure."""
    pool, _ = make_pool(error=Exception("connection refused"))
    with pytest.raises(Exception, match="connection refused"):
        await tools.get_server_summary(pool)


# ══════════════════════════════════════════════════════
# Tool 2: get_recent_events
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_recent_events_success():
    """Returns up to `limit` events from the DB."""
    fake_rows = [
        {"id": 1, "time": "2024-01-01T00:00:00", "server_id": "1.2.3.4:27015",
         "event_type": "CRASH", "root_cause": "SERVER_CRASH",
         "label_source": "model", "message": "Server went offline",
         "anomaly_score": 0.95, "diagnosis": "CPU spike"}
    ]
    pool, conn = make_pool(fetch_result=fake_rows)

    result = await tools.get_recent_events(pool, limit=10)

    assert isinstance(result, list)
    assert result[0]["event_type"] == "CRASH"
    # Confirm limit was passed as a query parameter, not interpolated into the string
    assert conn.queries[0][1] == (10,)


def test_get_recent_events_invalid_limit_too_low():
    """limit below 1 is rejected by Pydantic before the tool is called."""
    with pytest.raises(ValidationError):
        schemas.EventQuery(limit=0)


def test_get_recent_events_invalid_limit_too_high():
    """limit above 50 is rejected by Pydantic."""
    with pytest.raises(ValidationError):
        schemas.EventQuery(limit=999)


@pytest.mark.asyncio
async def test_get_recent_events_db_failure():
    """DB failure is raised, not swallowed."""
    pool, _ = make_pool(error=ConnectionError("db timeout"))
    with pytest.raises(ConnectionError):
        await tools.get_recent_events(pool, limit=5)


# ══════════════════════════════════════════════════════
# Tool 3: get_average_latency
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_average_latency_success_all_servers():
    """Returns latency rows for all servers when no server_id given."""
    fake_rows = [
        {"bucket": "2024-01-01T00:00:00", "server_id": "1.2.3.4:27015",
         "avg_ping": 42.3, "avg_players": 8.0}
    ]
    pool, _ = make_pool(fetch_result=fake_rows)
    result = await tools.get_average_latency(pool, minutes=10)
    assert result[0]["avg_ping"] == 42.3


@pytest.mark.asyncio
async def test_get_average_latency_success_single_server():
    """Filters to one server when server_id is provided."""
    fake_rows = [
        {"bucket": "2024-01-01T00:00:00", "server_id": "1.2.3.4:27015",
         "avg_ping": 35.1, "avg_players": 5.0}
    ]
    pool, conn = make_pool(fetch_result=fake_rows)
    result = await tools.get_average_latency(pool, minutes=5, server_id="1.2.3.4:27015")
    assert result[0]["avg_ping"] == 35.1
    # The server_id must be passed as a parameter ($2), not interpolated into SQL
    assert "1.2.3.4:27015" in conn.queries[0][1]


def test_get_average_latency_invalid_minutes_zero():
    """minutes=0 is rejected (must be >= 1)."""
    with pytest.raises(ValidationError):
        schemas.LatencyQuery(minutes=0)


def test_get_average_latency_invalid_minutes_too_high():
    """minutes=61 is rejected (must be <= 60)."""
    with pytest.raises(ValidationError):
        schemas.LatencyQuery(minutes=61)


@pytest.mark.asyncio
async def test_get_average_latency_db_failure():
    """DB failure is raised."""
    pool, _ = make_pool(error=Exception("timeout"))
    with pytest.raises(Exception):
        await tools.get_average_latency(pool, minutes=10)


# ══════════════════════════════════════════════════════
# Tool 4: relabel_event (write action)
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_relabel_event_success():
    """Returns confirmation dict when event is found and updated."""
    pool, conn = make_pool(execute_result="UPDATE 1")

    result = await tools.relabel_event(pool, event_id=5, root_cause="HIGH_LATENCY")

    assert result["event_id"] == 5
    assert result["root_cause"] == "HIGH_LATENCY"
    assert result["label_source"] == "manual"
    assert result["status"] == "relabelled"
    # Confirm the values were passed as parameters, not interpolated
    assert "HIGH_LATENCY" in conn.queries[0][1]
    assert 5 in conn.queries[0][1]


@pytest.mark.asyncio
async def test_relabel_event_not_found():
    """Returns 404 HTTPException when no row is updated."""
    from fastapi import HTTPException
    pool, _ = make_pool(execute_result="UPDATE 0")

    with pytest.raises(HTTPException) as exc_info:
        await tools.relabel_event(pool, event_id=9999, root_cause="MAINTENANCE")

    assert exc_info.value.status_code == 404


def test_relabel_request_accepts_a_numeric_event_id():
    """
    The model sends event_id as a number, so the schema has to take one.

    The three rejection tests below kept passing while event_id was typed
    str: an int input failed the type check before their own condition was
    ever reached, so they went green against a schema no real request
    could satisfy. This pins down the accepting case.
    """
    assert schemas.RelabelRequest(event_id=5, root_cause="HIGH_LATENCY").event_id == 5
    # A model that sends the id as a string still works -- Pydantic coerces.
    assert schemas.RelabelRequest(event_id="7", root_cause="MAINTENANCE").event_id == 7


def test_relabel_event_invalid_root_cause():
    """Rejects a root_cause string that isn't in the allowed Literal list."""
    with pytest.raises(ValidationError):
        schemas.RelabelRequest(event_id=1, root_cause="DROP TABLE server_events")


def test_relabel_event_invalid_event_id_zero():
    """event_id must be > 0."""
    with pytest.raises(ValidationError):
        schemas.RelabelRequest(event_id=0, root_cause="MAINTENANCE")


def test_relabel_event_invalid_event_id_negative():
    """Negative event_id is rejected."""
    with pytest.raises(ValidationError):
        schemas.RelabelRequest(event_id=-1, root_cause="MAINTENANCE")


@pytest.mark.asyncio
async def test_relabel_event_db_failure():
    """DB exception surfaces as an exception, not a silent no-op."""
    pool, _ = make_pool(error=Exception("db connection lost"))
    with pytest.raises(Exception, match="db connection lost"):
        await tools.relabel_event(pool, event_id=1, root_cause="SERVER_CRASH")


# ══════════════════════════════════════════════════════
# Tool 4: acknowledge_event
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_acknowledge_event_success():
    pool, conn = make_pool(execute_result="UPDATE 1")
    result = await tools.acknowledge_event(pool, event_id=42)
    assert result == {"event_id": 42, "status": "acknowledged"}
    assert conn.queries[0][1] == (42,)


def test_acknowledge_event_invalid_id():
    with pytest.raises(ValidationError):
        schemas.AcknowledgeRequest(event_id=0)
    with pytest.raises(ValidationError):
        schemas.AcknowledgeRequest(event_id=-5)


@pytest.mark.asyncio
async def test_acknowledge_event_not_found():
    from fastapi import HTTPException
    pool, _ = make_pool(execute_result="UPDATE 0")
    with pytest.raises(HTTPException) as exc:
        await tools.acknowledge_event(pool, event_id=999)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_acknowledge_event_db_failure():
    pool, _ = make_pool(error=Exception("db failure"))
    with pytest.raises(Exception, match="db failure"):
        await tools.acknowledge_event(pool, event_id=1)


# ══════════════════════════════════════════════════════
# get_muted_servers
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_muted_servers_lists_active_mutes():
    pool, _ = make_pool(fetch_result=[
        {"server_id": "a:1", "server_name": "Seven", "region": "Warsaw",
         "muted_until": None, "muted_by": "admin", "reason": "maintenance"},
    ])

    result = await tools.get_muted_servers(pool)

    assert result["muted_count"] == 1
    assert result["muted_servers"][0]["server_name"] == "Seven"
    assert result["note"] is None


@pytest.mark.asyncio
async def test_get_muted_servers_when_none_are_muted():
    pool, _ = make_pool(fetch_result=[])

    result = await tools.get_muted_servers(pool)

    assert result["muted_count"] == 0
    assert "No server" in result["note"]


@pytest.mark.asyncio
async def test_get_muted_servers_db_failure():
    pool, _ = make_pool(error=RuntimeError("db down"))

    with pytest.raises(RuntimeError):
        await tools.get_muted_servers(pool)


@pytest.mark.asyncio
async def test_muted_servers_endpoint(client, db):
    db._fetch_result = [{"server_id": "a:1", "server_name": "Seven", "region": "W",
                         "muted_until": None, "muted_by": "admin", "reason": None}]

    response = await client.get("/api/v1/agent/tools/muted-servers")

    assert response.status_code == 200
    assert response.json()["muted_count"] == 1


# ══════════════════════════════════════════════════════
# unmute_server_alerts
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_unmute_server_alerts_success():
    pool, _ = make_pool(fetch_result=[{"server_id": "1.2.3.4:27015"}])

    result = await tools.unmute_server_alerts(pool, server_id="1.2.3.4:27015")

    assert result["status"] == "unmuted"
    assert result["unmuted"] == ["1.2.3.4:27015"]


@pytest.mark.asyncio
async def test_unmute_several_servers_in_one_call():
    """"Unmute the first three" is one tool call, not three confirmations."""
    pool, conn = make_pool(fetch_result=[{"server_id": "a:1"}, {"server_id": "b:1"}])

    result = await tools.unmute_server_alerts(pool, server_ids=["a:1", "b:1", "c:1"])

    assert result["unmuted"] == ["a:1", "b:1"]
    assert result["unmuted_count"] == 2
    # c:1 was not muted: reported back, not an error.
    assert result["not_muted"] == ["c:1"]


@pytest.mark.asyncio
async def test_unmute_all_servers_at_once():
    pool, _ = make_pool(fetch_result=[{"server_id": f"s{i}:1"} for i in range(7)])

    result = await tools.unmute_server_alerts(pool, all_servers=True)

    assert result["unmuted_count"] == 7
    assert result["not_muted"] == []


def test_unmute_server_alerts_invalid_input():
    with pytest.raises(ValidationError):
        schemas.UnmuteAlertsRequest()
    with pytest.raises(ValidationError):
        schemas.UnmuteAlertsRequest(server_id="")
    with pytest.raises(ValidationError):
        schemas.UnmuteAlertsRequest(server_ids=[""])


@pytest.mark.asyncio
async def test_unmute_without_any_target_is_refused():
    from fastapi import HTTPException
    pool, _ = make_pool()

    with pytest.raises(HTTPException) as exc:
        await tools.unmute_server_alerts(pool)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("kwargs", [{"server_id": "1.2.3.4:27015"}, {"all_servers": True}])
async def test_unmute_server_alerts_without_an_active_mute(kwargs):
    from fastapi import HTTPException
    pool, _ = make_pool(fetch_result=[])

    with pytest.raises(HTTPException) as exc:
        await tools.unmute_server_alerts(pool, **kwargs)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_unmute_server_alerts_db_failure():
    pool, _ = make_pool(error=RuntimeError("db down"))

    with pytest.raises(RuntimeError):
        await tools.unmute_server_alerts(pool, server_ids=["1.2.3.4:27015"])


@pytest.mark.asyncio
async def test_bulk_unmute_endpoint_needs_an_admin(client, db):
    response = await client.post("/api/v1/alerts/unmute", json={"all_servers": True})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_bulk_unmute_endpoint(client, db, admin_headers):
    db._fetch_result = [{"server_id": "a:1"}, {"server_id": "b:1"}]

    response = await client.post("/api/v1/alerts/unmute", json={"all_servers": True}, headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["unmuted_count"] == 2


# ══════════════════════════════════════════════════════
# Tool 5: mute_server_alerts
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_mute_server_alerts_success():
    import datetime
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchval.return_value = 1
    conn.fetchrow.return_value = {
        "id": 10,
        "muted_until": datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.timezone.utc),
    }
    pool.acquire.return_value.__aenter__.return_value = conn

    result = await tools.mute_server_alerts(pool, server_id="1.2.3.4:27015", minutes=30, reason="Maintenance")
    assert result["status"] == "muted"
    assert result["server_id"] == "1.2.3.4:27015"
    assert result["silence_id"] == 10


def test_mute_server_alerts_invalid_input():
    with pytest.raises(ValidationError):
        schemas.MuteAlertsRequest(server_id="", minutes=10)
    with pytest.raises(ValidationError):
        schemas.MuteAlertsRequest(server_id="1.2.3.4:27015", minutes=0)
    with pytest.raises(ValidationError):
        schemas.MuteAlertsRequest(server_id="1.2.3.4:27015", minutes=20000)


@pytest.mark.asyncio
async def test_mute_server_alerts_not_found():
    from fastapi import HTTPException
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchval.return_value = None
    pool.acquire.return_value.__aenter__.return_value = conn

    with pytest.raises(HTTPException) as exc:
        await tools.mute_server_alerts(pool, server_id="unknown:27015", minutes=30)
    assert exc.value.status_code == 404


# ══════════════════════════════════════════════════════
# Tool 6: poll_server_now
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_poll_server_now_success():
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"server_id": "1.2.3.4:27015", "ping_ms": 25.0}

    with patch("httpx.AsyncClient.post", return_value=fake_resp):
        result = await tools.poll_server_now(None, server_id="1.2.3.4:27015")
    assert result["ping_ms"] == 25.0


def test_poll_server_now_invalid_input():
    with pytest.raises(ValidationError):
        schemas.PollRequest(server_id="")


@pytest.mark.asyncio
async def test_poll_server_now_service_unreachable():
    import httpx
    from fastapi import HTTPException
    with patch("httpx.AsyncClient.post", side_effect=httpx.RequestError("service down")):
        with pytest.raises(HTTPException) as exc:
            await tools.poll_server_now(None, server_id="1.2.3.4:27015")
    assert exc.value.status_code == 503


# ══════════════════════════════════════════════════════
# Tool 7: generate_daily_report
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_generate_daily_report_cached():
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "report_text": "All servers healthy",
        "json_data": '{"uptime": 99.9}',
    }
    pool.acquire.return_value.__aenter__.return_value = conn

    result = await tools.generate_daily_report(pool)
    assert result["report_text"] == "All servers healthy"
    assert result["json_data"]["uptime"] == 99.9


@pytest.mark.asyncio
async def test_generate_daily_report_not_generated():
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    pool.acquire.return_value.__aenter__.return_value = conn

    result = await tools.generate_daily_report(pool)
    assert result["status"] == "not_generated"


# ══════════════════════════════════════════════════════
# Endpoint: POST /api/v1/agent/ask
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ask_endpoint_calls_tool_and_returns_answer(client, db):
    """
    End-to-end: question → Gemini mocked to request get_server_summary
    → tool runs against fake DB → Gemini mocked to return answer
    → endpoint returns AskResponse.
    """
    # Fake server row that the tool will return
    db._fetch_result = [
        {"server_id": "1.2.3.4:27015", "server_name": "Warsaw #1",
         "region": "Warsaw", "status": "ONLINE", "ping_ms": 42.0,
         "player_count": 10, "max_players": 20, "last_metric_at": None}
    ]

    # Build fake Gemini responses
    fake_function_call = MagicMock()
    fake_function_call.name = "get_server_summary"
    fake_function_call.args = {}
    fake_function_call.id = None 

    fake_part_with_call = MagicMock()
    fake_part_with_call.function_call = fake_function_call
    fake_part_with_call.text = None

    fake_candidate = MagicMock()
    fake_candidate.content.parts = [fake_part_with_call]

    fake_turn1 = MagicMock()
    fake_turn1.candidates = [fake_candidate]
    fake_turn1.text = None

    fake_turn2 = MagicMock()
    fake_turn2.text = "Warsaw #1 is ONLINE with 42ms average ping and 10/20 players."

    with patch("app.agent.router._client") as mock_client:
        mock_client.models.generate_content.side_effect = [fake_turn1, fake_turn2]

        response = await client.post(
            "/api/v1/agent/ask",
            json={"question": "What servers are online?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["tool_used"] == "get_server_summary"
    assert "Warsaw" in data["answer"]


@pytest.mark.asyncio
async def test_ask_endpoint_rejects_empty_question(client):
    """Empty question is rejected by AskRequest validation."""
    response = await client.post("/api/v1/agent/ask", json={"question": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ask_endpoint_db_not_ready(monkeypatch, client):
    """Returns 503 when the DB pool is not initialised."""
    monkeypatch.setattr(gw, "db_pool", None)
    response = await client.post("/api/v1/agent/ask", json={"question": "hello"})
    assert response.status_code == 503

@pytest.mark.asyncio
async def test_ask_endpoint_surfaces_llm_provider_failure(client, db):
    """
    A provider-side failure (retired model id, bad key, quota) must come
    back as a clean 502, not an unhandled exception.

    An unhandled one renders as a bare 500 outside the CORS middleware, so
    the browser reports it as "No Access-Control-Allow-Origin" and the
    actual cause never reaches the dashboard.
    """
    from google.genai import errors as genai_errors

    provider_error = genai_errors.ClientError(
        404,
        {
            "error": {
                "code": 404,
                "message": "This model models/gemini-2.0-flash is no longer available.",
                "status": "NOT_FOUND",
            }
        },
    )

    with patch("app.agent.router._client") as mock_client:
        mock_client.models.generate_content.side_effect = provider_error

        response = await client.post(
            "/api/v1/agent/ask",
            json={"question": "What servers are online?"},
        )

    assert response.status_code == 502
    assert "no longer available" in response.json()["detail"]


@pytest.mark.asyncio
async def test_ask_endpoint_retries_transient_provider_error(monkeypatch, client, db):
    """
    A 503 ("model is experiencing high demand") is transient, so the
    endpoint retries instead of failing the user's question outright.
    """
    from app.agent import router as agent_router
    from google.genai import errors as genai_errors

    monkeypatch.setattr(agent_router, "_RETRY_BACKOFF_SECONDS", 0)

    overloaded = genai_errors.ClientError(
        503,
        {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}},
    )
    answered = MagicMock()
    answered.candidates = [MagicMock(content=MagicMock(parts=[]))]
    answered.text = "All 23 servers are online."

    with patch("app.agent.router._client") as mock_client:
        # Fails once, succeeds on the retry.
        mock_client.models.generate_content.side_effect = [overloaded, answered]

        response = await client.post(
            "/api/v1/agent/ask",
            json={"question": "How many servers are online?"},
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "All 23 servers are online."
    assert mock_client.models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_ask_endpoint_does_not_retry_quota_errors(client, db):
    """A 429 is a spent quota, not a blip: retrying it only burns more."""
    from google.genai import errors as genai_errors

    quota_error = genai_errors.ClientError(
        429,
        {"error": {"code": 429, "message": "You exceeded your current quota",
                   "status": "RESOURCE_EXHAUSTED"}},
    )

    with patch("app.agent.router._client") as mock_client:
        mock_client.models.generate_content.side_effect = quota_error

        response = await client.post(
            "/api/v1/agent/ask",
            json={"question": "How many servers are online?"},
        )

    assert response.status_code == 502
    assert "quota" in response.json()["detail"].lower()
    assert mock_client.models.generate_content.call_count == 1


# ══════════════════════════════════════════════════════
# Tool 8: get_fleet_overview
#
# This tool exists because the agent used to answer "how many players are
# online?" by summing a truncated server list, which reported 19 players
# on a fleet that had 45. The totals are computed in SQL now; these tests
# pin that they are passed through untouched.
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_fleet_overview_success():
    """Totals come straight from the single aggregate row."""
    pool, conn = make_pool(fetch_result=[{
        "total_servers": 23, "online_servers": 23, "offline_servers": 0,
        "stale_servers": 0, "total_players": 45, "total_slots": 230,
        "avg_ping": 61.4, "last_metric_at": None,
    }])

    result = await tools.get_fleet_overview(pool)

    assert result["total_servers"] == 23
    assert result["total_players"] == 45
    assert result["avg_ping"] == 61.4
    # Nothing is stale, so no caveat is attached.
    assert "note" in result or result["stale_servers"] == 0
    assert "monitored_servers" in conn.queries[0][0]


@pytest.mark.asyncio
async def test_get_fleet_overview_flags_stale_servers():
    """A short player count is labelled, not presented as the whole fleet."""
    pool, _ = make_pool(fetch_result=[{
        "total_servers": 23, "online_servers": 20, "offline_servers": 3,
        "stale_servers": 4, "total_players": 30, "total_slots": 200,
        "avg_ping": 58.0, "last_metric_at": None,
    }])

    result = await tools.get_fleet_overview(pool)

    assert "4 server(s)" in result["note"]
    assert "not included in the player count" in result["note"]


@pytest.mark.asyncio
async def test_get_fleet_overview_no_servers():
    """An empty fleet reports zeros rather than raising."""
    pool, _ = make_pool(fetch_result=[])
    result = await tools.get_fleet_overview(pool)
    assert result["total_servers"] == 0
    assert result["total_players"] == 0


@pytest.mark.asyncio
async def test_get_fleet_overview_db_failure():
    """DB error surfaces instead of returning a made-up total."""
    pool, _ = make_pool(error=Exception("connection refused"))
    with pytest.raises(Exception, match="connection refused"):
        await tools.get_fleet_overview(pool)


# ══════════════════════════════════════════════════════
# Tool 9: get_server_ranking
# ══════════════════════════════════════════════════════

def rank_row(**overrides):
    """A ranking row shaped like SERVER_RANKING_QUERY returns one."""
    row = {
        "server_id": "1.2.3.4:27015",
        "server_name": "Warsaw #1",
        "region": "Warsaw",
        "status": "ONLINE",
        "avg_ping": 50.0,
        "ping_jitter": 2.0,
        "p95_ping": 55.0,
        "sample_count": 100,
        "responsive_samples": 100,
        "uptime_pct": 100.0,
        "last_metric_at": None,
        "crash_count": 0,
        "anomaly_count": 0,
        "player_count": 10,
        "max_players": 20,
        "current_ping": 49.0,
        "metric_age_s": 3.0,
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_get_server_ranking_prefers_stability_over_raw_ping():
    """
    The whole point of the tool: a steady server that never dropped out
    beats a faster one that crashed twice.

    Ranking on the latest ping alone named a different "best server" on
    every ask, and ignored that the winner had been falling over.
    """
    pool, conn = make_pool(fetch_result=[
        rank_row(server_id="fast:27015", server_name="Fast but flaky",
                 avg_ping=25.0, crash_count=2, uptime_pct=90.0),
        rank_row(server_id="steady:27015", server_name="Slower but solid",
                 avg_ping=60.0, crash_count=0, uptime_pct=100.0),
    ])

    result = await tools.get_server_ranking(pool, hours=1)

    assert [r["server_id"] for r in result["ranked"]] == ["steady:27015", "fast:27015"]
    assert result["best"]["server_name"] == "Slower but solid"
    assert result["ranked"][0]["rank"] == 1
    # The window was passed as a query parameter, not spliced into SQL.
    assert conn.queries[0][1] == (1,)


@pytest.mark.asyncio
async def test_get_server_ranking_explains_a_higher_ping_winner():
    """The answer has to say why the slower server won, not just name it."""
    pool, _ = make_pool(fetch_result=[
        rank_row(server_id="fast:27015", server_name="Fast but flaky",
                 avg_ping=25.0, crash_count=3, uptime_pct=88.0),
        rank_row(server_id="steady:27015", server_name="Slower but solid",
                 avg_ping=60.0, crash_count=0, uptime_pct=100.0),
    ])

    result = await tools.get_server_ranking(pool, hours=1)

    assert "stability" in result["why_best"]
    assert "Slower but solid" in result["why_best"]
    reasons = " ".join(result["best"]["reasons"])
    assert "no crashes" in reasons
    assert "steady" in reasons


@pytest.mark.asyncio
async def test_get_server_ranking_excludes_offline_and_stale_servers():
    """A server that is down, or has stopped reporting, cannot be 'best'."""
    pool, _ = make_pool(fetch_result=[
        rank_row(server_id="down:27015", status="OFFLINE", avg_ping=10.0),
        rank_row(server_id="silent:27015", avg_ping=12.0, metric_age_s=900.0),
        rank_row(server_id="live:27015", avg_ping=70.0),
    ])

    result = await tools.get_server_ranking(pool, hours=1)

    assert [r["server_id"] for r in result["ranked"]] == ["live:27015"]
    excluded = {e["server_id"]: e["excluded_because"] for e in result["excluded"]}
    assert "offline" in excluded["down:27015"]
    assert "health check" in excluded["silent:27015"]


@pytest.mark.asyncio
async def test_get_server_ranking_no_eligible_servers():
    """Returns no winner rather than inventing one when nothing qualifies."""
    pool, _ = make_pool(fetch_result=[rank_row(status="OFFLINE")])
    result = await tools.get_server_ranking(pool, hours=1)
    assert result["ranked"] == []
    assert "best" not in result


def test_get_server_ranking_invalid_hours():
    """hours outside 1–24 is rejected before the DB is touched."""
    with pytest.raises(ValidationError):
        schemas.RankingQuery(hours=0)
    with pytest.raises(ValidationError):
        schemas.RankingQuery(hours=25)
    assert schemas.RankingQuery().hours == 1


@pytest.mark.asyncio
async def test_get_server_ranking_db_failure():
    """DB failure is raised, not answered around."""
    pool, _ = make_pool(error=Exception("db timeout"))
    with pytest.raises(Exception, match="db timeout"):
        await tools.get_server_ranking(pool, hours=1)


# ══════════════════════════════════════════════════════
# Charts: only where a chart was the question
# ══════════════════════════════════════════════════════

def test_counting_questions_get_no_chart():
    """
    "How many servers are online?" used to come back with a ten-bar
    latency chart stacked above a one-line answer. Only the ranking tool
    produces a chart now.
    """
    from app.agent import router as agent_router

    assert agent_router._build_chart("get_fleet_overview", {"total_servers": 23}) is None
    assert agent_router._build_chart("get_server_summary", [{"server_id": "a"}]) is None
    assert agent_router._build_chart("get_recent_events", []) is None


def test_ranking_chart_matches_the_ranking_order():
    """The bars are the ranking's own averages, in the ranking's own order."""
    from app.agent import router as agent_router

    chart = agent_router._build_chart("get_server_ranking", {
        "window_hours": 1,
        "order": "best",
        "shown": [
            {"server_name": "Solid", "avg_ping": 60.0, "crash_count": 0, "rank": 1},
            {"server_name": "Flaky", "avg_ping": 25.0, "crash_count": 2, "rank": 2},
        ],
    })

    assert [r.label for r in chart.rows] == ["Solid", "Flaky"]
    assert [r.value for r in chart.rows] == [60.0, 25.0]
    # The crash count travels with the bar, so the chart cannot read as
    # "lowest bar wins" when the ranking says otherwise.
    assert chart.rows[0].note is None
    assert chart.rows[1].note == "2 crash(es)"
    # Only the winner is set apart.
    assert [r.highlight for r in chart.rows] == [True, False]
    assert chart.order == "best"


def test_ranking_chart_is_empty_when_nothing_ranked():
    from app.agent import router as agent_router
    assert agent_router._build_chart("get_server_ranking", {"ranked": [], "shown": []}) is None


# ── "top N" / "worst N": how many servers a ranking shows ──────────────

def _fleet(n):
    """n eligible servers, server 1 the best."""
    return [rank_row(server_id=f"10.0.0.{i}:27015", server_name=f"S{i}", avg_ping=10.0 * i)
            for i in range(1, n + 1)]


@pytest.mark.asyncio
async def test_ranking_shows_the_best_five_by_default():
    pool, _ = make_pool(fetch_result=_fleet(23))
    result = await tools.get_server_ranking(pool, hours=1)

    assert [r["server_name"] for r in result["shown"]] == ["S1", "S2", "S3", "S4", "S5"]
    assert result["count_note"] is None
    # `ranked` still holds the whole fleet, with global rank numbers.
    assert len(result["ranked"]) == 23


@pytest.mark.asyncio
async def test_ranking_honours_the_number_the_user_asked_for():
    pool, _ = make_pool(fetch_result=_fleet(23))
    assert len((await tools.get_server_ranking(pool, hours=1, count=10))["shown"]) == 10
    assert len((await tools.get_server_ranking(pool, hours=1, count=3))["shown"]) == 3


@pytest.mark.asyncio
async def test_ranking_worst_comes_back_worst_first():
    pool, _ = make_pool(fetch_result=_fleet(23))
    result = await tools.get_server_ranking(pool, hours=1, order="worst")

    assert [r["server_name"] for r in result["shown"]] == ["S23", "S22", "S21", "S20", "S19"]


@pytest.mark.asyncio
async def test_ranking_asked_for_more_than_exist_says_how_many_there_are():
    pool, _ = make_pool(fetch_result=_fleet(23))
    result = await tools.get_server_ranking(pool, hours=1, count=50)

    assert len(result["shown"]) == 23
    assert result["available_count"] == 23
    assert "23" in result["count_note"] and "50" in result["count_note"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [0, -4])
async def test_ranking_rejects_zero_and_negative_counts(bad):
    from app.agent import router as agent_router

    pool, _ = make_pool(fetch_result=_fleet(23))
    result = await tools.get_server_ranking(pool, hours=1, count=bad)

    assert result["shown"] == []
    assert "not a valid number" in result["count_note"]
    # No servers shown, so no chart either.
    assert agent_router._build_chart("get_server_ranking", result) is None


def test_worst_chart_is_labelled_and_highlights_the_worst_server():
    from app.agent import router as agent_router

    chart = agent_router._build_chart("get_server_ranking", {
        "window_hours": 1,
        "order": "worst",
        "shown": [
            {"server_name": "Bad", "avg_ping": 200.0, "crash_count": 3},
            {"server_name": "Meh", "avg_ping": 120.0, "crash_count": 0},
        ],
    })

    assert chart.order == "worst"
    assert "worst" in chart.title
    assert chart.rows[0].highlight and not chart.rows[1].highlight


def test_a_single_server_gets_no_chart():
    from app.agent import router as agent_router

    chart = agent_router._build_chart("get_server_ranking", {
        "window_hours": 1, "order": "best",
        "shown": [{"server_name": "Only", "avg_ping": 30.0, "crash_count": 0}],
    })

    assert chart is None


def test_chart_is_not_capped_below_what_was_asked():
    from app.agent import router as agent_router

    shown = [{"server_name": f"S{i}", "avg_ping": float(i), "crash_count": 0} for i in range(1, 24)]
    chart = agent_router._build_chart("get_server_ranking", {"window_hours": 1, "order": "best", "shown": shown})

    assert len(chart.rows) == 23


# ══════════════════════════════════════════════════════
# Endpoints the voice agent reads the same numbers through
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_fleet_overview_endpoint(client, db):
    """The voice worker gets its totals from here, not from its own query."""
    db._fetch_result = [{
        "total_servers": 23, "online_servers": 23, "offline_servers": 0,
        "stale_servers": 0, "total_players": 45, "total_slots": 230,
        "avg_ping": 61.4, "last_metric_at": None,
    }]

    response = await client.get("/api/v1/agent/tools/fleet-overview")

    assert response.status_code == 200
    assert response.json()["total_players"] == 45


@pytest.mark.asyncio
async def test_server_ranking_endpoint(client, db):
    db._fetch_result = [
        rank_row(server_id="live:27015", avg_ping=42.0),
        rank_row(server_id="live2:27015", avg_ping=80.0),
    ]

    response = await client.get("/api/v1/agent/tools/server-ranking?hours=6")

    assert response.status_code == 200
    body = response.json()
    assert body["window_hours"] == 6
    assert body["ranked"][0]["server_id"] == "live:27015"
    # The voice worker draws this chart instead of building its own.
    assert body["chart"]["rows"][0]["highlight"] is True


@pytest.mark.asyncio
async def test_server_ranking_endpoint_passes_count_and_order(client, db):
    db._fetch_result = [rank_row(server_id=f"s{i}:1", server_name=f"S{i}", avg_ping=10.0 * i) for i in range(1, 9)]

    body = (await client.get("/api/v1/agent/tools/server-ranking?count=3&order=worst")).json()

    assert [r["server_name"] for r in body["shown"]] == ["S8", "S7", "S6"]
    assert body["chart"]["order"] == "worst"
    assert len(body["chart"]["rows"]) == 3


@pytest.mark.asyncio
async def test_server_ranking_endpoint_rejects_bad_window(client, db):
    """hours is validated at the edge, the same bounds as the tool schema."""
    assert (await client.get("/api/v1/agent/tools/server-ranking?hours=0")).status_code == 422
    assert (await client.get("/api/v1/agent/tools/server-ranking?hours=99")).status_code == 422


@pytest.mark.asyncio
async def test_tool_endpoints_report_db_not_ready(monkeypatch, client):
    monkeypatch.setattr(gw, "db_pool", None)
    assert (await client.get("/api/v1/agent/tools/fleet-overview")).status_code == 503
    assert (await client.get("/api/v1/agent/tools/server-ranking")).status_code == 503


@pytest.mark.asyncio
async def test_ask_endpoint_returns_a_chart_with_a_ranking_answer(client, db):
    """A ranking question comes back with the chart attached to the answer."""
    db._fetch_result = [
        rank_row(server_id="live:27015", server_name="Solid", avg_ping=42.0),
        rank_row(server_id="live2:27015", server_name="Other", avg_ping=90.0),
    ]

    fake_function_call = MagicMock()
    fake_function_call.name = "get_server_ranking"
    fake_function_call.args = {"hours": 1}
    fake_function_call.id = None

    fake_part = MagicMock()
    fake_part.function_call = fake_function_call
    fake_part.text = None

    fake_turn1 = MagicMock()
    fake_turn1.candidates = [MagicMock(content=MagicMock(parts=[fake_part]))]
    fake_turn1.text = None

    fake_turn2 = MagicMock()
    fake_turn2.text = "Solid is the best server: 42ms average ping and no crashes in the last hour."

    with patch("app.agent.router._client") as mock_client:
        mock_client.models.generate_content.side_effect = [fake_turn1, fake_turn2]
        response = await client.post(
            "/api/v1/agent/ask", json={"question": "What's the best server?"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["tool_used"] == "get_server_ranking"
    assert data["chart"]["rows"][0]["label"] == "Solid"


@pytest.mark.asyncio
async def test_ask_endpoint_sends_no_chart_for_a_counting_question(client, db):
    """A count comes back as a number, with no chart riding along."""
    db._fetch_result = [{
        "total_servers": 23, "online_servers": 23, "offline_servers": 0,
        "stale_servers": 0, "total_players": 45, "total_slots": 230,
        "avg_ping": 61.4, "last_metric_at": None,
    }]

    fake_function_call = MagicMock()
    fake_function_call.name = "get_fleet_overview"
    fake_function_call.args = {}
    fake_function_call.id = None

    fake_part = MagicMock()
    fake_part.function_call = fake_function_call
    fake_part.text = None

    fake_turn1 = MagicMock()
    fake_turn1.candidates = [MagicMock(content=MagicMock(parts=[fake_part]))]
    fake_turn1.text = None

    fake_turn2 = MagicMock()
    fake_turn2.text = "There are 45 players across 23 online servers."

    with patch("app.agent.router._client") as mock_client:
        mock_client.models.generate_content.side_effect = [fake_turn1, fake_turn2]
        response = await client.post(
            "/api/v1/agent/ask", json={"question": "How many players are online?"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["chart"] is None
    assert "45" in data["answer"]


# ══════════════════════════════════════════════════════
# P2 authorization
#
# P1/P2 used to be a prompt instruction and nothing more on this
# endpoint. The typed channel wrote straight to the database with no
# login at all, while the spoken one went through an authenticated
# endpoint and got a 403 -- the same sentence was refused by voice and
# carried out by text.
# ══════════════════════════════════════════════════════

def _model_calls(tool_name, args, answer="done"):
    """Build the two mocked Gemini turns for a tool call."""
    call = MagicMock()
    call.name = tool_name
    call.args = args
    call.id = None

    part = MagicMock()
    part.function_call = call
    part.text = None

    turn1 = MagicMock()
    turn1.candidates = [MagicMock(content=MagicMock(parts=[part]))]
    turn1.text = None

    turn2 = MagicMock()
    turn2.text = answer
    return [turn1, turn2]


@pytest.mark.asyncio
async def test_p2_tool_is_refused_without_an_admin_login(client, db):
    """An anonymous visitor cannot mute a server by asking the agent to."""
    with patch("app.agent.router._client") as mock_client:
        mock_client.models.generate_content.side_effect = _model_calls(
            "mute_server_alerts", {"server_id": "1.2.3.4:27015", "minutes": 30}
        )
        response = await client.post(
            "/api/v1/agent/ask",
            json={"question": "Mute alerts for 1.2.3.4:27015 for 30 minutes. Yes, do it."},
        )

    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()
    # The refusal happens before the database is touched.
    assert db.queries == []


@pytest.mark.asyncio
async def test_p2_tool_runs_for_an_admin(client, db, admin_headers):
    """With an admin key the same request goes through."""
    with patch("app.agent.router._client") as mock_client:
        mock_client.models.generate_content.side_effect = _model_calls(
            "acknowledge_event", {"event_id": 7}, answer="Event 7 acknowledged."
        )
        response = await client.post(
            "/api/v1/agent/ask",
            json={"question": "Acknowledge event 7. Confirmed."},
            headers=admin_headers,
        )

    assert response.status_code == 200
    assert response.json()["tool_used"] == "acknowledge_event"


@pytest.mark.asyncio
async def test_p2_tool_accepts_the_dashboard_session_cookie(client, db):
    """An admin signed in through the dashboard is an admin here too."""
    login = await client.post(
        "/api/v1/admin/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200

    with patch("app.agent.router._client") as mock_client:
        mock_client.models.generate_content.side_effect = _model_calls(
            "acknowledge_event", {"event_id": 3}, answer="Event 3 acknowledged."
        )
        response = await client.post(
            "/api/v1/agent/ask", json={"question": "Acknowledge event 3. Confirmed."}
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_p1_tools_stay_open_to_everyone(client, db):
    """Asking what the servers are doing must not require a login."""
    db._fetch_result = [{
        "total_servers": 23, "online_servers": 23, "offline_servers": 0,
        "stale_servers": 0, "total_players": 45, "total_slots": 230,
        "avg_ping": 61.4, "last_metric_at": None,
    }]

    with patch("app.agent.router._client") as mock_client:
        mock_client.models.generate_content.side_effect = _model_calls(
            "get_fleet_overview", {}, answer="There are 45 players online."
        )
        response = await client.post(
            "/api/v1/agent/ask", json={"question": "How many players are online?"}
        )

    assert response.status_code == 200


def test_every_state_changing_tool_is_marked_p2():
    """
    A new write tool must not reach the registry without being listed.

    The guard is a name list, so a tool added to the registry but not to
    _P2_TOOLS would quietly be world-callable.
    """
    from app.agent import router as agent_router

    writes = {"mute_server_alerts", "unmute_server_alerts", "acknowledge_event", "relabel_event"}
    assert writes <= agent_router._P2_TOOLS
    # Every P2 name is a real registered tool, so none is a dead string.
    assert agent_router._P2_TOOLS <= set(agent_router._TOOL_BY_NAME)


# ══════════════════════════════════════════════════════
# Audit trail
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_executed_p2_action_writes_an_audit_line(client, db, admin_headers, caplog):
    """
    AGENTS.md requires an audit entry per executed P2 action.

    The line was being written to a logger the service never configured,
    so it went nowhere and a mute left no trace outside its database row.
    """
    import logging

    with caplog.at_level(logging.INFO, logger="gsh.gateway.agent"):
        with patch("app.agent.router._client") as mock_client:
            mock_client.models.generate_content.side_effect = _model_calls(
                "acknowledge_event", {"event_id": 42}, answer="Event 42 acknowledged."
            )
            response = await client.post(
                "/api/v1/agent/ask",
                json={"question": "Acknowledge event 42. Confirmed."},
                headers=admin_headers,
            )

    assert response.status_code == 200
    audit = [r.getMessage() for r in caplog.records if "[AUDIT]" in r.getMessage()]
    assert len(audit) == 1
    line = audit[0]
    # The exact shape AGENTS.md specifies, so one grep finds them all.
    assert "Action: ACKNOWLEDGE_EVENT" in line
    assert "Target: 42" in line
    assert "Source: agent" in line


@pytest.mark.asyncio
async def test_refused_p2_action_is_also_audited(client, db, caplog):
    """A denial is worth a line too -- that is the one worth noticing."""
    import logging

    with caplog.at_level(logging.WARNING, logger="gsh.gateway.agent"):
        with patch("app.agent.router._client") as mock_client:
            mock_client.models.generate_content.side_effect = _model_calls(
                "mute_server_alerts", {"server_id": "1.2.3.4:27015", "minutes": 30}
            )
            await client.post(
                "/api/v1/agent/ask", json={"question": "Mute 1.2.3.4:27015. Yes."}
            )

    audit = [r.getMessage() for r in caplog.records if "[AUDIT]" in r.getMessage()]
    assert any("DENIED" in line for line in audit)


@pytest.mark.asyncio
async def test_p1_tool_writes_no_audit_line(client, db, caplog):
    """Reads are not state changes; auditing them would bury the writes."""
    import logging

    db._fetch_result = []
    with caplog.at_level(logging.INFO, logger="gsh.gateway.agent"):
        with patch("app.agent.router._client") as mock_client:
            mock_client.models.generate_content.side_effect = _model_calls(
                "get_recent_events", {"limit": 5}, answer="No recent incidents."
            )
            await client.post("/api/v1/agent/ask", json={"question": "Any incidents?"})

    assert not [r for r in caplog.records if "[AUDIT]" in r.getMessage()]
