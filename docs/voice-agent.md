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
                                (RealtimeModel / Gemini 2.0)         (Gateway, Ingestion, TG)
```

### Components

1. **Dashboard (`client/src/components/common/AskPanel.jsx`)**:
   - Manages WebRTC audio publishing and subscription via `@livekit/components-react`.
   - Live subtitles streamed through `registerTextStreamHandler('lk.transcription')`.
   - In-chat SVG bar charts received through LiveKit reliable data channels.
   - Visual audio indicators (animated mic button, `BarVisualizer`, speaking ring pulses).
   - Inactivity auto-disconnect after 60 seconds of silence.

2. **Token Generator (`gateway-api/main.py`)**:
   - Route `GET /api/v1/agent/livekit/token` validates session and issues signed JWTs with room join permissions for room `gsh-agent`.

3. **Voice Worker (`voice-agent/worker.py`)**:
   - Built on `livekit.agents` framework.
   - Pre-warms Silero VAD (Voice Activity Detection) for low-latency speech segment detection.
   - Connects to Google Gemini Multimodal Live API using `RealtimeModel(voice="Puck", language="en-US")`.
   - Dispatches tools and streams synthesized audio back to the room.

## Autonomy Levels and Safety in Voice

The voice assistant enforces the same two-tier autonomy model as the text agent:

### Level P1 (Autonomous Read / Diagnostic)
Tools execute immediately during the conversation:
- `get_server_summary`: Reads status, ping, and player counts; publishes a live latency SVG bar chart.
- `get_server_performance_chart`: Ranks servers by latency and provides downtime trend estimates; publishes ranking chart.
- `get_recent_events`: Reads latest incident anomalies and root causes.
- `poll_server_now`: Triggers on-demand health check for an IP:port via ingestion-service.

### Level P2 (Controlled Write / State Changes)
Tools require explicit verbal explanation and confirmation before execution:
- `mute_server_alerts`: Silences Telegram notifications for a server for N minutes.
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

## Data Channel Visual Charts

In addition to voice output, the worker sends structured JSON payloads over the LiveKit data channel:
```json
{
  "type": "chart",
  "chartType": "bar",
  "title": "Server Latency (ms)",
  "rows": [
    { "label": "Warsaw #1", "value": 38.2, "status": "ONLINE" },
    { "label": "Frankfurt #2", "value": 45.0, "status": "ONLINE" }
  ]
}
```
The frontend listens via `useDataChannel`, decodes the payload, and renders a lightweight SVG bar chart directly in the transcript feed.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `LIVEKIT_URL` | Yes | WebRTC WebSocket URL (e.g. `wss://livekit.example.com` or local `ws://livekit:7880`). |
| `LIVEKIT_API_KEY` | Yes | LiveKit API Key for authentication and token signing. |
| `LIVEKIT_API_SECRET` | Yes | LiveKit API Secret for authentication and token signing. |
| `AGENT_LLM_API_KEY` | Yes | Google Gemini API key supporting Multimodal Live API. |
| `AGENT_LLM_MODEL` | No | Model ID (defaults to `gemini-2.0-flash-exp` in container). |
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
```
