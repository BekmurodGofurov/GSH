# Game Server Health Monitor

Real-time monitoring dashboard for CS2 servers. It collects server status, player counts, ping, and events, stores them in TimescaleDB, and displays them in a React dashboard.

> **Current status:** The working demo pipeline includes a CS2 synthetic data generator, PostgreSQL/TimescaleDB, a FastAPI Gateway, and a React frontend. Dota 2/PUBG sources, ML services, and Discord alerting are planned but not implemented yet.

## Features

- Two demo CS2 servers: Vienna and Warsaw
- Synthetic metrics generated every 3 seconds
- `ONLINE` and `OFFLINE` statuses
- Automatic `CRASH`, `RECOVERY`, and `HIGH_PING` events
- Metric history stored in a TimescaleDB hypertable
- FastAPI REST API and WebSocket live stream
- React + Vite dashboard with charts
- Frontend circuit breaker and connection banner

## Architecture

```text
Synthetic Generator (every 3 seconds)
              |
              v
TimescaleDB/PostgreSQL <---- Redis foundation
              |
              v
FastAPI Gateway (REST + /ws/live)
              |
              v
React/Vite Dashboard
```

### Data flow

1. `generator.py` registers the demo servers in the database.
2. Every 3 seconds it generates player count and ping values.
3. It writes metrics and status changes to the database.
4. It records `CRASH`, `RECOVERY`, and `HIGH_PING` events.
5. The Gateway exposes the latest data through REST and WebSocket endpoints.
6. The frontend loads initial data through REST and receives live updates through WebSocket.

## Technology stack

| Component | Technology |
|---|---|
| Frontend | React 18, Vite, Recharts, Tailwind CSS, Lucide |
| API | FastAPI, Uvicorn |
| Database | PostgreSQL 15 + TimescaleDB |
| Async database client | asyncpg |
| Queue foundation | Redis 7 |
| Development | Docker Compose, Python 3.11 |

## Requirements

- Docker Desktop and Docker Compose
- Node.js 18+ and npm
- Git

Python is not required on the host because the backend services and generator run inside containers.

## Getting started

### 1. Start backend services

Run from the project root:

```bash
docker compose up -d --build timescaledb redis gateway-api ingestion-service
```

Check service status:

```bash
docker compose ps
```

Useful URLs:

- Gateway Swagger docs: http://localhost:8000/docs
- Ingestion health check: http://localhost:8001/health

### 2. Start the demo generator

Run this in a new terminal:

```bash
docker compose exec -T ingestion-service \
  sh -lc 'DB_URL=postgresql://postgres:postgrespassword@timescaledb:5432/game_monitor \
  REDIS_URL=redis://redis:6379 python /app/generator.py'
```

The generator runs continuously. Press `Ctrl+C` to stop it.

### 3. Start the frontend

```bash
cd client
npm install
npm run dev
```

Open the dashboard at http://localhost:3000.

The Vite proxy forwards `/api` and `/ws` requests to `localhost:8000`.

### 4. Stop services

```bash
docker compose down
```

No database volume is configured, so recreating the database container normally removes stored data. To also remove the Compose network:

```bash
docker compose down --remove-orphans
```

## API endpoints

### Gateway API: `http://localhost:8000`

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/servers` | All servers and their latest metrics |
| `GET` | `/api/v1/servers/{server_id}/metrics?limit=30` | Metric history for one server |
| `GET` | `/api/v1/events?limit=20` | Latest server events |
| `GET` | `/api/v1/analytics/ping-buckets?minutes=10` | Per-minute ping/player aggregation |
| `WS` | `/ws/live` | Servers and the latest five events every 3 seconds |

Examples:

```bash
curl http://localhost:8000/api/v1/servers
curl 'http://localhost:8000/api/v1/events?limit=10'
curl 'http://localhost:8000/api/v1/analytics/ping-buckets?minutes=10'
```

### Ingestion API: `http://localhost:8001`

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health status |
| `POST` | `/api/v1/ingest/metric` | Store one metric |
| `POST` | `/api/v1/ingest/event` | Store one event |

Metric example:

```bash
curl -X POST http://localhost:8001/api/v1/ingest/metric \
  -H 'Content-Type: application/json' \
  -d '{
    "server_id": "185.25.180.1:27015",
    "player_count": 12,
    "max_players": 24,
    "ping_ms": 32.5
  }'
```

Event example:

```bash
curl -X POST http://localhost:8001/api/v1/ingest/event \
  -H 'Content-Type: application/json' \
  -d '{
    "server_id": "185.25.180.1:27015",
    "event_type": "HIGH_PING",
    "message": "High latency detected: 250ms"
  }'
```

## Database structure

`init.sql` creates three tables:

- `monitored_servers` stores server names, regions, statuses, and timestamps.
- `server_metrics` stores timestamped player counts, maximum players, and ping. Its `time` column is a TimescaleDB hypertable dimension.
- `server_events` stores `CRASH`, `RECOVERY`, `HIGH_PING`, and other event records.

Connect from the host:

```bash
psql 'postgresql://postgres:postgrespassword@localhost:5433/game_monitor'
```

Connect from inside the database container:

```bash
docker compose exec timescaledb psql -U postgres -d game_monitor
```

## Project structure

```text
.
├── docker-compose.yml
├── init.sql
├── gateway-api/
│   ├── main.py                 # REST API and WebSocket endpoint
│   ├── Dockerfile
│   └── requirements.txt
├── ingestion-service/
│   ├── main.py                 # Metric and event write API
│   ├── generator.py            # Synthetic CS2 data generator
│   ├── Dockerfile
│   └── requirements.txt
├── shared_schemas/
│   └── models.py               # Shared Pydantic models
├── anomaly-detection-ml/
│   └── main.py                 # Planned ML service
├── root-cause-ml/
│   └── main.py                 # Planned classification service
├── alerting-service/
│   └── main.py                 # Planned alerting service
└── client/
    ├── src/
    │   ├── components/         # Shared, dashboard, layout, and view components
    │   ├── hooks/              # API, WebSocket, and audio alert hooks
    │   ├── services/api.js     # Gateway REST client
    │   └── utils/              # Formatting helpers
    ├── vite.config.js          # Port 3000 and Gateway proxy
    └── package.json
```

Build the frontend for production:

```bash
npm --prefix client run build
```

## Configuration

Default local values:

```text
DB_URL=postgresql://postgres:postgrespassword@localhost:5433/game_monitor
REDIS_URL=redis://localhost:6379
```

Container values:

```text
DB_URL=postgresql://postgres:postgrespassword@timescaledb:5432/game_monitor
REDIS_URL=redis://redis:6379
```

To change the frontend Gateway URL, add this to `client/.env`:

```text
VITE_API_URL=http://localhost:8000
```

## Troubleshooting

Restart backend services if the database was not ready when they started:

```bash
docker compose restart gateway-api ingestion-service
```

View logs:

```bash
docker compose logs -f gateway-api
docker compose logs -f ingestion-service
```

If `/api/v1/servers` returns an empty list, make sure the generator is running and the database is ready. The generator must run inside the `ingestion-service` container; a host `localhost` database URL does not work from inside a container.

If the frontend cannot connect, verify that the Gateway is running, the API returns a response, generator logs show new metrics, and the dashboard is open at `http://localhost:3000`.

## Roadmap

- [ ] Redis Streams for metric and anomaly events
- [ ] Real CS2 A2S/Steam API ingestion
- [ ] Dota 2 OpenDota/Steam live data integration
- [ ] PUBG API integration with rate-limit backoff
- [ ] Rolling z-score or EWMA anomaly detection
- [ ] Root-cause classification
- [ ] Discord webhook alerting and incident deduplication
- [ ] Authentication, secrets management, and production CORS configuration
- [ ] Automated tests and CI pipeline

## Project goal

Build a health monitoring platform for multiplayer game servers that collects metrics through a shared schema, detects anomalies, classifies likely causes, and delivers actionable information through a live dashboard and alerts.
