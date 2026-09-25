# Anomaly Detection ML

Real-time anomaly detection microservice for the **GSH (Game Server Health)** platform. It monitors CS2 game server metrics (ping, player count, etc.) and flags abnormal behavior such as latency spikes and servers going offline.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Folder Structure](#folder-structure)
- [How It Works](#how-it-works)
- [API Reference](#api-reference)
- [Event Classification](#event-classification)
- [Configuration](#configuration)
- [Running Locally](#running-locally)
- [Design Decisions](#design-decisions)
- [Ownership & Boundaries](#ownership--boundaries)

---

## Overview

This service is one component of the larger GSH pipeline. It does not collect metrics itself — it consumes metrics already written to TimescaleDB by the ingestion service, scores them for anomalies, and writes flagged incidents back to the database for downstream consumers (dashboards, alerting, root-cause analysis).

**Pipeline position:**

```
generator.py → server_metrics (TimescaleDB)
                     │
                     ▼
              bridge.py  ──POST──▶  main.py (/predict/anomaly)
                     │
                     ▼
              server_events (TimescaleDB)
                     │
                     ▼
        root-cause-ml (separate service, fills root_cause)
```

## Architecture

The service ships as a single Docker image, run as **two separate containers** with different entrypoints:

| Container | Entrypoint | Role |
|---|---|---|
| `anomaly-detection-ml` | `uvicorn main:app` | FastAPI REST API, port `8002` |
| `anomaly-bridge` | `python bridge.py` | Background poller, no exposed port |

Both containers are built from the same `Dockerfile` and share the same codebase, keeping the API and the polling logic independently deployable and restartable.

## Folder Structure

```
anomaly-detection-ml/
├── main.py            # FastAPI service — anomaly detection logic
├── bridge.py           # DB polling + integration script
├── Dockerfile          # Builds both main.py and bridge.py into one image
└── requirements.txt    # fastapi, uvicorn, pydantic, asyncpg, httpx
```

## How It Works

### `main.py` — Detection Engine

- In-memory sliding window per server: last **30 readings** (`WINDOW_SIZE`).
- Requires **≥5 baseline samples** (`MINIMUM_BASELINE_SAMPLES`) before it will flag anything — prevents false positives on freshly-seen servers.
- Computes a z-score per feature (`player_count`, `ping_ms`, `tick_rate`, `match_duration_s`) against that server's own recent history:

  ```python
  scale = max(std, abs(mean) * 0.05, 1.0)
  z_score = abs(value - mean) / scale
  score = min(z_score / 6.0, 1.0)
  ```

- A `player_count` drop to exactly `0` (from a previously active average ≥3) is treated as an automatic maximum-severity signal, independent of the z-score calculation.
- Anomaly threshold: `score >= 0.75`.

### `bridge.py` — Integration Layer

Runs an infinite polling loop (default interval: 5s, `BRIDGE_POLL_INTERVAL`):

1. `SELECT` new rows from `server_metrics` (joined with `monitored_servers` for `region`) since the last poll.
2. For each row, `POST` to `main.py`'s `/predict/anomaly`.
3. If `is_anomaly: true`, classify the event and `INSERT` into `server_events`.
4. Log the result to stdout (`✅ normal` / `🚨 ANOMALY!`).

No queue or message broker is used — polling is intentionally simple for this stage of the project.

## API Reference

### `GET /health`

```json
{ "status": "ok", "service": "anomaly-detection-ml" }
```

### `POST /predict/anomaly`

**Request:**
```json
{
  "metric": {
    "id": "51.77.47.223:27015",
    "game": "cs2",
    "region": "eu-west",
    "player_count": 20,
    "max_players": 20,
    "ping_ms": 900,
    "timestamp": "2026-08-28T09:25:00.000Z"
  }
}
```

**Response:**
```json
{
  "server_id": "51.77.47.223:27015",
  "anomaly_score": 1.0,
  "is_anomaly": true,
  "reasons": ["ping_ms deviates strongly from its recent baseline"],
  "baseline_samples": 6
}
```

### `DELETE /baseline/{game}/{server_id}`

Clears the in-memory history for a given server — useful for testing or resetting a server's baseline after a known configuration change.

Full interactive docs available at `localhost:8002/docs` (Swagger UI).

## Event Classification

`bridge.py` maps detected anomalies to a `server_events.event_type` using this priority order:

| Priority | Condition (in `reasons`) | `event_type` |
|---|---|---|
| 1 | `"dropped to zero"` | `OFFLINE` |
| 2 | `"ping_ms"` | `HIGH_PING` |
| 3 | *(fallback)* | `CRASH` |

Every inserted row sets `root_cause = 'UNKNOWN'` — see [Design Decisions](#design-decisions).

## Configuration

Environment variables (set via `docker-compose.yml`):

| Variable | Default | Description |
|---|---|---|
| `DB_URL` | — | TimescaleDB connection string |
| `ANOMALY_API_URL` | `http://localhost:8002/predict/anomaly` | Where `bridge.py` sends requests (set to the container name in Docker, e.g. `http://anomaly-detection-ml:8002/predict/anomaly`) |
| `BRIDGE_POLL_INTERVAL` | `5` | Seconds between polling cycles |

## Running Locally

```bash
# Build and start both containers
docker compose up -d --build anomaly-detection-ml anomaly-bridge

# Tail bridge logs
docker compose logs -f anomaly-bridge

# Verify server_events is being written
docker compose exec timescaledb psql -U postgres -d game_monitor \
  -c "SELECT time, server_id, event_type, root_cause, message FROM server_events ORDER BY time DESC LIMIT 10;"
```

## Design Decisions

**`root_cause` is left as `'UNKNOWN'` on purpose.**
This service determines *what* is anomalous, not *why*. Diagnosing the underlying cause (network outage, hardware failure, DDoS, etc.) is explicitly the responsibility of the `root-cause-ml` team, which reads `server_events` rows and updates `root_cause` afterward via a separate `UPDATE`. This keeps detection and diagnosis as two independently deployable, loosely-coupled stages — `anomaly-detection-ml` never needs to know how root-cause classification works, and vice versa.

**`MINIMUM_BASELINE_SAMPLES = 5` is a hard gate.**
A server with fewer than 5 recorded samples will never be flagged, regardless of how extreme its metrics look. This is intentional: with too little history, "deviation from baseline" is not statistically meaningful, and flagging early would produce noisy false positives on newly-added servers.

**Polling, not a message queue.**
`bridge.py` uses a simple poll-and-forward loop rather than a pub/sub or streaming setup. Given the current data volume (23 servers, low-frequency metrics) this keeps the integration layer trivial to reason about and debug.

## Ownership & Boundaries

This documentation and codebase covers only the `anomaly-detection-ml` folder and its corresponding entries in the root `docker-compose.yml`. Other GSH components are owned by separate teams:

- `gateway-api`, `ingestion-service` — backend team
- `alerting-service` (Telegram bot) — alerting team
- `root-cause-ml` — AI partner team, consumes `server_events` produced here

Issues found in those services (e.g. a `shared_schemas` import error previously seen in `gateway-api`) are reported upstream rather than fixed directly, to keep team boundaries clean.
