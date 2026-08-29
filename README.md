# Game Server Health & Anomaly Monitor (GSH)

Real-time monitoring and anomaly detection platform for multiplayer game servers. It collects live server status, player counts, latency (ping), and events, stores time-series data in TimescaleDB, streams metrics via Redis Streams, and provides a real-time React dashboard.

> **Current status:** The live CS2 ingestion pipeline directly queries 28 real game servers (Vienna, Warsaw, EU-East) via Valve's UDP A2S protocol, stores metrics in TimescaleDB, publishes to Redis Streams, and streams live updates to the React dashboard via FastAPI WebSockets. The ML anomaly detection (Z-Score baseline) and Telegram alerting services are implemented. Root-Cause ML and Dota 2 / PUBG pollers are in active development.

---

## Features

- **Live CS2 Monitoring:** Real-time UDP A2S queries to 28 public CS2 servers across Eastern/Central Europe (Vienna, Warsaw, EU-East).
- **Asynchronous Ingestion:** Concurrent non-blocking polling with automatic timeout handling.
- **Time-Series Storage:** High-performance metric storage using TimescaleDB hypertables.
- **Message Broker:** Redis Streams (`server_metrics_stream`) publishing for downstream ML anomaly detection and classification pipelines.
- **Real-Time Gateway:** FastAPI REST API and live WebSocket broadcast (`/ws/live`).
- **Interactive Dashboard:** Modern React 18 + Vite dashboard with Recharts, regional/status filters, KPI metrics, and audio alerts.

---

## Architecture & Data Flow

```text
[28 Real CS2 Servers (UDP A2S Queries)]
                 │ (every 3s)
                 ▼
       [Ingestion Service / Poller]
          │                     │
          ▼                     ▼
[TimescaleDB (Hypertable)]   [Redis Streams (server_metrics_stream)]
          │                     │
          ▼                     ▼
    [Gateway API]        [ML Services (Planned)]
    (REST + /ws/live)           │
          │                     ▼
          ▼             [Alerting Service] ──► Telegram
  [React Dashboard]
```

### Data Flow Steps

1. **Seed & Discovery:** On startup, `db.py` ensures the monitored servers list is initialized in `monitored_servers`.
2. **Polling Loop:** `poller.py` performs concurrent UDP A2S queries every 3 seconds to measure latency, player count, and online status.
3. **Database Storage:** Metrics are written to the `server_metrics` TimescaleDB hypertable, and server statuses are updated in `monitored_servers`.
4. **Stream Publishing:** Each metric record is pushed to the Redis Stream `server_metrics_stream` for consumption by ML anomaly detection models.
5. **Gateway Broadcasting:** The Gateway API provides REST endpoints and pushes live snapshots every 3 seconds through `/ws/live`.
6. **Frontend Visualization:** The React UI renders KPI cards, time-series charts, and server grids in real time.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, Vite, Recharts, Tailwind CSS, Lucide Icons |
| **Gateway API** | FastAPI, Uvicorn, asyncpg, WebSockets |
| **Ingestion Service** | FastAPI, `python-a2s`, `asyncpg`, `redis-py` |
| **Database** | PostgreSQL 15 + TimescaleDB Extension |
| **Message Queue** | Redis 7 (Redis Streams) |
| **Shared Schemas** | Pydantic v2 |

---

## Project Structure

```text
.
├── docker-compose.yml          # Container orchestration (TimescaleDB, Redis, Gateway, Ingestion)
├── init.sql                    # TimescaleDB schema (hypertables, servers, events)
├── shared_schemas/             # Shared Pydantic schemas across services
│   └── models.py
├── gateway-api/                # REST API & WebSocket service
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── ingestion-service/          # Live CS2 A2S poller and ingestion API
│   ├── db.py                   # Async connection pool & initial server seeds
│   ├── poller.py               # Asynchronous UDP A2S poller & Redis publisher
│   ├── main.py                 # FastAPI service and lifespan runner
│   ├── schemas.py              # Ingestion-specific Pydantic schemas
│   ├── Dockerfile
│   └── requirements.txt
├── anomaly-detection-ml/       # ML Anomaly Detection Service (Baseline implemented)
│   ├── main.py
│   ├── bridge.py
│   └── Dockerfile
├── root-cause-ml/              # ML Root-Cause Classifier Service (In Development)
│   ├── main.py
│   └── Dockerfile
├── alerting-service/           # Telegram Alerting & Reporting service
│   ├── main.py
│   ├── scheduler.py
│   ├── reports.py
│   └── Dockerfile
└── client/                     # React + Vite Dashboard
    ├── src/
    │   ├── components/         # Dashboard views, charts, cards, modals
    │   ├── hooks/              # useServerData, useWebSocket, useAudioAlert
    │   └── services/           # REST client with circuit breaker
    ├── vite.config.js
    └── package.json
```

---

## Getting Started

### Development Mode (Recommended)

Run databases in Docker, and run the backend poller and frontend locally for development and testing:

#### 1. Start Infrastructure (TimescaleDB + Redis + Gateway)
```bash
docker compose up -d timescaledb redis gateway-api
```

#### 2. Run the Ingestion Poller (in a separate terminal)
```bash
cd ingestion-service
python poller.py
```
*(Or run the full Ingestion API: `uvicorn main:app --port 8001 --reload`)*

#### 3. Start the Frontend Dashboard (in a separate terminal)
```bash
cd client
npm install
npm run dev
```

Open `http://localhost:3000` to view the live dashboard.

---

### Full Docker Mode

To run all services inside Docker containers:

```bash
docker compose up -d --build
```

### Anomaly and root-cause pipeline

`anomaly-bridge` sends every confirmed anomaly to `root-cause-ml` and stores
the telemetry, anomaly score, ranked diagnosis, and primary root cause in
`server_events`. For an existing database volume, apply the schema migration
once before starting the updated bridge:

```bash
docker compose exec -T timescaledb psql -U postgres -d game_monitor < migrations/001_add_anomaly_evidence.sql
```

Then rebuild and start the ML services:

```bash
docker compose up -d --build root-cause-ml anomaly-detection-ml anomaly-bridge
```

- **Dashboard:** http://localhost:3000
- **Gateway API Swagger Docs:** http://localhost:8000/docs
- **Ingestion Service Health:** http://localhost:8001/health

To stop all services:
```bash
docker compose down
```

---

## API Endpoints

### Gateway API (`http://localhost:8000`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/servers` | All monitored servers with their latest metrics |
| `GET` | `/api/v1/servers/{server_id}/metrics?limit=30` | Historical time-series metrics for a server |
| `GET` | `/api/v1/events?limit=20` | Recent server incident and anomaly events |
| `GET` | `/api/v1/analytics/ping-buckets?minutes=10` | Time-bucketed average ping and player counts |
| `POST` | `/api/v1/servers` | Register a new server to monitor |
| `WS` | `/ws/live` | Real-time WebSocket snapshot stream (every 3s) |

### Ingestion API (`http://localhost:8001`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Ingestion service health status |
| `POST` | `/api/v1/ingest/metric` | Ingest a raw server metric record |
| `POST` | `/api/v1/ingest/event` | Ingest an event or alert log |

---

## Roadmap

- [x] Shared Pydantic data schemas
- [x] TimescaleDB time-series storage and hypertable configuration
- [x] Live CS2 asynchronous UDP A2S poller (Vienna, Warsaw, EU-East)
- [x] Redis Streams publishing (`server_metrics_stream`)
- [x] Real-time FastAPI WebSocket gateway
- [x] Full-featured React dashboard with live charts and filters
- [x] Anomaly Detection Service (Rolling Z-Score Baseline)
- [ ] Root-Cause Classification Service (Rules & ML classification)
- [x] Telegram Bot Alerting Service with scheduled reports
- [ ] Dota 2 (OpenDota / Steam API) live ingestion
- [ ] PUBG API rate-limited shard polling
