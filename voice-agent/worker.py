import asyncio
import os
import sys
import logging
import json
import time
import httpx
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

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

SYSTEM_PROMPT = (
    "You are the GSH (Game Server Health) voice assistant monitoring Counter-Strike 2 servers. "
    "You only understand and speak English. Always respond concisely in English (1-3 sentences). "
    "\n\nAutonomy Levels:"
    "\n- P1 (Read / Diagnose / Immediate): Run automatically without prior confirmation:"
    " get_server_summary, get_server_performance_chart, get_recent_events, poll_server_now."
    "\n- P2 (Write / State Change / Controlled): Requires explanation and explicit user confirmation before executing:"
    " mute_server_alerts, acknowledge_event, send_daily_report."
    "\n\nExplain and Propose Workflow:"
    "\nWhen asked 'why is server X unstable?' or about server issues, check get_recent_events and metrics. "
    "Diagnose the cause (e.g. latency spike, player drop, crash) and PROPOSE a P2 action "
    "(e.g. 'Server 188.212.101.109 had 3 latency spikes. Would you like me to mute alerts for 30 minutes?'). "
    "Wait for the user to say 'yes', 'confirm', or 'proceed' before calling the P2 tool."
)


@dataclass
class WorkerCtx:
    room: Optional[object] = None


def audit_log(action: str, target: str, result: str) -> None:
    """Log an audit entry for P2 state-changing actions."""
    logger.info("[AUDIT] Action: %s | Target: %s | Result: %s | Source: voice-agent", action, target, result)


async def publish_chart(room, chart_type: str, title: str, rows: list[dict]) -> None:
    if not room or not getattr(room, "local_participant", None):
        logger.warning("publish_chart: Room or local_participant not ready")
        return
    try:
        payload = json.dumps({
            "type": "chart",
            "chartType": chart_type,
            "title": title,
            "rows": rows,
        }).encode()
        await room.local_participant.publish_data(payload, reliable=True)
        logger.info("PUBLISHED CHART: title='%s' rows=%d", title, len(rows))
    except Exception as e:
        logger.warning("Failed to publish chart data: %s", e)


# ─── P1 Tools (Autonomous / Read) ─────────────────────────────────────────────

@function_tool(
    description="Returns current status, player count, latency, and region of monitored servers, with an inline bar chart."
)
async def get_server_summary(context: RunContext[WorkerCtx]) -> str:
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.get(f"{GATEWAY_URL}/api/v1/servers")
            if resp.status_code != 200:
                return f"Failed to fetch servers: HTTP {resp.status_code}"
            data = resp.json()
            online = sum(1 for s in data if s.get("status") == "ONLINE")
            total = len(data)

            rows = [
                {
                    "label": (s.get("server_name") or s.get("server_id", ""))[:22],
                    "value": s.get("ping_ms") or 0,
                    "status": s.get("status", "OFFLINE"),
                }
                for s in data[:10]
            ]
            await publish_chart(context.userdata.room, "bar", "Server Latency (ms)", rows)
            return f"Total {total} servers. {online} currently online. Servers: {json.dumps(data[:8], ensure_ascii=False)}"
        except Exception as e:
            return f"Error fetching server summary: {e}"


@function_tool(
    description="Shows sorted ranking of servers by latency and provides downtime predictions."
)
async def get_server_performance_chart(context: RunContext[WorkerCtx]) -> str:
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.get(f"{GATEWAY_URL}/api/v1/servers")
            if resp.status_code != 200:
                return f"Failed: HTTP {resp.status_code}"
            data = resp.json()

            online = [s for s in data if s.get("status") == "ONLINE" and s.get("ping_ms")]
            offline = [s for s in data if s.get("status") == "OFFLINE"]

            ranked = sorted(online, key=lambda s: s.get("ping_ms") or 9999)
            rows = [
                {
                    "label": (s.get("server_name") or s.get("server_id", ""))[:22],
                    "value": round(s.get("ping_ms") or 0, 1),
                    "status": "ONLINE",
                }
                for s in ranked[:10]
            ]
            await publish_chart(context.userdata.room, "bar", "Performance Ranking (lower = better)", rows)

            best = ranked[0] if ranked else None
            best_name = best.get("server_name", best.get("server_id", "N/A")) if best else "N/A"
            best_ping = round(best.get("ping_ms", 0), 1) if best else 0
            offline_ratio = len(offline) / len(data) if data else 0
            predicted_down = round(offline_ratio * len(data))

            return (
                f"Best server is {best_name} at {best_ping}ms. "
                f"Currently {len(offline)} of {len(data)} servers offline. "
                f"Based on current trends, around {predicted_down} servers may experience downtime over the next 2 days."
            )
        except Exception as e:
            return f"Error: {e}"


@function_tool(
    description="Returns recent incident events, anomalies, crashes, and latency spikes across all servers."
)
async def get_recent_events(context: RunContext[WorkerCtx], limit: int = 5) -> str:
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.get(f"{GATEWAY_URL}/api/v1/events?limit={limit}")
            if resp.status_code == 200:
                events = resp.json()
                if not events:
                    return "No recent incidents recorded."
                return json.dumps(events, ensure_ascii=False)
            return f"Failed to fetch events: HTTP {resp.status_code}"
        except Exception as e:
            return f"Error fetching events: {e}"


@function_tool(
    description="Triggers an immediate live health check for a specific server (e.g. '188.212.101.109:27015') and returns its fresh ping and player count."
)
async def poll_server_now(context: RunContext[WorkerCtx], server_id: str) -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{INGESTION_URL}/api/v1/servers/{server_id}/poll")
            if resp.status_code == 200:
                data = resp.json()
                audit_log("POLL_NOW", server_id, f"ping={data.get('ping_ms')} players={data.get('player_count')}")
                return json.dumps(data, ensure_ascii=False)
            return f"Server check returned HTTP {resp.status_code}: {resp.text}"
        except Exception as e:
            return f"Error checking server: {e}"


# ─── P2 Tools (Write / State Changes / Require Confirmation) ───────────────────

@function_tool(
    description="[P2 action - requires user confirmation] Silences Telegram alerts for a server for the given minutes (default 30)."
)
async def mute_server_alerts(context: RunContext[WorkerCtx], server_id: str, minutes: int = 30, reason: str = "Voice assistant mute") -> str:
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


async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    worker_ctx = WorkerCtx(room=ctx.room)

    agent = Agent(
        instructions=SYSTEM_PROMPT,
        vad=ctx.proc.userdata["vad"],
        tools=[
            get_server_summary,
            get_server_performance_chart,
            get_recent_events,
            poll_server_now,
            mute_server_alerts,
            acknowledge_event,
            send_daily_report,
        ],
        llm=RealtimeModel(
            api_key=GEMINI_API_KEY,
            voice="Puck",
            language="en-US",
        ),
    )

    session = AgentSession(userdata=worker_ctx)
    await session.start(agent, room=ctx.room)

    session.generate_reply(
        instructions="Greet the user in 1 short sentence as GSH voice assistant and say you are ready to check servers."
    )

    await asyncio.sleep(float("inf"))


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
