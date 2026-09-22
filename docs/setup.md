# Local Setup

## Prerequisites

- Docker + Docker Compose v2 (the whole stack is designed to run via
  `docker-compose up`).
- A Telegram bot token and chat/group ID — `alerting-service` will not
  start without them (from [@BotFather](https://t.me/BotFather)).
- Only needed if running services **outside** Docker: Node.js 18+ for
  the client, Python 3.11 for `gateway-api` / `ingestion-service` /
  `anomaly-detection-ml` / `root-cause-ml`, Python 3.12 for
  `alerting-service` (the Dockerfiles pin different versions per
  service — worth knowing if you hit version-specific bugs).

## 1. Configure environment

```bash
cp .env.example .env
```

Fill in the required values — `docker-compose.yml` will refuse to
start without them (`${VAR:?VAR is required in .env}`):

| Variable | Required | Notes |
|---|---|---|
| `POSTGRES_PASSWORD` | yes | |
| `TIMESCALE_PORT` | yes | host+container port for TimescaleDB |
| `REDIS_PORT` | yes | default `6379` |
| `GATEWAY_PORT` | yes | default `8000` |
| `INGESTION_PORT` | yes | default `8001` |
| `ANOMALY_ML_PORT` | yes | default `8002` |
| `ROOT_CAUSE_ML_PORT` | yes | default `8003` |
| `CLIENT_PORT` | yes | default `3000` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | yes | gateway-api admin login |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | yes | alerting-service |
| `HOST` | no | default `localhost`; see [deployment SKILL.md](../skills/deployment/SKILL.md) for the `HOST`/`DOMAIN` fallback chain |
| `FRONTEND_URL`, `VITE_API_URL`, `VITE_WS_URL` | no | auto-derived from `HOST` + ports if unset |
| `VITE_ADMIN_PATH` | no | default `/secret-admin` |
| `DB_URL`, `REDIS_URL` | no | only needed to point at an external DB/Redis instead of the compose-managed ones |
| `REPORT_HOUR_UTC` / `REPORT_MINUTE_UTC` | no | default `9:00 UTC`, daily report time |
| `LOOKBACK_DAYS` | no | default `1` |
| `SEND_ON_STARTUP` | no | default `false`; send a report immediately on boot, useful for testing |

`ingestion-service/` and `client/` also have their own
`.env.example` files, only relevant if you run those two services
standalone outside Docker Compose.

## 2. Start the stack

```bash
docker-compose up -d --build
```

Startup order (handled by `depends_on` + healthchecks in
`docker-compose.yml`):

1. `timescaledb` and `redis` come up (health-checked).
2. `db-migrations` runs once against TimescaleDB, applying everything
   in `migrations/`, then exits — safe to re-run since it's idempotent.
3. `gateway-api` and `ingestion-service` start once both are healthy.
4. `anomaly-detection-ml` and `root-cause-ml` start once TimescaleDB is
   healthy.
5. `anomaly-bridge` (a second process from the `anomaly-detection-ml`
   image, running `bridge.py`) starts once TimescaleDB is healthy and
   the two ML services have started.
6. `alerting-service` starts once TimescaleDB is healthy — it's also
   pinned to public DNS (`8.8.8.8`/`1.1.1.1`) so it can reach the
   Telegram API.
7. `client` starts once `gateway-api` has started.

## 3. Verify

- Dashboard: `http://localhost:3000` (or whatever `CLIENT_PORT` you set)
- gateway-api Swagger docs: `http://localhost:8000/docs`
- ingestion-service Swagger docs: `http://localhost:8001/docs`
- `docker compose logs -f <service>` to tail any service's logs

`init.sql` is applied automatically by Postgres's own
`docker-entrypoint-initdb.d` mechanism the **first** time the
TimescaleDB volume is created — it won't re-run against an existing
volume, which is what the separate `db-migrations` step is for.

## Running a single service outside Docker

Every Python service reads its required env vars at import time and
raises a clear `ValueError` listing what's missing if you forget one —
so this is mostly self-documenting:

```bash
cd gateway-api
pip install -r requirements.txt
DB_URL=... ADMIN_USERNAME=... ADMIN_PASSWORD=... python main.py
```

For the client:

```bash
cd client
npm install
npm run dev   # requires client/.env with VITE_API_URL and CLIENT_PORT set
```

## No test suite yet

There is currently no automated test setup in any service. See
[skills/testing/SKILL.md](../skills/testing/SKILL.md) for what to do
when adding tests to a service that doesn't have a framework wired up
yet.
