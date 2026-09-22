# Microservices and Data Workflow

GSH is split into six services, each in its own directory and Docker
image, communicating over HTTP and (in one place) Redis Streams. This
doc describes what each service actually does and how data moves
between them, traced from the code rather than assumed from the stack
list.

## Services

| Service | Role | Talks to |
|---|---|---|
| `ingestion-service` | Polls game servers over UDP (Valve A2S protocol), writes metrics/status to TimescaleDB | TimescaleDB, Redis (best-effort) |
| `anomaly-detection-ml` | Scores incoming metrics for anomalies (rolling z-score) | Called over HTTP by `anomaly-bridge` |
| `root-cause-ml` | Classifies a likely root cause for a flagged anomaly (ML model + rule-based fallback) | Called over HTTP by `anomaly-bridge` |
| `anomaly-bridge` | A second process built from the `anomaly-detection-ml` image (`bridge.py`); polls TimescaleDB, orchestrates the anomaly → root-cause pipeline, writes labeled incidents back to TimescaleDB | TimescaleDB, `anomaly-detection-ml`, `root-cause-ml` |
| `gateway-api` | Read/aggregation API + admin CRUD + live WebSocket feed for the dashboard | TimescaleDB only |
| `alerting-service` | Telegram bot: scheduled daily reports + near-real-time incident alerts | TimescaleDB, Telegram API |
| `client` | React/Vite dashboard | `gateway-api` (HTTP + WebSocket) |

## Real data flow

```
ingestion-service --(A2S poll, every 3s)--> game servers
        |
        v
   server_metrics (TimescaleDB hypertable)
        |
        v (polled every 5s)
   anomaly-bridge --(HTTP POST /predict/anomaly)--> anomaly-detection-ml
        |
        v (if anomaly)
   anomaly-bridge --(HTTP POST /predict/root-cause)--> root-cause-ml
        |
        v
   server_events (labeled incident row)
        |
        +--> gateway-api --(HTTP + WebSocket)--> client dashboard
        |
        +--> alerting-service --(poll every 15s)--> Telegram alert
        |
        +--> alerting-service --(daily cron)--> Telegram report
```

1. `ingestion-service` polls every server in `monitored_servers` every
   3 seconds, writes a row to `server_metrics`, and updates that
   server's `status`/`last_online_at`/`last_offline_at`.
2. `anomaly-bridge` polls `server_metrics` for rows newer than its last
   cursor every 5 seconds, and calls `anomaly-detection-ml`'s
   `/predict/anomaly` over HTTP.
3. If the result is an anomaly, `anomaly-bridge` also calls
   `root-cause-ml`'s `/predict/root-cause`, then writes a labeled row
   into `server_events` (`label_source='model'`) with the anomaly
   score, reasons, and root-cause diagnosis.
4. `gateway-api` reads `monitored_servers`, `server_metrics`,
   `server_events`, and `daily_reports` to serve the REST API and the
   `/ws/live` WebSocket feed the dashboard uses.
5. `alerting-service` runs independently: every 15 seconds it checks
   `server_events` for new unalerted rows and sends a Telegram alert;
   once a day it builds and sends a full report, and caches it in
   `daily_reports`.

## Known discrepancy: Redis Streams are not actually part of the pipeline yet

`ingestion-service` does publish each metric to a Redis Stream
(`server_metrics_stream`), and `gateway-api` carries a `redis`
dependency with `REDIS_URL` wired up in `docker-compose.yml`. However,
**nothing in the codebase currently reads from that stream** — no
service has consumer-group or `XREAD` code. The real anomaly pipeline
(`anomaly-bridge`) works entirely by polling `server_metrics` directly
in TimescaleDB, not by consuming the stream.

Per [AGENTS.md](../AGENTS.md), inter-service communication should go
through HTTP, Redis Streams, or shared schemas — the current
implementation satisfies that with HTTP + direct DB polling, but the
Redis Streams path is a write-only, currently-orphaned side channel.
If you're picking this up: either wire a real consumer for
`server_metrics_stream` (e.g. to decouple `anomaly-bridge` from
polling TimescaleDB directly), or remove the write path and the unused
`redis` dependency in `gateway-api` to avoid the dead code implying a
data flow that doesn't exist.

## Cross-service import boundary

None of the services import another service's application code
directly — each communicates only via HTTP calls or direct database
access to tables it's responsible for. Keep it that way: if two
services need to share a request/response shape, put it in
`shared_schemas` rather than importing across service directories.
