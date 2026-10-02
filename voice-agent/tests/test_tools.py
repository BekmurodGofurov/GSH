"""Voice agent tool tests — the three categories AGENTS.md requires:

  1. Success — valid input, expected output
  2. Invalid input — a hallucinated argument is clamped, not passed on
  3. Service failure — the gateway being down produces a sentence the
     agent can say, not a stack trace and not a silent wrong answer

Several of these pin behaviour that went wrong in production: a tool that
raised NameError after its chart had already been drawn, a chart on a
question that only asked for a count, and a player total summed from a
truncated server list.
"""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import worker
from tests.conftest import gateway_fails, gateway_returns


FLEET = {
    "total_servers": 23,
    "online_servers": 23,
    "offline_servers": 0,
    "stale_servers": 0,
    "total_players": 45,
    "total_slots": 230,
    "avg_ping": 61.4,
}


def ranking(*servers, with_chart=True):
    """What the gateway's server-ranking endpoint returns, chart included."""
    rows = [
        {
            "label": s["server_name"],
            "value": s["avg_ping"],
            "status": "ONLINE",
            "note": f"{s['crash_count']} crash(es)" if s["crash_count"] else None,
            "highlight": i == 0,
        }
        for i, s in enumerate(servers)
    ]
    chart = (
        {"title": f"{len(rows)} best servers · average ping over 1h", "order": "best", "unit": "ms", "rows": rows}
        if with_chart and len(rows) > 1
        else None
    )
    return {
        "window_hours": 1,
        "chart": chart,
        "shown": list(servers),
        "ranked": list(servers),
        "excluded": [],
        "best": servers[0] if servers else None,
        "why_best": "Solid wins on stability.",
    }


def server(name, ping, crashes=0, **extra):
    row = {
        "server_id": f"{name}:27015",
        "server_name": name,
        "avg_ping": ping,
        "ping_jitter": 2.0,
        "crash_count": crashes,
        "uptime_pct": 100.0,
        "reasons": ["ping is steady", "no crashes in the last 1 hour"],
    }
    row.update(extra)
    return row


# ══════════════════════════════════════════════════════
# get_fleet_overview
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_fleet_overview_success(ctx):
    """The spoken totals are the gateway's totals, unmodified."""
    with gateway_returns(FLEET):
        result = await worker.get_fleet_overview(ctx)

    assert json.loads(result)["total_players"] == 45


@pytest.mark.asyncio
async def test_fleet_overview_draws_no_chart(ctx, room):
    """
    "How many servers are online?" is a number, not a chart.

    The old summary tool published a ten-bar latency chart on every call,
    so a one-line count arrived under a chart nobody asked for.
    """
    with gateway_returns(FLEET):
        await worker.get_fleet_overview(ctx)

    assert room.charts == []


@pytest.mark.asyncio
async def test_fleet_overview_gateway_down(ctx):
    """An outage yields a sentence to say, not an exception."""
    with gateway_fails(ConnectionError("connection refused")):
        result = await worker.get_fleet_overview(ctx)

    assert "Could not reach the monitoring API" in result


@pytest.mark.asyncio
async def test_fleet_overview_gateway_error_status(ctx):
    with gateway_returns({}, status_code=500):
        result = await worker.get_fleet_overview(ctx)

    assert "HTTP 500" in result


# ══════════════════════════════════════════════════════
# get_server_ranking
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_server_ranking_success(ctx):
    """The ranking, its reasons and its winner all reach the model."""
    payload = ranking(server("Solid", 60.0), server("Flaky", 25.0, crashes=2))
    with gateway_returns(payload):
        result = await worker.get_server_ranking(ctx, hours=1)

    data = json.loads(result)
    assert data["best"]["server_name"] == "Solid"
    assert "stability" in data["why_best"]


@pytest.mark.asyncio
async def test_server_ranking_chart_agrees_with_the_answer(ctx, room):
    """
    The bars and the spoken answer are built from one payload.

    They used to disagree: the chart was published first, then the tool
    hit a NameError on an undefined `best_ping`, and the model filled the
    gap by naming a server that was nowhere near the top of the chart.
    """
    payload = ranking(server("Solid", 60.0), server("Flaky", 25.0, crashes=2))
    with gateway_returns(payload):
        result = await worker.get_server_ranking(ctx, hours=1)

    chart = room.charts[0]
    assert [r["label"] for r in chart["rows"]] == ["Solid", "Flaky"]
    assert [r["value"] for r in chart["rows"]] == [60.0, 25.0]
    # The top bar is the server the answer names.
    assert chart["rows"][0]["label"] == json.loads(result)["best"]["server_name"]
    # Crash counts ride with the bars, so a taller "winning" bar reads correctly.
    assert chart["rows"][1]["note"] == "2 crash(es)"
    # The winner is set apart, and the chart is not part of what the model reads.
    assert chart["rows"][0]["highlight"] is True
    assert "chart" not in json.loads(result)


@pytest.mark.asyncio
async def test_server_ranking_skips_chart_for_a_single_server(ctx, room):
    """One server is not a comparison, so there is nothing to chart."""
    with gateway_returns(ranking(server("Solid", 60.0))):
        await worker.get_server_ranking(ctx, hours=1)

    assert room.charts == []


@pytest.mark.asyncio
async def test_server_ranking_clamps_a_hallucinated_window(ctx):
    """An out-of-range `hours` is clamped to what the endpoint accepts."""
    captured = {}

    payload = ranking(server("Solid", 60.0))
    with gateway_returns(payload) as mocked:
        await worker.get_server_ranking(ctx, hours=9999)
        captured["params"] = mocked.call_args.kwargs["params"]

    assert captured["params"] == {"hours": 24, "order": "best"}

    with gateway_returns(payload) as mocked:
        await worker.get_server_ranking(ctx, hours=0)
        assert mocked.call_args.kwargs["params"] == {"hours": 1, "order": "best"}


@pytest.mark.asyncio
async def test_server_ranking_passes_the_count_and_order_asked_for(ctx):
    with gateway_returns(ranking(server("Solid", 60.0), server("Flaky", 25.0))) as mocked:
        await worker.get_server_ranking(ctx, hours=1, count=3, order="worst")

    assert mocked.call_args.kwargs["params"] == {"hours": 1, "count": 3, "order": "worst"}


@pytest.mark.asyncio
async def test_server_ranking_empty_window(ctx, room):
    with gateway_returns({"window_hours": 1, "ranked": []}):
        result = await worker.get_server_ranking(ctx, hours=1)

    assert "No server reported enough health checks" in result
    assert room.charts == []


@pytest.mark.asyncio
async def test_server_ranking_gateway_down_draws_no_chart(ctx, room):
    """
    A failed lookup must leave nothing on screen.

    Publishing a chart and then failing is what let a stale chart sit
    under an answer invented from it.
    """
    with gateway_fails(ConnectionError("gateway unreachable")):
        result = await worker.get_server_ranking(ctx, hours=1)

    assert "Could not reach the monitoring API" in result
    assert room.charts == []


# ══════════════════════════════════════════════════════
# get_server_summary
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_server_summary_returns_every_server(ctx):
    """
    All servers reach the model, not the first handful.

    The old tool passed `data[:8]`, so the model answered "how many
    players are online?" by adding up eight of twenty-three servers and
    reported 19 where the fleet had 45.
    """
    servers = [
        {
            "server_id": f"10.0.0.{i}:27015",
            "server_name": f"Server {i}",
            "region": "Warsaw",
            "status": "ONLINE",
            "ping_ms": 50.0,
            "player_count": 2,
            "max_players": 10,
        }
        for i in range(23)
    ]

    with gateway_returns(servers):
        result = await worker.get_server_summary(ctx)

    parsed = json.loads(result)
    assert len(parsed) == 23
    assert sum(s["players"] for s in parsed) == 46


@pytest.mark.asyncio
async def test_server_summary_draws_no_chart(ctx, room):
    with gateway_returns([]):
        await worker.get_server_summary(ctx)

    assert room.charts == []


@pytest.mark.asyncio
async def test_server_summary_gateway_down(ctx):
    with gateway_fails(ConnectionError("down")):
        result = await worker.get_server_summary(ctx)

    assert "Could not reach the monitoring API" in result


# ══════════════════════════════════════════════════════
# get_average_latency / get_recent_events
# ══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_average_latency_success(ctx):
    with gateway_returns([{"avg_ping": 40.0}, {"avg_ping": 60.0}]):
        result = await worker.get_average_latency(ctx, minutes=10)

    assert "50.0 ms" in result


@pytest.mark.asyncio
async def test_average_latency_clamps_minutes(ctx):
    with gateway_returns([{"avg_ping": 40.0}]) as mocked:
        await worker.get_average_latency(ctx, minutes=9999)
        assert mocked.call_args.kwargs["params"] == {"minutes": 60}


@pytest.mark.asyncio
async def test_average_latency_no_samples(ctx):
    with gateway_returns([]):
        result = await worker.get_average_latency(ctx, minutes=10)

    assert "No latency metrics" in result


@pytest.mark.asyncio
async def test_recent_events_success(ctx):
    with gateway_returns([{"id": 1, "event_type": "OFFLINE"}]):
        result = await worker.get_recent_events(ctx, limit=5)

    assert json.loads(result)[0]["event_type"] == "OFFLINE"


@pytest.mark.asyncio
async def test_recent_events_gateway_down(ctx):
    with gateway_fails(ConnectionError("down")):
        result = await worker.get_recent_events(ctx, limit=5)

    assert "Could not reach the monitoring API" in result


# ══════════════════════════════════════════════════════
# The agent itself
# ══════════════════════════════════════════════════════

def test_every_tool_returns_a_string_on_a_good_response(ctx):
    """
    Regression guard for the crash that started this.

    `get_server_performance_chart` referenced an undefined `best_ping`,
    so it raised NameError on the happy path -- after publishing its
    chart. Nothing exercised it, so it shipped. This walks every
    no-argument read tool against a healthy gateway.
    """
    import asyncio

    tools = [worker.get_fleet_overview, worker.get_server_summary]
    for tool in tools:
        with gateway_returns([]):
            result = asyncio.run(tool(ctx))
        assert isinstance(result, str), f"{tool.info.name} did not return a string"


def test_voice_and_model_are_pinned():
    """
    The assistant's voice must not change between builds.

    Left unset, the plugin picks its own current default realtime model,
    which moves with the plugin version and changes how the assistant
    sounds.
    """
    assert worker.VOICE_MODEL
    assert worker.VOICE_NAME
    assert "NOT_GIVEN" not in str(worker.VOICE_MODEL)


def test_worker_registers_under_an_agent_name():
    """
    Explicit dispatch keeps other stacks' workers out of these rooms.

    An unnamed worker joins a shared pool, so a dev stack or a laptop
    could answer a production call -- in its own voice, on its own build.
    """
    assert worker.AGENT_NAME


def test_agent_exposes_the_expected_tools():
    agent = worker.build_agent(None)
    names = {t.info.name for t in agent.tools}
    assert "get_fleet_overview" in names
    assert "get_server_ranking" in names
    # The tool that crashed is gone, replaced by the ranking tool.
    assert "get_server_performance_chart" not in names


# ══════════════════════════════════════════════════════
# P2 authorization in voice
#
# The worker holds a service-wide admin key, so before this check any
# visitor who opened voice chat could mute a server just by asking and
# saying yes. The key proves the worker is the worker; it says nothing
# about who is speaking.
# ══════════════════════════════════════════════════════

class AdminCtx:
    """A room joined by someone who signed in on the admin page."""

    def __init__(self, room=None):
        self.userdata = worker.WorkerCtx(room=room, is_admin=True)


@pytest.mark.asyncio
async def test_viewer_cannot_mute(ctx):
    """A non-admin is refused before any request leaves the worker."""
    with gateway_returns({"status": "muted"}) as mocked:
        result = await worker.mute_server_alerts(ctx, server_id="1.2.3.4:27015", minutes=30)

    assert "admin login" in result
    assert mocked.call_count == 0


@pytest.mark.asyncio
async def test_viewer_cannot_acknowledge_or_send_reports(ctx):
    assert "admin login" in await worker.acknowledge_event(ctx, event_id=5)
    assert "admin login" in await worker.send_daily_report(ctx)


@pytest.mark.asyncio
async def test_admin_can_mute():
    """The same request goes through for an admin."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"muted_until": "2026-10-01T12:00:00+00:00"}

    with patch("httpx.AsyncClient.post", AsyncMock(return_value=response)):
        result = await worker.mute_server_alerts(
            AdminCtx(), server_id="1.2.3.4:27015", minutes=30
        )

    assert "muted for 30 minutes" in result


@pytest.mark.asyncio
async def test_viewer_cannot_unmute(ctx):
    with gateway_returns({"status": "unmuted"}) as mocked:
        result = await worker.unmute_server_alerts(ctx, all_servers=True)

    assert "admin login" in result
    assert mocked.call_count == 0


@pytest.mark.asyncio
async def test_admin_unmutes_several_servers_in_one_request():
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"unmuted": ["a:1", "b:1", "c:1"]}
    post = AsyncMock(return_value=response)

    with patch("httpx.AsyncClient.post", post):
        result = await worker.unmute_server_alerts(AdminCtx(), server_ids=["a:1", "b:1", "c:1"])

    assert post.call_count == 1
    assert "3 server(s)" in result


@pytest.mark.asyncio
async def test_admin_can_unmute_everything():
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"unmuted": ["a:1", "b:1"]}
    post = AsyncMock(return_value=response)

    with patch("httpx.AsyncClient.post", post):
        await worker.unmute_server_alerts(AdminCtx(), all_servers=True)

    assert post.call_args.kwargs["json"]["all_servers"] is True


@pytest.mark.asyncio
async def test_unmute_needs_a_target():
    with patch("httpx.AsyncClient.post", AsyncMock()) as post:
        result = await worker.unmute_server_alerts(AdminCtx())

    assert "which servers" in result
    assert post.call_count == 0


@pytest.mark.asyncio
async def test_unmute_with_nothing_muted():
    response = MagicMock()
    response.status_code = 404

    with patch("httpx.AsyncClient.post", AsyncMock(return_value=response)):
        result = await worker.unmute_server_alerts(AdminCtx(), all_servers=True)

    assert "None of those" in result


@pytest.mark.asyncio
async def test_anyone_can_ask_which_servers_are_muted(ctx):
    """Reading mutes is P1: it needs no login, and the model needs it to unmute."""
    payload = {"muted_count": 1, "muted_servers": [{"server_id": "a:1", "server_name": "Seven"}]}
    with gateway_returns(payload):
        result = await worker.get_muted_servers(ctx)

    assert json.loads(result)["muted_servers"][0]["server_name"] == "Seven"


@pytest.mark.asyncio
async def test_viewers_keep_full_read_access(ctx):
    """P1 is unaffected: anyone may ask what the servers are doing."""
    with gateway_returns(FLEET):
        result = await worker.get_fleet_overview(ctx)

    assert json.loads(result)["total_players"] == 45


def test_role_defaults_to_viewer():
    """
    An unexpected or missing token attribute means viewer, not admin.

    Failing open here would hand every visitor the admin key's reach.
    """
    assert worker.WorkerCtx().is_admin is False
    assert worker.require_admin(FakeCtxNoRole(), "MUTE_ALERTS") is not None


class FakeCtxNoRole:
    """A context whose userdata predates the is_admin field."""

    class _U:
        pass

    userdata = _U()
