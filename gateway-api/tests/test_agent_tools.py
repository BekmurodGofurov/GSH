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