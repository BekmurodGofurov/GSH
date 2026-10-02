# Voice Agent Architecture and Live Chat

The GSH Voice Agent enables hands-free voice operations over WebRTC. Users can talk to the agent in English, ask for server health diagnostics, hear spoken responses, view dynamically rendered charts, and trigger controlled actions such as server muting.

## Architecture

```
Dashboard (AskPanel) ──1. GET /api/v1/agent/livekit/token──► gateway-api
        │
        │ 2. Connect WebRTC (audio + data channel)
        ▼
   LiveKit Server ◄──3. WebRTC audio + tool calls──► voice-agent (worker.py)
                                                              │
                                            ┌─────────────────┴─────────────────┐
                                            ▼                                   ▼
                                 Gemini Multimodal Live API            Internal Services
                                (RealtimeModel)         (Gateway, Ingestion, TG)
```

### Components

1. **Dashboard (`client/src/components/common/AskPanel.jsx`)**:
   - One conversation, typed and spoken. There is no mode to choose: the composer carries a text
     box and a microphone, and answers from either land in the same thread in the order they happened.
   - Manages WebRTC audio publishing and subscription via `@livekit/components-react`.
   - Live subtitles streamed through `registerTextStreamHandler('lk.transcription')`.
   - In-chat SVG bar charts, received over LiveKit data channels in voice and on the `chart`
     field of `POST /api/v1/agent/ask` in text.
   - Visual audio indicators (mic button, `BarVisualizer`, speaking ring pulses).
   - Inactivity auto-disconnect after 60 seconds, counting `thinking` and typing as activity so a
     slow tool call cannot close the session mid-answer.

2. **Token Generator (`gateway-api/main.py`)**:
   - Route `GET /api/v1/agent/livekit/token` validates the session and issues a signed JWT for a
     fresh per-session room (`gsh-agent-<random>`), so two listeners never share one conversation.
   - The token carries a `RoomConfiguration` naming `VOICE_AGENT_NAME`, which is what dispatches
     this stack's worker and only this stack's worker.

3. **Voice Worker (`voice-agent/worker.py`)**:
   - Built on `livekit.agents` framework.
   - Pre-warms Silero VAD (Voice Activity Detection) for low-latency speech segment detection.
   - Connects to Google Gemini Multimodal Live API using `RealtimeModel(model=..., voice=..., language="en-US")`.
     The model and voice come from `AGENT_VOICE_MODEL` / `AGENT_VOICE` and are never left to the plugin's
     own default, which moves with the plugin version and changes how the assistant sounds.
   - Registers under `VOICE_AGENT_NAME` and is dispatched explicitly, so only this stack's worker joins
     this stack's rooms. Dev and production must not share the name.
   - Reads its data through `gateway-api` over HTTP; it holds no queries of its own.
   - Dispatches tools and streams synthesized audio back to the room.

## Autonomy Levels and Safety in Voice

The voice assistant enforces the same two-tier autonomy model as the text agent:

### Level P1 (Autonomous Read / Diagnostic)
Tools execute immediately during the conversation:
- `get_servers_overview`: "Show me all servers" — says the total / online / offline counts and publishes a status chart of every server.
- `get_muted_servers`: Lists servers whose alerts are muted; called before unmuting.
- `end_conversation`: "Stop" / "stop the chat" — publishes a `stop` message and the dashboard hangs up.
- `get_fleet_overview`: Reads fleet totals — servers online, players connected now, average ping. No chart: a
  count is answered with a number.
- `get_server_summary`: Reads status, ping, and player counts for every monitored server.
- `get_server_ranking`: Ranks servers on stability first (crashes, uptime, ping jitter) then average ping, with
  `count` (default best 5) and `order` (`best`/`worst`). Publishes a chart of exactly the servers asked for. The
  gateway builds the chart (`chart` in the endpoint's response), so the bars and the spoken numbers cannot disagree.
- `get_recent_events`: Reads latest incident anomalies and root causes.
- `poll_server_now`: Triggers on-demand health check for an IP:port via ingestion-service.

### Level P2 (Controlled Write / State Changes)
Tools require explicit verbal explanation and confirmation before execution:
- `mute_server_alerts`: Silences Telegram notifications for a server for N minutes.
- `unmute_server_alerts`: Lifts mutes — `server_ids` for several, `all_servers` for everything, in one call.

The worker holds a service-wide admin key, so confirmation alone is not enough: `require_admin` checks the
`gsh_role` attribute the gateway signs into the room token, and a viewer is refused before any request is sent.
- `acknowledge_event`: Acknowledges an incident to halt repetitive alert firings.
- `send_daily_report`: Builds today's summary and posts the report to Telegram.

### Explain and Propose Workflow
When asked why a server is failing or unstable:
1. The voice agent inspects recent events and metrics.
2. The voice agent verbally diagnoses the root cause.
3. The voice agent proposes a specific remediation (e.g. "Server 188.212.101.109 had 3 latency spikes. Would you like me to mute alerts for 30 minutes?").
4. The voice agent calls the P2 tool only after the user says "yes", "confirm", or "proceed".

### Audit Logging
Every P2 action executed by the voice agent emits a log:
```
[AUDIT] Action: <ACTION> | Target: <TARGET> | Result: <RESULT> | Source: voice-agent
```

## Data Channel Messages

In addition to voice output, the worker sends structured JSON over the LiveKit data channel. A chart:
```json
{
  "type": "chart",
  "chartType": "bar",
  "title": "5 best servers · average ping over 1h",
  "order": "best",
  "unit": "ms",
  "rows": [
    { "label": "Warsaw #1", "value": 38.2, "status": "ONLINE", "highlight": true },
    { "label": "Frankfurt #2", "value": 45.0, "status": "ONLINE", "highlight": false }
  ]
}
```
`order` is `best`, `worst` or `overview` (whole-fleet status; offline rows have `status: "OFFLINE"`). The frontend listens via `useDataChannel` and renders an SVG bar chart in the transcript feed.

And the hang-up signal, sent by `end_conversation`:
```json
{ "type": "stop" }
```
On receiving it the dashboard disconnects from the room, which cuts the assistant off mid-sentence and releases the microphone. The panel also has an **End** button, and the room is created with `stopMicTrackOnMute` so muting the mic stops the track (and the browser's microphone indicator) instead of leaving it open.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `LIVEKIT_URL` | Yes | WebRTC WebSocket URL (e.g. `wss://livekit.example.com` or local `ws://livekit:7880`). |
| `LIVEKIT_API_KEY` | Yes | LiveKit API Key for authentication and token signing. |
| `LIVEKIT_API_SECRET` | Yes | LiveKit API Secret for authentication and token signing. |
| `AGENT_LLM_API_KEY` | Yes | Google Gemini API key supporting Multimodal Live API. |
| `AGENT_VOICE_MODEL` | No | Realtime model id (default `gemini-3.8-live`); must support `bidiGenerateContent`. |
| `AGENT_VOICE` | No | Prebuilt voice name (default `Puck`). |
| `VOICE_AGENT_NAME` | No | Dispatch name; must match `gateway-api`. Defaults to `<COMPOSE_PROJECT_NAME>-voice`. |
| `ADMIN_API_KEY` | For P2 | Lets the worker call admin-only gateway endpoints for an admin listener. |
| `GATEWAY_INTERNAL_URL` | No | URL to gateway API (default: `http://gateway-api:8000`). |
| `INGESTION_INTERNAL_URL` | No | URL to ingestion service (default: `http://ingestion-service:8001`). |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram bot token for on-demand report delivery. |
| `TELEGRAM_CHAT_ID` | Optional | Target Telegram chat ID for on-demand reports. |

## Running and Deployment

The voice agent is packaged in `voice-agent/Dockerfile` and integrated into `docker-compose.yml`:

```bash
docker compose up -d voice-agent
```

To run standalone in development:
```bash
cd voice-agent
pip install -r requirements.txt
python worker.py dev
pytest -v      # the tool tests, no LiveKit needed
```
