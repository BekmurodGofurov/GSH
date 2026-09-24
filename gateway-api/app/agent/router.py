import asyncio
import json
import os
from fastapi import APIRouter, HTTPException, Depends
from fastapi.encoders import jsonable_encoder
from google import genai
from google.genai import types as genai_types
from google.genai import errors as genai_errors

from app.agent import schemas, tools

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
        "name": "get_server_summary",
        "description": (
            "Returns the current status of every monitored CS2 game server, "
            "including online/offline status, ping in ms, player count, and region."
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


def _get_db_pool():
    """Import the live db_pool from main at request time (not at module load time)."""
    import main as gw
    if gw.db_pool is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    return gw.db_pool


@router.post("/api/v1/agent/ask", response_model=schemas.AskResponse)
async def agent_ask(body: schemas.AskRequest):
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

    system_instruction = (
        "You are GSH (Game Server Health) assistant. "
        "You have access to live data from a Counter-Strike 2 server monitoring system. "
        "Always use the available tools to get real data before answering. "
        "Be concise and factual. If a tool returns no data, say so clearly."
    )

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
            call_args = {}

        # Run the actual tool function
        try:
            tool_result = await tool_fn(db_pool, **call_args)
        except HTTPException:
            raise  # re-raise clean HTTP errors (e.g. 404 event not found)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Tool '{tool_name}' failed: {e}")

        tool_used = tool_name

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

    return schemas.AskResponse(answer=answer, tool_used=tool_used)