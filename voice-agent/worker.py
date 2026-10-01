import asyncio
import os
import logging
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import httpx
from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    Agent,
    AgentSession,
    function_tool,
    RunContext,
)
from livekit.plugins import silero
from livekit.plugins.google.realtime import RealtimeModel

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gsh.voice_agent")

GATEWAY_URL = os.environ.get("GATEWAY_INTERNAL_URL", "http://gateway-api:8000")
INGESTION_URL = os.environ.get("INGESTION_INTERNAL_URL", "http://ingestion-service:8001")
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

GEMINI_API_KEY = os.environ.get("AGENT_LLM_API_KEY", "")
if not GEMINI_API_KEY:
    raise ValueError("AGENT_LLM_API_KEY environment variable is not set.")

# Both of these are named rather than left to the plugin's default.
#
# The voice was picking itself: with no model id the plugin falls back to
# whatever its current default is, which today is a dated native-audio
# *preview* snapshot. That default moves with the plugin version, and the
# requirements file did not pin one -- so two rebuilds a week apart could
# run two different realtime models, and a native-audio model renders the
# same prebuilt voice name with a noticeably different character. Naming
# the model here, next to a pinned plugin, is what makes the assistant
# sound the same tomorrow as it does today.
#
# Must be a model that advertises bidiGenerateContent. Check the current
# list before changing it:
#   curl "https://generativelanguage.googleapis.com/v1beta/models?key=$AGENT_LLM_API_KEY"
VOICE_MODEL = os.environ.get("AGENT_VOICE_MODEL", "gemini-3.8-live")
VOICE_NAME = os.environ.get("AGENT_VOICE", "Puck")

# Only the worker registered under this name is dispatched into a room,
# and the gateway stamps the same name into every token it issues. Two
# stacks (dev and production) must not share it -- see the matching
# comment on _VOICE_AGENT_NAME in gateway-api/main.py.
#
# livekit-agents logs a deprecation warning for passing this to
# WorkerOptions and points at livekit.toml instead. It stays here because
# the name has to differ per environment and comes from the environment;
# a checked-in toml file would hard-code one name for every stack. The
# pinned version in requirements.txt is what keeps that warning from
# turning into a breakage -- whoever lifts the pin needs to generate the
# toml per environment first.
AGENT_NAME = os.environ.get("VOICE_AGENT_NAME", "gsh-voice")

# The behaviour rules here mirror _SYSTEM_INSTRUCTION in
# gateway-api/app/agent/router.py, which drives the typed channel. Keep
# them in step: a question should get the same answer spoken or typed.
SYSTEM_PROMPT = (
    "You are the GSH (Game Server Health) voice assistant monitoring Counter-Strike 2 servers. "
    "You only understand and speak English. Always respond concisely in English (1-3 sentences). "
    "\n\nPicking a tool:"
    "\n- Counting questions ('how many servers are online?', 'how many players are playing "
    "right now?') -> get_fleet_overview. Read out its totals exactly; never add up a server "
    "list yourself."
    "\n- 'Which server is best / fastest / most stable?', comparing servers, or a request for "
    "a chart -> get_server_ranking."
    "\n- Questions about particular servers -> get_server_summary."
    "\nSpeech recognition mishears 'servers' as 'sellers', 'cellars' or 'serves'. Treat those "
    "as 'servers'. If a question is still unclear, ask what the user meant instead of guessing "
    "a tool."
    "\n\nAnswering about the best server:"
    "\nThe ranking tool sorts on stability first (crashes, uptime, ping jitter) and then average "
    "ping, so the best server is not always the one with the lowest ping. Name the winner and "
    "give the reasons the tool returned -- how many times it dropped out, how steady its ping "
    "is -- and say so explicitly when it wins despite a higher ping."
    "\n\nAutonomy Levels:"
    "\n- P1 (Read / Diagnose / Immediate): Run automatically without prior confirmation:"
    " get_fleet_overview, get_server_ranking, get_server_summary, get_average_latency,"
    " get_recent_events, poll_server_now."
    "\n- P2 (Write / State Change / Controlled): Requires explanation and explicit user "
    "confirmation before executing: mute_server_alerts, acknowledge_event, send_daily_report."
    "\n\nExplain and Propose Workflow:"
    "\nWhen asked 'why is server X unstable?' or about server issues, check get_recent_events and metrics. "
    "Diagnose the cause (e.g. latency spike, player drop, crash) and PROPOSE a P2 action "
    "(e.g. 'Server 188.212.101.109 had 3 latency spikes. Would you like me to mute alerts for 30 minutes?'). "
    "Wait for the user to say 'yes', 'confirm', or 'proceed' before calling the P2 tool."
    "\nP2 tools also require the listener to be signed in as an admin, which is checked by "
    "the server, not by you. If a P2 tool answers that an admin login is needed, say so "
    "plainly and offer the diagnosis instead -- do not retry it and do not claim the action "
    "was done."
    "\n\nIf a tool reports an error or returns no data, say the data is unavailable. Never fill "
    "the gap with numbers from an earlier answer, and never invent a server, a ping or a player "
    "count."
)


@dataclass
class WorkerCtx:
    room: Optional[object] = None
    # Whether the person in this room signed in on the admin page. Read
    # from the signed token attribute the gateway stamps in, never from
    # anything the speaker claims -- "I'm the admin" is not a credential.
    is_admin: bool = False


def require_admin(context: RunContext[WorkerCtx], action: str) -> str | None:
    """Return a refusal sentence for a P2 action by a non-admin, else None.

    The worker carries a service-wide admin key, so without this check any
    visitor who opened voice chat could mute a server simply by asking and
    confirming. The key is for proving the worker is the worker; it is not
    a stand-in for the listener being an admin.
    """
    if getattr(context.userdata, "is_admin", False):
        return None
    audit_log(action, "-", "DENIED (not an admin)")
    return (
        f"I can't {action.lower().replace('_', ' ')} from this session. That changes "
        "server state, so it needs an admin login on the dashboard first."
    )


def audit_log(action: str, target: str, result: str) -> None:
    """Log an audit entry for P2 state-changing actions."""
    logger.info("[AUDIT] Action: %s | Target: %s | Result: %s | Source: voice-agent", action, target, result)


async def gateway_get(path: str, params: dict | None = None) -> tuple[dict | list | None, str | None]:
    """GET a gateway endpoint, returning (data, error_message).

    The agent's data tools live in gateway-api and are reached over HTTP:
    this service must not import another service's code, and duplicating
    the queries here is what let the spoken answers drift away from the
    typed ones in the first place.
    """
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.get(f"{GATEWAY_URL}{path}", params=params)
        except Exception as e:
            return None, f"Could not reach the monitoring API: {e}"
    if resp.status_code != 200:
        return None, f"The monitoring API returned HTTP {resp.status_code}."
    try:
        return resp.json(), None
    except ValueError:
        return None, "The monitoring API returned a response I could not read."


async def publish_chart(room, chart_type: str, title: str, rows: list[dict], unit: str = "ms") -> None:
    if not room or not getattr(room, "local_participant", None):
        logger.warning("publish_chart: Room or local_participant not ready")
        return
    try:
        payload = json.dumps({
            "type": "chart",
            "chartType": chart_type,
            "title": title,
            "unit": unit,
            "rows": rows,
        }).encode()
        await room.local_participant.publish_data(payload, reliable=True)
        logger.info("PUBLISHED CHART: title='%s' rows=%d", title, len(rows))
    except Exception as e:
        logger.warning("Failed to publish chart data: %s", e)


# How many bars fit in the panel before the labels collide.
CHART_MAX_ROWS = 10


# ─── P1 Tools (Autonomous / Read) ─────────────────────────────────────────────

@function_tool(
    description=(
        "Returns fleet-wide totals: how many servers are monitored, how many are online "
        "or offline, how many players are connected right now across all of them, and the "
        "average ping. Use this for every counting question."
    )
)
async def get_fleet_overview(context: RunContext[WorkerCtx]) -> str:
    data, err = await gateway_get("/api/v1/agent/tools/fleet-overview")
    if err:
        return err
    # No chart here on purpose: "how many servers are online?" wants a
    # number, and a ten-bar latency chart above a one-line answer buries it.
    return json.dumps(data, ensure_ascii=False)


@function_tool(
    description=(
        "Ranks servers over a time window by stability first (crashes, uptime, ping jitter) "
        "and then average ping, and explains why the top one wins. Use this for 'which server "
        "is best', for comparing servers, and when the user asks for a performance chart. "
        "Do not answer 'best server' from get_server_summary -- that holds a single momentary "
        "ping sample per server."
    )
)
async def get_server_ranking(context: RunContext[WorkerCtx], hours: int = 1) -> str:
    hours = max(1, min(int(hours or 1), 24))
    data, err = await gateway_get("/api/v1/agent/tools/server-ranking", {"hours": hours})
    if err:
        return err
    if not isinstance(data, dict):
        return "The ranking data was not in the expected form."

    ranked = data.get("ranked") or []
    if not ranked:
        return "No server reported enough health checks in that window to rank."

    # A ranking is a comparison, so a chart earns its place here -- and
    # the bars are the same averages the spoken answer is built from, so
    # the two cannot disagree.
    if len(ranked) > 1:
        rows = [
            {
                "label": (r.get("server_name") or r.get("server_id", ""))[:28],
                "value": r.get("avg_ping") or 0,
                "status": "ONLINE",
                "note": f"{r.get('crash_count') or 0} crash" if r.get("crash_count") else None,
            }
            for r in ranked[:CHART_MAX_ROWS]
        ]
        window = f"{hours}h" if hours != 1 else "1h"
        await publish_chart(
            context.userdata.room,
            "bar",
            f"Average ping over {window} — best first",
            rows,
        )

    return json.dumps(data, ensure_ascii=False)


@function_tool(
    description="Returns current status, player count, latency, and region of each monitored server."
)
async def get_server_summary(context: RunContext[WorkerCtx]) -> str:
    data, err = await gateway_get("/api/v1/servers")
    if err:
        return err
    if not isinstance(data, list):
        return "The server list was not in the expected form."

    # Every server, not a slice of the list. The model used to receive the
    # first eight rows and answer counting questions by adding those up,
    # which is how a 23-server fleet was reported as having 19 players.
    # Only the fields an answer needs travel, so the full list still fits.
    compact = [
        {
            "server_id": s.get("server_id"),
            "name": s.get("server_name"),
            "region": s.get("region"),
            "status": s.get("status"),
            "ping_ms": s.get("ping_ms"),
            "players": s.get("player_count"),
            "max_players": s.get("max_players"),
        }
        for s in data
    ]
    return json.dumps(compact, ensure_ascii=False)


@function_tool(
    description="Returns average ping latency across servers over recent minutes."
)
async def get_average_latency(context: RunContext[WorkerCtx], minutes: int = 10) -> str:
    minutes = max(1, min(int(minutes or 10), 60))
    data, err = await gateway_get("/api/v1/analytics/ping-buckets", {"minutes": minutes})
    if err:
        return err
    if not data:
        return "No latency metrics recorded in this time window."
    pings = [row["avg_ping"] for row in data if row.get("avg_ping")]
    if not pings:
        return "No server answered a health check in this time window."
    overall_avg = round(sum(float(p) for p in pings) / len(pings), 1)
    return f"The average latency across monitored servers over the last {minutes} minutes is {overall_avg} ms."


@function_tool(
    description="Returns recent incident events, anomalies, crashes, and latency spikes across all servers."
)
async def get_recent_events(context: RunContext[WorkerCtx], limit: int = 5) -> str:
    limit = max(1, min(int(limit or 5), 50))
    data, err = await gateway_get("/api/v1/events", {"limit": limit})
    if err:
        return err
    if not data:
        return "No recent incidents recorded."
    return json.dumps(data, ensure_ascii=False)


@function_tool(
    description="Triggers an immediate live health check for a specific server (e.g. '188.212.101.109:27015') and returns its fresh ping and player count."
)
async def poll_server_now(context: RunContext[WorkerCtx], server_id: str) -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{INGESTION_URL}/api/v1/servers/{server_id}/poll")
        except Exception as e:
            return f"Error checking server: {e}"
    if resp.status_code == 200:
        data = resp.json()
        audit_log("POLL_NOW", server_id, f"ping={data.get('ping_ms')} players={data.get('player_count')}")
        return json.dumps(data, ensure_ascii=False)
    return f"Server check returned HTTP {resp.status_code}: {resp.text}"


# ─── P2 Tools (Write / State Changes / Require Confirmation) ───────────────────

@function_tool(
    description="[P2 action - requires user confirmation] Silences Telegram alerts for a server for the given minutes (default 30)."
)
async def mute_server_alerts(context: RunContext[WorkerCtx], server_id: str, minutes: int = 30, reason: str = "Voice assistant mute") -> str:
    refusal = require_admin(context, "MUTE_ALERTS")
    if refusal:
        return refusal
    headers = {"X-API-Key": ADMIN_API_KEY} if ADMIN_API_KEY else {}
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.post(
                f"{GATEWAY_URL}/api/v1/servers/{server_id}/mute",
                json={"minutes": minutes, "reason": reason},
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                audit_log("MUTE_ALERTS", server_id, f"Muted for {minutes}m until {data.get('muted_until')}")
                return f"Server {server_id} alerts muted for {minutes} minutes."
            return f"Failed to mute server: HTTP {resp.status_code} {resp.text}"
        except Exception as e:
            return f"Error muting alerts: {e}"


@function_tool(
    description="[P2 action - requires user confirmation] Marks an incident event as acknowledged so repeated alerts stop."
)
async def acknowledge_event(context: RunContext[WorkerCtx], event_id: int) -> str:
    refusal = require_admin(context, "ACKNOWLEDGE_EVENT")
    if refusal:
        return refusal
    headers = {"X-API-Key": ADMIN_API_KEY} if ADMIN_API_KEY else {}
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.post(
                f"{GATEWAY_URL}/api/v1/events/{event_id}/acknowledge",
                headers=headers,
            )
            if resp.status_code == 200:
                audit_log("ACKNOWLEDGE_EVENT", str(event_id), "Acknowledged")
                return f"Event {event_id} has been acknowledged."
            return f"Failed to acknowledge event: HTTP {resp.status_code} {resp.text}"
        except Exception as e:
            return f"Error acknowledging event: {e}"


@function_tool(
    description="[P2 action - requires user confirmation] Generates today's daily health summary report and sends it to Telegram."
)
async def send_daily_report(context: RunContext[WorkerCtx]) -> str:
    refusal = require_admin(context, "DAILY_REPORT")
    if refusal:
        return refusal
    headers = {"X-API-Key": ADMIN_API_KEY} if ADMIN_API_KEY else {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{GATEWAY_URL}/api/v1/reports/daily", headers=headers)
            report_text = ""
            if resp.status_code == 200:
                report_data = resp.json()
                report_text = report_data.get("report_text", "Daily summary report.")
            else:
                report_text = "Daily server report: all services monitored."

            telegram_status = "not configured"
            if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                try:
                    tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                    tg_resp = await client.post(
                        tg_url,
                        json={"chat_id": TELEGRAM_CHAT_ID, "text": f"📋 <b>GSH Daily Report (On-Demand)</b>\n\n{report_text[:3500]}", "parse_mode": "HTML"},
                        timeout=8.0,
                    )
                    telegram_status = "sent" if tg_resp.status_code == 200 else f"telegram HTTP {tg_resp.status_code}"
                except Exception as tg_err:
                    telegram_status = f"failed: {tg_err}"

            audit_log("DAILY_REPORT", "Telegram", telegram_status)
            return f"Today's report prepared ({telegram_status}). Summary: {report_text[:150]}"
        except Exception as e:
            return f"Error generating report: {e}"


# ─── Worker Setup ─────────────────────────────────────────────────────────────

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


def build_agent(vad) -> Agent:
    return Agent(
        instructions=SYSTEM_PROMPT,
        vad=vad,
        tools=[
            get_fleet_overview,
            get_server_ranking,
            get_server_summary,
            get_average_latency,
            get_recent_events,
            poll_server_now,
            mute_server_alerts,
            acknowledge_event,
            send_daily_report,
        ],
        llm=RealtimeModel(
            api_key=GEMINI_API_KEY,
            model=VOICE_MODEL,
            voice=VOICE_NAME,
            language="en-US",
        ),
    )


async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Who joined, according to the token the gateway signed. A viewer can
    # ask the agent anything (P1); only an admin can change state (P2).
    # Defaults to viewer, so a token without the attribute -- an older
    # client, or anything unexpected -- is treated as the lower privilege.
    participant = await ctx.wait_for_participant()
    is_admin = (participant.attributes or {}).get("gsh_role") == "admin"

    logger.info(
        "Agent '%s' joined room %s as %s with voice '%s' on model '%s'",
        AGENT_NAME, ctx.room.name, "ADMIN" if is_admin else "viewer", VOICE_NAME, VOICE_MODEL,
    )

    worker_ctx = WorkerCtx(room=ctx.room, is_admin=is_admin)
    session = AgentSession(userdata=worker_ctx)
    await session.start(build_agent(ctx.proc.userdata["vad"]), room=ctx.room)

    session.generate_reply(
        instructions="Greet the user in 1 short sentence as GSH voice assistant and say you are ready to check servers."
    )

    await asyncio.sleep(float("inf"))


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name=AGENT_NAME,
        )
    )
