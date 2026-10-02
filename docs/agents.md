# Agent Harness, Tools, and Safety

GSH includes two in-product LLM agent interfaces:
1. The **Ask** panel in the dashboard, which takes typed questions and, through the same conversation, spoken ones.
2. The **Voice Agent** that answers the spoken half in real time.

Both agent interfaces operate under strict autonomy tiers, whitelist validation, and audit logging.

Not to be confused with [AGENTS.md](../AGENTS.md): that file governs how an AI coding assistant edits this repository. This document covers the in-product agents that run for users.

## Where It Lives

The text agent runs inside `gateway-api`. The voice agent runs as a dedicated service in `voice-agent/`.

| File | What it holds |
|---|---|
| `gateway-api/app/agent/router.py` | `POST /api/v1/agent/ask`, Gemini client, tool whitelist (`_TOOL_REGISTRY`), retry and audit logging |
| `gateway-api/app/agent/tools.py` | Async tool implementations running parameterised SQL or internal service calls |
| `gateway-api/app/agent/schemas.py` | Pydantic models for request/response payloads and tool arguments |
| `gateway-api/queries.py` | Shared SQL constants used across the REST API and agent tools |
| `voice-agent/worker.py` | LiveKit voice agent using Silero VAD and Gemini Multimodal Live API (`RealtimeModel`) |
| `client/src/components/common/AskPanel.jsx` | One conversation for typing and talking; draws the charts; light and dark themes |
| `client/src/services/api.js` | Frontend API client methods (`askAgent`, `getLivekitToken`, `pollServer`, `muteServer`, `unmuteServer`, `probeAddress`, etc.) |
| `gateway-api/tests/test_agent_tools.py` | Unit and integration tests for agent tools and endpoints |
| `voice-agent/tests/test_tools.py` | The same tools as seen from the voice worker |

## Autonomy Levels

To guarantee safety and prevent unintended state changes, tools operate under two explicit tiers:

### Level P1: Autonomous (Read & Diagnostic)
May execute immediately without user confirmation:
- Read fleet-wide totals — servers online, players connected (`get_fleet_overview`)
- Show the whole fleet's status with a chart (`get_servers_overview`)
- Query server metrics and status (`get_server_summary`)
- Rank servers by stability, then latency — best or worst, any count (`get_server_ranking`)
- List the servers whose alerts are muted (`get_muted_servers`)
- Query recent incidents and anomaly history (`get_recent_events`)
- Calculate latency buckets (`get_average_latency`)
- Trigger immediate live health checks on an external game server (`poll_server_now`)
- Read cached daily analytics summaries (`generate_daily_report`)

### Level P2: Controlled (Write & State Changes)
Requires explanation, proposal, and explicit user confirmation before executing:
- Temporarily silence alerts for a server (`mute_server_alerts`)
- Lift mutes — one server, several, or all in a single call (`unmute_server_alerts`)
- Mark incident events as acknowledged (`acknowledge_event`)
- Correct or re-classify an incident root cause (`relabel_event`)
- Trigger and deliver on-demand daily reports to Telegram (`send_daily_report`)

**Confirmation is not authorization.** Every P2 tool also requires an admin credential, checked in code
(`_require_admin` in `router.py` for typed requests; `require_admin` in the voice worker, which reads the
`gsh_role` attribute the gateway signs into the room token). A non-admin who says "yes" is refused and the
attempt is audit-logged as `DENIED`. P1 stays open to everyone.

### Explain and Propose Workflow
When a user asks why a server is unstable or degrading:
1. The agent inspects recent incident logs and metric trends.
2. The agent explains the root cause diagnosis to the user.
3. The agent proposes an appropriate remediation (for example, muting alerts for 30 minutes).
4. The agent waits for explicit user confirmation before running any P2 tool.

### Audit Trail
Every executed P2 action emits an audit log line:
```
[AUDIT] Action: <ACTION> | Target: <TARGET> | Result: <RESULT> | Source: <agent>
```
Audit logs are recorded in the service logger for compliance and debugging.

## Tools Overview

| Tool | Autonomy | Arguments | Purpose |
|---|---|---|---|
| `get_fleet_overview` | P1 | none | Returns fleet totals in one row: servers, online/offline, players connected now, average ping. Used for every counting question so the model never sums a list itself. |
| `get_servers_overview` | P1 | none | Total / online / offline counts and one row per server. Backs "show me all servers": the answer is one sentence of counts plus a status chart of **every** server (offline ones marked). The model is given the counts only, not a list to recite. |
| `get_server_summary` | P1 | none | Returns status, ping, player count, region and `muted_until` for all monitored servers. |
| `get_server_ranking` | P1 | `hours` (int, 1-24, default 1), `count` (int, optional), `order` (`best`\|`worst`, default `best`) | Ranks servers on stability first (crashes, uptime, ping jitter) then average ping, with the reasons behind each placing. `shown` holds the servers asked for (default the best 5); `ranked` keeps the whole fleet. Asking for more than exist returns a `count_note` with the real total; `count` ≤ 0 returns a note and no chart. |
| `get_muted_servers` | P1 | none | Servers whose alerts are muted right now, with when each mute ends, who set it and why. Always called before `unmute_server_alerts`. |
| `get_recent_events` | P1 | `limit` (int, 1-50, default 10) | Returns latest incident events from `server_events`. |
| `get_average_latency` | P1 | `minutes` (int, 1-60), optional `server_id` (str) | Returns 1-minute bucketed ping and player averages. |
| `poll_server_now` | P1 | `server_id` (str) | Queries the server immediately via `ingestion-service` bypassing the poll loop. |
| `generate_daily_report` | P1 | none | Reads today's cached summary from `daily_reports`. |
| `mute_server_alerts` | P2 | `server_id` (str), `minutes` (int, 1-10080), optional `reason` (str) | Adds a temporary mute record in `alert_silences` to suppress Telegram alerts. |
| `unmute_server_alerts` | P2 | `server_ids` (list), `server_id` (str), or `all_servers` (bool) | Ends active silences (`muted_until = NOW()`; rows are kept). One call covers any number of servers. Servers that were not muted are reported back; if nothing was unmuted it returns 404. |
| `acknowledge_event` | P2 | `event_id` (int > 0) | Sets `is_acknowledged = TRUE` on `server_events` to stop repeated notifications. |
| `relabel_event` | P2 | `event_id` (int > 0), `root_cause` (enum) | Updates `root_cause` and sets `label_source = 'manual'`. |
| `send_daily_report` | P2 | none | Builds today's daily report and sends the formatted HTML file to Telegram. |

## Charts

A chart has to be the question. Two tools draw one, and both build it in `router._build_chart` so the typed and spoken channels draw identical bars:

| Tool | Chart |
|---|---|
| `get_server_ranking` | Exactly the servers asked for (no silent cap). The first bar — the best, or the worst when `order=worst` — is highlighted (gradient, ★). Not drawn for a single server. |
| `get_servers_overview` | Every server, online ones by ping, offline ones last in red. Title carries the counts. |

When a chart is drawn the model is told to answer in one or two sentences and not to list the servers it can already see. Counting questions (`get_fleet_overview`) get a number and no chart.

## Safety Model

1. **Whitelist Only**: The LLM is supplied only registered tools. Any unrecognised function call is rejected with HTTP 400.
2. **Schema Validation**: Arguments are strictly parsed and validated using Pydantic models before touching the database or external APIs. Invalid parameters return HTTP 422.
3. **Parameterised SQL**: Tools execute static, parameterised queries. The LLM cannot supply raw SQL or alter query structures.
4. **No Direct Secret Access**: The LLM context never receives database connection strings, credentials, or internal tokens.
5. **Admin-Gated Writes**: P2 tools are refused without an admin session or API key (HTTP 403 and an `[AUDIT] … DENIED` line), regardless of what the user confirmed.

## Configuration

| Variable | Service | Required | Purpose |
|---|---|---|---|
| `AGENT_LLM_API_KEY` | `gateway-api`, `voice-agent` | Yes | Google Gemini API key for text and voice models. |
| `AGENT_LLM_MODEL` | `gateway-api` | No | Gemini model id for typed questions. Defaults to `gemini-3.6-flash`. |
| `AGENT_VOICE_MODEL`, `AGENT_VOICE` | `voice-agent` | No | Realtime model and prebuilt voice for speech. |
| `VOICE_AGENT_NAME` | `gateway-api`, `voice-agent` | No | Which worker answers this stack's rooms; must match on both. |
| `ADMIN_API_KEY` | `gateway-api`, `voice-agent` | No | Lets the voice worker call the admin-only gateway endpoints on behalf of an admin listener. |
| `LIVEKIT_URL` | `gateway-api`, `voice-agent` | Yes (for voice) | WebSocket URL for the LiveKit WebRTC server. |
| `LIVEKIT_API_KEY` | `gateway-api`, `voice-agent` | Yes (for voice) | LiveKit server API key. |
| `LIVEKIT_API_SECRET` | `gateway-api`, `voice-agent` | Yes (for voice) | LiveKit server API secret. |
| `INGESTION_INTERNAL_URL` | `gateway-api`, `voice-agent` | No | Internal URL for ingestion service (default `http://ingestion-service:8001`). |

## Live Voice Assistant

The voice assistant allows hands-free voice operations using bidirectional WebRTC audio:
* Frontend connects to LiveKit via short-lived room tokens from `GET /api/v1/agent/livekit/token`.
* The background worker (`voice-agent/worker.py`) participates in the room with Gemini Multimodal Live API.
* Speech is automatically converted to text, processed against the toolset, and spoken back via text-to-speech.
* The voice agent can publish visual metric charts to the dashboard over LiveKit data channels while answering.
* Saying "stop" / "stop the chat" makes the agent call `end_conversation`, which sends a `stop` message; the dashboard hangs up, cutting the assistant off and releasing the microphone.

Detailed architecture and deployment steps are in [voice-agent.md](voice-agent.md).

## Testing

Run the agent tool test suite:

```bash
cd gateway-api && pytest tests/test_agent_tools.py -v
cd voice-agent && pytest -v
cd client && npm test
```

Tests cover:
* Success execution for each tool.
* Rejection of invalid inputs via Pydantic schema validation.
* Database and network connection failure handling without service crashes.
* End-to-end endpoint mocking for Gemini turns, tool selection, 503 transient backoff, and 429 quota exhaustion.
