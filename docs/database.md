# TimescaleDB and Redis Streams

## TimescaleDB

Schema is defined in `init.sql` (applied automatically on first
container start via Postgres's `docker-entrypoint-initdb.d`
mechanism) plus one migration in `migrations/`. The `timescaledb`
extension is enabled at the top of `init.sql`.

### `monitored_servers`

The list of game servers being watched.

| Column | Type | Notes |
|---|---|---|
| `server_id` | `VARCHAR(64)` | Primary key, format `"ip:port"` |
| `server_name` | `VARCHAR(256)` | |
| `region` | `VARCHAR(32)` | |
| `status` | `VARCHAR(16)` | Default `'ONLINE'` |
| `last_online_at` | `TIMESTAMPTZ` | |
| `last_offline_at` | `TIMESTAMPTZ` | |
| `created_at` | `TIMESTAMPTZ` | Default `NOW()` |

### `server_metrics` — hypertable

Raw polling data, one row per server per poll (~every 3s).
`create_hypertable('server_metrics', 'time', if_not_exists => TRUE)`
partitions it on `time`. No retention or compression policy is
configured yet — this table grows unbounded, worth addressing before
running this in production for any length of time.

| Column | Type | Notes |
|---|---|---|
| `time` | `TIMESTAMPTZ` | Not null; hypertable partition key |
| `server_id` | `VARCHAR(64)` | FK → `monitored_servers.server_id` |
| `player_count` | `INT` | |
| `max_players` | `INT` | |
| `ping_ms` | `NUMERIC(6,2)` | |

### `server_events`

Labeled incidents — anomalies detected by the ML pipeline, or manually
relabeled by an admin via `PATCH /api/v1/events/{id}/label`. A regular
table, not a hypertable, despite having a `time` column.

| Column | Type | Notes |
|---|---|---|
| `id` | `SERIAL` | Primary key |
| `time` | `TIMESTAMPTZ` | Not null |
| `server_id` | `VARCHAR(64)` | FK → `monitored_servers.server_id` |
| `event_type` | `VARCHAR(32)` | `CRASH` \| `OFFLINE` \| `HIGH_PING` \| `RECOVERY` |
| `root_cause` | `VARCHAR(64)` | Default `'NORMAL'`; widened from 32 chars by a later `ALTER` |
| `label_source` | `VARCHAR(32)` | `'model'` or `'manual'`, default `'model'` |
| `message` | `TEXT` | Not null |
| `anomaly_score` | `NUMERIC(5,4)` | |
| `anomaly_reasons` | `TEXT[]` | |
| `player_count`, `max_players`, `ping_ms` | | Snapshot at time of event |
| `ping_delta`, `player_delta` | | Deviation from baseline |
| `servers_affected_same_region` | `INT` | Used to distinguish a single-server issue from a regional outage |
| `diagnosis` | `JSONB` | Full root-cause-ml response |
| `is_alerted` | `BOOLEAN` | Default `FALSE`; flipped once `alerting-service` sends a Telegram alert |

`root_cause` values produced by `root-cause-ml`: `SERVER_CRASH`,
`HIGH_LATENCY`, `DDOS_ATTACK`, `REGIONAL_OUTAGE`, `PLAYER_DROP`,
`MAINTENANCE`, `UNKNOWN_ANOMALY`, plus `NORMAL`/`UNKNOWN`.

A partial index,
`idx_server_events_label_source ON server_events(label_source, root_cause) WHERE root_cause IS NOT NULL AND root_cause NOT IN ('UNKNOWN','NORMAL')`,
speeds up the query `root-cause-ml`'s training job uses to pull
labeled examples.

### `daily_reports`

Cache of `alerting-service`'s once-a-day report, also served back
through `gateway-api`'s `/api/v1/insights/daily`.

| Column | Type | Notes |
|---|---|---|
| `report_date` | `DATE` | Primary key |
| `report_text` | `TEXT` | Plain-text Telegram message |
| `html_content` | `TEXT` | HTML report attached to the Telegram message |
| `json_data` | `JSONB` | Structured data backing the report |

### Migrations

`migrations/001_add_anomaly_evidence.sql` re-adds (via `ADD COLUMN IF
NOT EXISTS`) the `server_events` evidence columns already present in
`init.sql`, so it's a no-op on a fresh database but brings an
existing/older TimescaleDB volume up to date. It's applied by a
one-shot `db-migrations` container on every `docker compose up`.

**When adding a schema change**: add a new numbered file under
`migrations/`, write it idempotently (`IF NOT EXISTS` / `IF EXISTS`),
and never hand-edit `init.sql` for a database that already exists —
`init.sql` only runs once, on first volume creation. See
[deployment SKILL.md](../skills/deployment/SKILL.md).

## Redis Streams

Redis is used for exactly one stream today: `server_metrics_stream`,
written by `ingestion-service` on every successful poll (`XADD`,
capped at `maxlen=10000`, approx-trimmed). Writes are best-effort — if
Redis is unreachable, the write is silently skipped and polling
continues uninterrupted.

**No service currently consumes this stream.** There is no
`XREAD`/`XREADGROUP`/consumer-group code anywhere in the repo. The
actual anomaly pipeline (`anomaly-bridge`) polls `server_metrics` in
TimescaleDB directly instead — see
[architecture.md](architecture.md#known-discrepancy-redis-streams-are-not-actually-part-of-the-pipeline-yet)
for the full picture. `gateway-api` also carries a `redis` dependency
and a `REDIS_URL` env var that its code never uses.

If you add a real consumer for this stream, or add a new one, document
the producer, consumer, and message shape here.
