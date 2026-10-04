---
name: anomaly-detection-ml
description: Context and conventions for the anomaly-detection-ml microservice in the GSH (Game Server Health) project — a CS2 server monitoring pipeline using TimescaleDB, FastAPI, and Docker. Use this skill whenever working on the anomaly-detection-ml folder, debugging its Docker setup, extending its detection logic, writing its documentation, or coordinating with the root-cause-ml / backend / alerting teams on the server_metrics / server_events contract. Also use when asked about GSH project architecture, team boundaries, or this service's API.
---

# Anomaly Detection ML (GSH project)

Real-time anomaly detection microservice for CS2 game server metrics. Part of a multi-team project (GSH) — this skill covers only the `anomaly-detection-ml` folder and its `docker-compose.yml` entries.

## Project boundaries (critical — read first)

- **Only modify `anomaly-detection-ml/` and its own `docker-compose.yml` service blocks.** Other folders belong to other teams:
  - `gateway-api`, `ingestion-service` — backend team
  - `alerting-service` (Telegram bot) — alerting team
  - `root-cause-ml` — separate AI partner team
- If a bug is found in another team's service (e.g. a `shared_schemas` import error from a bad Docker build context), **report it, don't fix it directly.**
- This discipline holds even when the fix looks trivial — team ownership is the point, not code quality.

## Architecture

```
generator.py → server_metrics (TimescaleDB)
                     │
                     ▼
              bridge.py ──POST──▶ main.py (/predict/anomaly)
                     │
                     ▼
              server_events (TimescaleDB)
                     │
                     ▼
        root-cause-ml (separate service — fills root_cause)
```

Two containers, one Dockerfile/codebase:

| Container | Entrypoint | Role |
|---|---|---|
| `anomaly-detection-ml` | `uvicorn main:app` | FastAPI REST API, port 8002 |
| `anomaly-bridge` | `python bridge.py` | Background DB poller, no exposed port |

## Folder structure

```
anomaly-detection-ml/
├── main.py          # FastAPI service — detection logic
├── bridge.py         # DB polling + integration script
├── Dockerfile        # Builds BOTH main.py and bridge.py into one image
└── requirements.txt  # fastapi, uvicorn, pydantic, asyncpg, httpx
```

## Core logic (`main.py`)

- In-memory sliding window per server: last 30 readings (`WINDOW_SIZE`).
- **`MINIMUM_BASELINE_SAMPLES = 5`** — hard gate. A server with fewer than 5 recorded samples is never flagged, no matter how extreme its values. This is intentional (avoids noisy false positives on new servers), not a bug — don't "fix" it by lowering the threshold without discussing it.
- z-score per feature (`player_count`, `ping_ms`, `tick_rate`, `match_duration_s`):
  ```python
  scale = max(std, abs(mean) * 0.05, 1.0)
  z_score = abs(value - mean) / scale
  score = min(z_score / 6.0, 1.0)
  ```
- `player_count` dropping to exactly 0 (from a previously active average ≥3) is an automatic max-severity signal, independent of z-score.
- Anomaly threshold: `score >= 0.75`.
- Endpoints: `GET /health`, `POST /predict/anomaly`, `DELETE /baseline/{game}/{server_id}`.

## Integration layer (`bridge.py`)

- Polls `server_metrics` JOINed with `monitored_servers` (for `region`) every `BRIDGE_POLL_INTERVAL` seconds (default 5).
- Forwards each new row to `/predict/anomaly`.
- Classifies anomalies into `event_type` (priority order):
  1. reasons contain `"dropped to zero"` → `OFFLINE`
  2. reasons contain `"ping_ms"` → `HIGH_PING`
  3. fallback → `CRASH`
- Inserts into `server_events` with **`root_cause = 'UNKNOWN'`** — always, on purpose (see below).
- No message queue — simple poll-and-forward loop, intentional for this project's scale (23 servers).

## Architectural contract: `root_cause = 'UNKNOWN'`

This service determines **what** is anomalous, not **why**. Every row it writes to `server_events` leaves `root_cause` as `'UNKNOWN'`. Diagnosing the actual cause (network outage, hardware failure, DDoS, etc.) is the `root-cause-ml` team's job — they read these rows and `UPDATE root_cause` later. Never fill in a guessed `root_cause` value from this service; that would break the contract between the two services.

## Known Docker gotcha: build context

The `Dockerfile` for this service and sibling services (`gateway-api`, `ingestion-service`) sometimes break with `ModuleNotFoundError: No module named 'shared_schemas'`. Root cause: `build: ./service-folder` in `docker-compose.yml` restricts the Docker build context to that folder alone, so a sibling folder like `shared_schemas/` at the repo root is invisible to `COPY` instructions. Fix pattern (only apply to `anomaly-detection-ml`'s own block):
```yaml
anomaly-detection-ml:
  build:
    context: .
    dockerfile: anomaly-detection-ml/Dockerfile
```
and in the Dockerfile, `COPY shared_schemas/ ./shared_schemas/` alongside the service's own files. **Do not apply this fix to other teams' service blocks** — report the issue to them instead.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DB_URL` | — | TimescaleDB connection string |
| `ANOMALY_API_URL` | `http://localhost:8002/predict/anomaly` | Set to `http://anomaly-detection-ml:8002/predict/anomaly` inside Docker |
| `BRIDGE_POLL_INTERVAL` | `5` | Seconds between poll cycles |

## Common commands

```bash
# Build and start both containers
docker compose up -d --build anomaly-detection-ml anomaly-bridge

# Tail bridge logs (watch for 🚨 ANOMALY! / ✅ normal)
docker compose logs -f anomaly-bridge

# Verify server_events is being written
docker exec -it gsh-timescaledb psql -U postgres -d game_monitor \
  -c "SELECT time, server_id, event_type, root_cause, message FROM server_events ORDER BY time DESC LIMIT 10;"

# Check real-time lag (should be a few seconds)
docker exec -it gsh-timescaledb psql -U postgres -d game_monitor \
  -c "SELECT NOW() - MAX(time) AS lag FROM server_metrics;"
```

Swagger UI for manual testing: `localhost:8002/docs`.

## Documentation style

When writing docs for this project:
- **Technical docs / GitHub**: standard markdown — headers, tables, fenced code blocks, a Table of Contents, an explicit "Design Decisions" section explaining *why* (not just what).
- **Notion-style docs**: numbered bold headings followed by explanatory prose paragraphs, with named sub-sections like `OFFLINE:`, `HIGH_PING:`, `CRASH:` for event types — matching the house style already used elsewhere in this project's Notion space.
- Always include a short "ownership/boundaries" note distinguishing what this service owns vs. what other teams own.

## Communication note

The user communicates in both Uzbek and English and may ask for responses or docs in either language — follow whichever language the current request is in.
