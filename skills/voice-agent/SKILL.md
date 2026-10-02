---
name: gsh-voice-agent
description: >
  Use this skill whenever working on the voice-agent service, adding voice tools,
  modifying LiveKit agent configurations, tuning Silero VAD, or updating
  data channel chart communication.
---

# GSH Voice Agent Developer Rules

The `voice-agent` service provides real-time bidirectional voice conversation
for server monitoring. It connects to a LiveKit WebRTC room, processes incoming
audio with Silero VAD, streams conversations with Gemini Multimodal Live API,
dispatches function tools, and sends SVG chart events over LiveKit data channels.

## Service Structure

```
voice-agent/
  Dockerfile       (container build for voice agent worker)
  requirements.txt (livekit-agents, livekit-plugins-google, silero, httpx)
  worker.py        (worker lifecycle, VAD prewarming, tools, agent session)
```

## Worker Lifecycle

1. **Pre-warm**: Load Silero VAD into process memory before room connections arrive to minimise initial voice latency:
   ```python
   def prewarm(proc: JobProcess):
       proc.userdata["vad"] = silero.VAD.load()
   ```
2. **Entrypoint**: Runs upon room creation (`ctx: JobContext`):
   - Connects audio subscription (`AutoSubscribe.AUDIO_ONLY`).
   - Instantiates `Agent` with `SYSTEM_PROMPT`, tools list, and `RealtimeModel`.
   - Starts `AgentSession` and triggers initial spoken greeting.

## Adding Voice Tools

Voice tools are registered using the `@function_tool` decorator from `livekit.agents`.

### Tool Declaration Rules
- Include clear descriptions in the decorator. The Gemini Multimodal Live API uses this to decide when to call the tool.
- Accept `context: RunContext[WorkerCtx]` as the first parameter to access room state and data channels.
- Keep execution fast. Use a strict timeout (e.g. 8.0s) on HTTP requests (`httpx.AsyncClient`).
- Return concise text (1-3 sentences) suitable for text-to-speech synthesis.

```python
@function_tool(description="Returns current status and latency of monitored servers.")
async def get_server_summary(context: RunContext[WorkerCtx]) -> str:
    ...
```

### Autonomy Tiers in Voice

Tools must be marked as P1 or P2:

1. **Level P1 (Autonomous Read / Diagnostic)**:
   - Tool executes immediately upon user request (e.g. `get_server_summary`, `get_servers_overview`, `get_muted_servers`, `get_recent_events`, `poll_server_now`).
   - Read tools reach the data through `GET /api/v1/agent/tools/*` on the gateway; never re-implement a query in the worker. Charts are built by the gateway and only published by the worker.
2. **Level P2 (Controlled Write / State Changes)**:
   - Tool description must note `[P2 action - requires user confirmation]`.
   - Call `require_admin(context, "ACTION")` first and return its refusal for a non-admin listener; confirmation is not authorization.
   - System prompt instructs the model to explain the diagnosis, propose the action, and wait for confirmation ("yes", "confirm", "proceed") before invoking the tool.
   - The tool implementation must emit an audit log entry:
     ```python
     logger.info("[AUDIT] Action: %s | Target: %s | Result: %s | Source: voice-agent", action, target, result)
     ```

## Streaming Visual Charts via Data Channels

When a voice tool gathers tabular or ranking data, it can broadcast a visual chart to the dashboard over the room data channel:

```python
await publish_chart(
    room=context.userdata.room,
    chart_type="bar",
    title="Server Latency (ms)",
    rows=[
        {"label": "Server #1", "value": 35.5, "status": "ONLINE"},
        {"label": "Server #2", "value": 78.1, "status": "ONLINE"}
    ]
)
```

### Data Channel Contract
The dashboard (`AskPanel.jsx`) expects:
- Channel: reliable data channel (`room.local_participant.publish_data(payload, reliable=True)`).
- JSON format:
  ```json
  {
    "type": "chart",
    "chartType": "bar",
    "title": "...",
    "rows": [{ "label": "...", "value": 12.3, "status": "ONLINE" }]
  }
  ```

## Development and Verification

Run the worker locally against a running LiveKit server:
```bash
cd voice-agent
python worker.py dev
```

Key checks:
- Verify microphone audio is detected by Silero VAD without cutoffs.
- Verify speech synthesis returns natural English responses.
- Verify P2 tools require affirmative confirmation before execution.
- Check stdout for audit lines (`[AUDIT] Action: ...`).
