import asyncio
import json
import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.encoders import jsonable_encoder
from google import genai
from google.genai import types as genai_types
from google.genai import errors as genai_errors

from app.agent import schemas, tools

logger = logging.getLogger("gsh.gateway.agent")

# Startup validation
# Fail loudly at import time — same pattern as DB_URL in main.py.
# If the key is missing, the service won't start and the error is obvious.

_LLM_API_KEY = os.environ.get("AGENT_LLM_API_KEY", "")
if not _LLM_API_KEY:
    raise ValueError(
        "AGENT_LLM_API_KEY environment variable is not set. "
        "Add it to your .env file. Get a key at https://aistudio.google.com/app/apikey"
    )

_client = genai.Client(api_key=_LLM_API_KEY)

# Model id, overridable from .env. Google retires model ids on its own
# schedule -- when that happens the API answers 404 and names the
# replacement, which should be a one-line .env change, not a redeploy.
_MODEL = os.environ.get("AGENT_LLM_MODEL") or "gemini-3.6-flash"

# Tool whitelist
# The LLM only knows about tools in this list.
# Functions in tools.py that are NOT listed here are invisible to the model.
# Adding a function to tools.py without adding it here does nothing.

_TOOL_REGISTRY = [
    {
        "name": "get_fleet_overview",
        "description": (
            "Returns fleet-wide totals in a single row: how many servers are "
            "monitored, how many are online or offline, how many players are "
            "connected right now across all of them, and the average ping. "
            "Use this for every counting question ('how many servers are "
            "online?', 'how many players are playing right now?') instead of "
            "listing servers and adding them up."
        ),
        "fn": tools.get_fleet_overview,
        "schema": None,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_server_ranking",
        "description": (
            "Ranks servers over a time window by stability first (crashes, "
            "uptime, ping jitter) and then average ping, and explains why the "
            "top one wins. Use this for 'which server is best / fastest / most "
            "stable', for comparing servers, and whenever the user wants a "
            "chart of server performance. Do NOT answer 'best server' from "
            "get_server_summary: that only holds one momentary ping sample per "
            "server, which changes between sweeps."
        ),
        "fn": tools.get_server_ranking,
        "schema": schemas.RankingQuery,
        "parameters": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "Window to judge the servers over, in hours (1–24). Default is 1.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_server_summary",
        "description": (
            "Returns one row per monitored CS2 server with its current "
            "online/offline status, latest ping, player count, and region. "
            "Use it when the user asks about specific servers or wants the "
            "list itself -- not for fleet totals (use get_fleet_overview) and "
            "not for picking the best server (use get_server_ranking)."
        ),
        "fn": tools.get_server_summary,
        "schema": None,  # no input arguments
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_recent_events",
        "description": (
            "Returns the most recent incident events (anomalies, crashes, outages). "
            "Use this to answer questions about what happened recently."
        ),
        "fn": tools.get_recent_events,
        "schema": schemas.EventQuery,
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of events to return (1–50). Default is 10.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_average_latency",
        "description": (
            "Returns average ping (latency) and player count per server over the last N minutes. "
            "Optionally filter by a specific server_id."
        ),
        "fn": tools.get_average_latency,
        "schema": schemas.LatencyQuery,
        "parameters": {
            "type": "object",
            "properties": {
                "minutes": {
                    "type": "integer",
                    "description": "Time window in minutes (1–60). Default is 10.",
                },
                "server_id": {
                    "type": "string",
                    "description": "Optional. Filter results to a specific server ID (e.g. '188.212.101.109:27015').",
                },
            },
            "required": [],
        },
    },
    {
        "name": "relabel_event",
        "description": (
            "Re-labels an incident's root cause. Use this when the user asks to correct "
            "or update the diagnosis of a specific event. "
            "Allowed root causes: SERVER_CRASH, HIGH_LATENCY, DDOS_ATTACK, "
            "REGIONAL_OUTAGE, PLAYER_DROP, MAINTENANCE."
        ),
        "fn": tools.relabel_event,
        "schema": schemas.RelabelRequest,
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "integer",
                    "description": "The numeric ID of the event to relabel.",
                },
                "root_cause": {
                    "type": "string",
                    "description": (
                        "The new root cause label. Must be one of: "
                        "SERVER_CRASH, HIGH_LATENCY, DDOS_ATTACK, "
                        "REGIONAL_OUTAGE, PLAYER_DROP, MAINTENANCE."
                    ),
                },
            },
            "required": ["event_id", "root_cause"],
        },
    },
    {
        "name": "acknowledge_event",
        "description": (
            "Acknowledges an incident so the alerting service stops sending repeated "
            "Telegram notifications about it. Use this when the user says they have seen "
            "an alert or are investigating it."
        ),
        "fn": tools.acknowledge_event,
        "schema": schemas.AcknowledgeRequest,
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "integer",
                    "description": "The numeric ID of the incident event to acknowledge.",
                },
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "mute_server_alerts",
        "description": (
            "Temporarily silences Telegram alerts for a specific server for the given number "
            "of minutes. Useful during planned maintenance or known outages."
        ),
        "fn": tools.mute_server_alerts,
        "schema": schemas.MuteAlertsRequest,
        "parameters": {
            "type": "object",
            "properties": {
                "server_id": {
                    "type": "string",
                    "description": "The server ID to mute (e.g. '188.212.101.109:27015').",
                },
                "minutes": {
                    "type": "integer",
                    "description": "How many minutes to silence alerts (1–10080).",
                },
                "reason": {
                    "type": "string",
                    "description": "Optional reason for the mute (e.g. 'Scheduled maintenance').",
                },
            },
            "required": ["server_id", "minutes"],
        },
    },
    {
        "name": "poll_server_now",
        "description": (
            "Immediately triggers a fresh health check for a specific server, bypassing "
            "the background polling interval. Returns live ping, player count, and status."
        ),
        "fn": tools.poll_server_now,
        "schema": schemas.PollRequest,
        "parameters": {
            "type": "object",
            "properties": {
                "server_id": {
                    "type": "string",
                    "description": "The server ID to re-check (e.g. '188.212.101.109:27015').",
                },
            },
            "required": ["server_id"],
        },
    },
    {
        "name": "generate_daily_report",
        "description": (
            "Returns today's cached daily summary report including uptime, anomaly counts, "
            "and server performance. If the report hasn't been generated yet, explains how "
            "to trigger it via Telegram."
        ),
        "fn": tools.generate_daily_report,
        "schema": schemas.DailyReportRequest,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

# Build the genai FunctionDeclaration list once at startup.
# This is what gets sent to Gemini so it knows what tools are available.
_GEMINI_TOOLS = [
    genai_types.Tool(
        function_declarations=[
            genai_types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=t["parameters"],
            )
            for t in _TOOL_REGISTRY
        ]
    )
]

# Index by name for fast lookup when the LLM requests a specific tool
_TOOL_BY_NAME = {t["name"]: t for t in _TOOL_REGISTRY}

# FastAPI router

router = APIRouter()


# 503 means the shared model is momentarily overloaded -- it clears on its
# own, so it is worth retrying before bothering the user with an error.
#
# 429 is deliberately NOT retried: on this API it usually means the quota
# for the period is spent, and every retry burns more of what is left
# without any chance of succeeding. It surfaces straight away instead, so
# the message names the real problem.
_RETRYABLE_STATUS = (503,)
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.0


async def _generate(**kwargs):
    """Call the LLM: retry transient failures, surface the rest as 502.

    The SDK call is synchronous, so it runs in a worker thread -- calling
    it inline would block the event loop for the whole round trip and
    stall every other request, the dashboard's WebSocket included.

    Letting google.genai raise through the handler would produce a bare
    500 that Starlette renders outside the CORS middleware, so the browser
    reports a misleading "No Access-Control-Allow-Origin" error and the
    real cause (retired model id, bad key, quota) never reaches the
    dashboard.
    """
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return await asyncio.to_thread(
                _client.models.generate_content, model=_MODEL, **kwargs
            )
        except genai_errors.APIError as e:
            is_last = attempt == _MAX_ATTEMPTS - 1
            if getattr(e, "code", None) not in _RETRYABLE_STATUS or is_last:
                raise HTTPException(
                    status_code=502,
                    detail=f"LLM provider error for model '{_MODEL}': {e}",
                )
            # Exponential backoff: 1s, then 2s.
            await asyncio.sleep(_RETRY_BACKOFF_SECONDS * (2 ** attempt))


# The behaviour rules below are mirrored in voice-agent/worker.py, which
# runs the same agent over the voice channel. Keep the two in step: the
# whole point of routing both through the same gateway tools is that a
# question gets the same answer whether it was typed or spoken.
_SYSTEM_INSTRUCTION = (
    "You are GSH (Game Server Health) assistant monitoring Counter-Strike 2 game servers. "
    "Always use the available tools to get real data before answering. "
    "\n\nPicking a tool:"
    "\n- Counting questions ('how many servers are online?', 'how many players are "
    "playing right now?') -> get_fleet_overview. Report its totals verbatim; never "
    "add up a server list yourself."
    "\n- 'Which server is best / fastest / most stable?', comparing servers, or any "
    "request for a performance chart -> get_server_ranking."
    "\n- Questions about particular servers or the list itself -> get_server_summary."
    "\n\nAnswering about the best server:"
    "\nThe ranking tool sorts on stability first (crashes, uptime, ping jitter) and then "
    "average ping, so the best server is not always the one with the lowest ping. Name the "
    "winner and give the reasons the tool returned -- how many times it dropped out, how "
    "steady its ping is -- and say so explicitly when it wins despite a higher ping."
    "\n\nAutonomy Levels:"
    "\n- P1 (Read / Diagnose / Live Poll): Execute immediately without waiting for confirmation: "
    "get_fleet_overview, get_server_ranking, get_server_summary, get_recent_events, "
    "get_average_latency, poll_server_now, generate_daily_report."
    "\n- P2 (Write / State Changes): Require user confirmation before executing: "
    "mute_server_alerts, acknowledge_event, relabel_event."
    "\n\nExplain and Propose Workflow:"
    "\nWhen asked 'why is server X unstable?' or about server problems, fetch recent events and metrics. "
    "Explain the diagnosis clearly, and PROPOSE the appropriate P2 action (e.g. muting alerts for 30 minutes). "
    "Only call P2 tools if the user explicitly commanded it or confirmed your proposal."
    "\nP2 tools additionally require an admin login, which the server enforces. If one is "
    "refused for that reason, say the action needs an admin sign-in -- never report it as done."
    "\n\nBe concise and factual. If a tool returns no data, say so clearly. If a tool "
    "returns an error, say the data is unavailable -- never fill the gap from an earlier "
    "answer or from numbers you saw before. "
    "Never speculate, guess, or invent server metrics; strictly base answers on tool outputs."
)

# How many bars an inline chart carries. Past ten the labels collide and
# the chart stops being readable in the panel.
_CHART_MAX_ROWS = 10


def _build_chart(tool_name: str, tool_result) -> schemas.ChartPayload | None:
    """Build the inline chart for a tool result, or None when none belongs.

    Only the ranking tool produces one. Charts used to be attached to
    every server lookup, so asking "how many servers are online?" drew a
    ten-bar latency chart above a one-line answer. A chart now appears
    only where the question was itself a comparison.
    """
    if tool_name != "get_server_ranking" or not isinstance(tool_result, dict):
        return None

    ranked = tool_result.get("ranked") or []
    if not ranked:
        return None

    rows = []
    for row in ranked[:_CHART_MAX_ROWS]:
        crashes = row.get("crash_count") or 0
        rows.append(
            schemas.ChartRow(
                label=row.get("server_name") or row.get("server_id", ""),
                value=row.get("avg_ping") or 0.0,
                status="ONLINE",
                # The bar is average ping; the crash count is what the
                # ranking actually turned on, so it travels with the bar.
                note=f"{crashes} crash(es)" if crashes else None,
            )
        )

    hours = tool_result.get("window_hours", 1)
    window = f"{hours}h" if hours != 1 else "1h"
    return schemas.ChartPayload(
        title=f"Average ping over {window} — best first",
        unit="ms",
        rows=rows,
    )


def _get_db_pool():
    """Import the live db_pool from main at request time (not at module load time)."""
    import main as gw
    if gw.db_pool is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    return gw.db_pool


# The tools that change state. Asking the model nicely is not what keeps
# these safe -- a user who says "yes, do it" gets past the prompt every
# time. The check below is what actually holds.
_P2_TOOLS = frozenset({"mute_server_alerts", "acknowledge_event", "relabel_event"})


async def _require_admin(request, tool_name: str) -> None:
    """Refuse a P2 tool unless this request carries an admin credential.

    POST /agent/ask is open, because asking what the servers are doing
    should not need a login. Muting an alert is a different thing, and it
    used to run on the same open endpoint: the typed channel wrote
    straight to the database while the spoken one went through an
    authenticated endpoint, so the same sentence was refused by voice and
    carried out by text.

    main.verify_api_key is reused rather than reimplemented so there is
    one definition of "admin" -- it covers both the X-API-Key header and
    the dashboard's session cookie, including expiry.
    """
    import main as gw

    try:
        await gw.verify_api_key(request, request.headers.get("X-API-Key"))
    except HTTPException:
        logger.warning(
            "[AUDIT] Action: %s | Target: - | Result: DENIED (not an admin) | Source: agent",
            tool_name.upper(),
        )
        raise HTTPException(
            status_code=403,
            detail=(
                f"'{tool_name}' changes server state, so it needs an admin login. "
                "Sign in on the admin page and ask again."
            ),
        )


# Read-only views of the agent's own data tools.
#
# The voice agent runs in its own service and so cannot import these
# functions (AGENTS.md: services talk over HTTP, never by importing each
# other). It used to carry its own copy of the logic, which is how the
# spoken answer came to report a different player count from the typed
# one. Both channels now read the same numbers through these endpoints.

@router.get("/api/v1/agent/tools/fleet-overview")
async def fleet_overview():
    """Fleet-wide totals: servers, online/offline, players, average ping."""
    return await tools.get_fleet_overview(_get_db_pool())


@router.get("/api/v1/agent/tools/server-ranking")
async def server_ranking(hours: int = Query(1, ge=1, le=24)):
    """Servers ranked by stability then latency, with the reasons behind it."""
    return await tools.get_server_ranking(_get_db_pool(), hours=hours)


@router.post("/api/v1/agent/ask", response_model=schemas.AskResponse)
async def agent_ask(body: schemas.AskRequest, request: Request):
    """
    Ask the agent a question about live server data, or ask it to perform
    a safe action (like re-labelling an incident).

    Flow:
      1. Send question + tool list to Gemini.
      2. If Gemini requests a tool → validate args → run whitelisted function.
      3. Send tool result back to Gemini for a grounded answer.
      4. Return the final answer to the client.
    """
    db_pool = _get_db_pool()

    system_instruction = _SYSTEM_INSTRUCTION

    # Turn 1: Send question to Gemini with tool list
    response = await _generate(
        contents=body.question,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=_GEMINI_TOOLS,
            temperature=0.1,  # low temperature = more factual, less creative
        ),
    )

    # Check if Gemini wants to call a tool
    tool_used = None
    chart = None
    candidate = response.candidates[0]
    function_call = None

    for part in candidate.content.parts:
        if part.function_call:
            function_call = part.function_call
            break

    if function_call:
        tool_name = function_call.name
        raw_args = dict(function_call.args) if function_call.args else {}

        # SECURITY: Only execute tools that are on the whitelist.
        # If Gemini somehow requests a tool not in the registry, refuse.
        if tool_name not in _TOOL_BY_NAME:
            raise HTTPException(
                status_code=400,
                detail=f"Model requested unknown tool: '{tool_name}'. This is not allowed.",
            )

        # P2 tools change state, so the caller has to be an admin. This
        # runs before the arguments are even validated: an unauthorised
        # request should not reach the database at all.
        if tool_name in _P2_TOOLS:
            await _require_admin(request, tool_name)

        tool_entry = _TOOL_BY_NAME[tool_name]
        tool_fn = tool_entry["fn"]
        tool_schema = tool_entry["schema"]

        # Validate the LLM's arguments through Pydantic before touching the DB.
        # If the model hallucinated a bad value, this raises ValidationError → 422.
        if tool_schema and raw_args:
            try:
                validated = tool_schema(**raw_args)
                call_args = validated.model_dump(exclude_none=True)
            except Exception as e:
                raise HTTPException(
                    status_code=422,
                    detail=f"Tool '{tool_name}' received invalid arguments from model: {e}",
                )
        else:
            # No Pydantic schema — pass raw args directly (already validated by type
            # in the FunctionDeclaration sent to Gemini).
            call_args = raw_args

        # Run the actual tool function
        try:
            tool_result = await tool_fn(db_pool, **call_args)
            if tool_name in _P2_TOOLS:
                # The format AGENTS.md specifies, so one grep finds every
                # state change across the gateway and the voice worker.
                logger.info(
                    "[AUDIT] Action: %s | Target: %s | Result: %s | Source: agent",
                    tool_name.upper(),
                    call_args.get("server_id") or call_args.get("event_id") or "-",
                    jsonable_encoder(tool_result),
                )
        except HTTPException:
            raise  # re-raise clean HTTP errors (e.g. 404 event not found)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Tool '{tool_name}' failed: {e}")

        tool_used = tool_name
        chart = _build_chart(tool_name, tool_result)

        # Turn 2: Ask for a grounded answer with the tool output inlined as
        # text. Replaying the function_call/function_response pair instead
        # would be the textbook round trip, but Gemini now rejects a
        # functionCall part echoed back without the thought_signature it was
        # issued with -- and that signature is not available on the parsed
        # response. Plain text keeps this working across model revisions.
        #
        # No tools are offered on this turn: the data is already in hand and
        # a second tool request would just be discarded.
        tool_payload = json.dumps(jsonable_encoder(tool_result), ensure_ascii=False)
        final_response = await _generate(
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[
                        genai_types.Part(
                            text=(
                                f"{body.question}\n\n"
                                f"Data returned by the `{tool_name}` tool "
                                f"(JSON):\n{tool_payload}"
                            )
                        )
                    ],
                ),
            ],
            config=genai_types.GenerateContentConfig(
                system_instruction=(
                    system_instruction
                    + " Answer using only the tool data provided in the message."
                ),
                temperature=0.1,
            ),
        )
        answer = final_response.text

    else:
        # Gemini answered directly without needing a tool (e.g. a general question)
        answer = response.text

    return schemas.AskResponse(answer=answer, tool_used=tool_used, chart=chart)