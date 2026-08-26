# Game Server Health & Anomaly Monitor — Project Requirements

**Team:** 1 Backend Developer + 2 ML/AI Developers
**Lead:** Nodirbek
**Goal:** Build a monitoring system that ingests live server/match data from CS2, Dota 2, and PUBG, detects anomalies (crashes, lag spikes, abnormal player drop-off), classifies the likely cause, and alerts in real time.

---

## 1. Project Overview

We are building a mini version of a network operations monitoring platform (similar in spirit to enterprise infra monitoring), but pointed at public multiplayer game server data instead of corporate infrastructure. The system will:

1. Continuously pull server/match health metrics for CS2, Dota 2, and PUBG
2. Detect anomalies in real time (tick rate drops, ping spikes, sudden player count crashes)
3. Classify what likely caused the anomaly (crash, DDoS pattern, patch-day overload, regional ISP issue)
4. Alert the team via Discord
5. Display live server health on a dashboard

**Why this project:** it uses real, freely available data, is genuinely useful to check during patches/tournaments, and teaches the full stack of skills (API integration, time-series data engineering, ML anomaly detection, and service architecture) that transfer directly to production monitoring systems.

---

## 2. Architecture Overview

```
[Data Sources: Steam API / A2S / OpenDota / PUBG API]
              |
              v
      [Ingestion Service]  (Backend)
              |
              v
   [Message Queue: Redis Streams]
         |              |
         v              v
[Anomaly Detection]  [Root-Cause Classifier]   (ML #1, ML #2)
         |              |
         v              v
      [Alerting Service]  --> Discord Webhook
              |
              v
        [Dashboard API]  --> Frontend (live view)
```

Each box is an independently runnable FastAPI service (Docker container). Services talk to each other over HTTP or via the queue — never by importing each other's code directly. This is intentional: it forces clean API contracts between the backend and ML sides.

---

## 3. Roles & Ownership

| Service | Owner | Stack |
|---|---|---|
| Ingestion Service | Backend Dev | FastAPI, Postgres/TimescaleDB, APScheduler/Celery |
| Anomaly Detection Service | ML Dev #1 | FastAPI, scikit-learn / statsmodels |
| Root-Cause Classification Service | ML Dev #2 | FastAPI, scikit-learn / rule engine |
| Alerting Service | Backend Dev (or shared) | FastAPI, Redis, Discord webhook |
| Dashboard/Gateway API | Backend Dev | FastAPI, WebSocket/SSE |

**Golden rule:** the Backend Dev defines and publishes the Pydantic request/response schema for every ML endpoint *before* the ML devs write real model code. ML devs can build against a mocked/random-response version of their own endpoint from day one, then swap in the real model later without changing the contract.

---

## 3.1 Regional Scope: Eastern Europe

For v1, we're scoping server monitoring to Eastern Europe rather than trying to cover every region globally. Here's how "Eastern Europe" maps onto each game's actual server/region setup:

- **CS2**: Valve's "EU East" datacenter region is physically split across **Vienna, Austria** and **Warsaw, Poland**. These are the two datacenters to target with A2S queries and to filter for in the `GetServerList` call (filter by IP range or by pinging/geolocating returned servers). Valve doesn't expose a clean "region" filter param directly — the practical approach is to pull servers via `GetServerList`, then geolocate/filter by IP to the Vienna/Warsaw ranges.
- **Dota 2**: Uses the same underlying Valve datacenter network as CS2, so live league games routed through Vienna/Warsaw are the equivalent "Eastern Europe" slice. Since OpenDota's `/live` endpoint doesn't expose datacenter directly, the backend intern will need to cross-reference match/server info from the Steam `GetLiveLeagueGames` response to filter for the EU East datacenter.
- **PUBG**: The PUBG API doesn't split "Eastern" vs "Western" Europe — it has one `pc-eu` shard covering all of Europe, and a separate `pc-ru` shard for Russia/CIS. For an "Eastern Europe" scope, poll both the `pc-eu` and `pc-ru` shards, since between them they cover the region we care about. This is a coarser split than CS2/Dota2 give us — worth flagging to the team early.

**Action item:** the backend intern should build a small reference table (or config file) of monitored server IPs / shard identifiers per game, so the ingestion service has a fixed, known target list rather than trying to discover "Eastern Europe" dynamically on every poll.

---

## 4. Per-Game Data Source Requirements

### 4.1 CS2 (Counter-Strike 2)

**Data sources:**
- **A2S Query Protocol** — Valve's Source server query protocol. Any public server IP:port can be queried directly (UDP) for: current map, player count, max players, tick rate (via `A2S_INFO`), and round-trip ping from the querying machine.
  - Protocol reference: `https://developer.valvesoftware.com/wiki/Server_queries`
  - Python client (recommended, no external deps): `python-a2s` — install via `pip install python-a2s`, repo/docs at `https://github.com/Yepoleb/python-a2s`. Exposes `a2s.info()`, `a2s.players()`, `a2s.rules()` (plus async variants `ainfo`/`aplayers`/`arules`).
  - Example: `a2s.info(("some.server.ip", 27015))` returns tick-adjacent server fields (map, player_count, max_players, server_name) in one UDP round trip — this is your core CS2 metric source.
- **Steam Web API** (`IGameServersService/GetServerList/v1/`) — returns lists of public CS2 servers by region/appid/tag, useful for building the initial server pool to monitor.
  - Endpoint: `https://api.steampowered.com/IGameServersService/GetServerList/v1/?filter=\appid\730&limit=5000&key=YOUR_KEY` (CS2's Steam AppID is 730; filter syntax reference at `https://developer.valvesoftware.com/wiki/Master_Server_Query_Protocol#Filter`)
  - Get a free key: `https://steamcommunity.com/dev/apikey` (requires a Steam account that owns at least one game)
  - Full interface reference: `https://partner.steamgames.com/doc/webapi/igameserversservice`

**Metrics to capture per poll:**
- `server_id`, `region`, `map`, `player_count`, `max_players`, `tick_rate`, `ping_ms`, `timestamp`

**Known real-world anomaly patterns to watch for:**
- Tick rate drop below expected (e.g., 128 → under 60) = server under load or hardware issue
- Sudden player count drop to 0 mid-session = crash
- Ping spike across many servers in one region simultaneously = regional network issue, not a single server problem

**Expected result:** a poller that queries a configurable list of server IPs every N seconds and writes normalized rows to the metrics table without blocking on slow/unresponsive servers (must have a timeout).

---

### 4.2 Dota 2

**Data sources:**
- **OpenDota API** (public, free, no key required for most endpoints) — match data, live league games, player and match history.
  - Base URL: `http://api.opendota.com/api` — full docs at `https://docs.opendota.com/`
  - Key endpoints: `GET /live` (top currently ongoing live games — best fit for our polling), `GET /leagues`, `GET /matches/{match_id}`
  - Free tier: 50,000 calls/month, 60 requests/minute (no key needed at this tier) — plenty for a polling interval of a few seconds
  - Python wrapper (optional): `pyopendota` — docs at `https://pyopendota.readthedocs.io/`
- **Steam Web API** (`IDOTA2Match_570/GetLiveLeagueGames/v1/`) — official live match data direct from Valve, needs the same Steam Web API key as the CS2 GetServerList call above (`https://steamcommunity.com/dev/apikey`). Use this as a cross-check against OpenDota's `/live` endpoint if you want two independent sources for the same anomaly signal.

**Metrics to capture per poll:**
- `match_id`, `server/region`, `spectator_count`, `game_time`, `radiant_score`, `dire_score`, `average_ping_estimate` (if available), `timestamp`

**Known real-world anomaly patterns to watch for:**
- Match data suddenly stops updating = server-side match crash or disconnect
- Spectator/viewer count anomaly during major tournaments (spike or unexpected drop)
- Correlate anomalies with Dota 2 patch release dates (Valve publishes patch notes — this is a good external signal for the classifier)

**Expected result:** a poller for live league/match data that handles the case where a match ends mid-polling (should stop tracking gracefully, not error out).

---

### 4.3 PUBG

**Data sources:**
- **Official PUBG Developer API** — full docs at `https://documentation.pubg.com/en/index.html`. Provides matches, player stats, and telemetry.
  - Get a free API key: `https://developer.pubg.com` (sign in, create a key tied to an in-game name)
  - Auth: send `Authorization: Bearer <api-key>` and `Accept: application/vnd.api+json` headers
  - Core flow: `GET https://api.pubg.com/shards/{platform}/samples` (a free, no-extra-cost way to pull a rolling sample of recent match IDs across a region without needing specific player names) → `GET https://api.pubg.com/shards/{platform}/matches/{matchId}` (match object, includes an asset with the telemetry URL) → fetch the telemetry JSON URL directly (telemetry itself needs **no** API key, it's served from `telemetry-cdn.pubg.com`)
  - Telemetry event/object reference: `https://documentation.pubg.com/en/telemetry-events.html` and `https://documentation.pubg.com/en/telemetry-objects.html`
  - Python wrapper (optional): `pubg-python` — `pip install pubg-python`, repo at `https://github.com/ramonsaraiva/pubg-python`
- Rate limits are strict (10 requests/minute on the free tier) — this is an important constraint for the backend dev to design around (queuing/backoff logic). Full policy: `https://documentation.pubg.com/en/rate-limits.html`

**Metrics to capture per poll:**
- `match_id`, `region`, `platform` (steam/psn/xbox), `player_count`, `match_duration`, `telemetry_status`, `timestamp`

**Known real-world anomaly patterns to watch for:**
- Abnormally short match duration (players disconnecting/server dying early)
- Region-specific match count drop (fewer matches starting than expected for that region/time of day)

**Expected result:** a poller respecting the 10 req/min rate limit via a token-bucket or scheduled queue, with graceful degradation (skip a cycle rather than crash) when the limit is hit.

**Fallback:** if API key approval is delayed, use a synthetic data generator (see Section 7) so ML work isn't blocked.

---

## 5. Common Data Schema (all three games normalize into this)

```python
class ServerMetric(BaseModel):
    id: str
    game: Literal["cs2", "dota2", "pubg"]
    region: str
    player_count: int
    max_players: int | None = None
    tick_rate: float | None = None       # CS2 only
    ping_ms: float | None = None
    match_duration_s: int | None = None  # PUBG/Dota only
    timestamp: datetime
```

Backend dev owns this schema. ML devs consume it — they should never need to know the game-specific quirks (A2S vs REST vs telemetry) because ingestion normalizes everything first.

---

## 6. Service Requirements & Expected Results

### 6.1 Ingestion Service (Backend)
**Requirements:**
- Poll all three data sources on independent, configurable schedules
- Normalize into the common `ServerMetric` schema
- Write to TimescaleDB/Postgres
- Publish each new metric onto a Redis Stream for downstream consumers
- Must not crash or block if one game's API is down — isolate failures per source

**Expected result:** a continuously running service that, after 24 hours, has a gap-free (or gap-logged) time series for every monitored server, with source failures visible in logs/metrics but not taking down ingestion for the other two games.

---

### 6.2 Anomaly Detection Service (ML Dev #1)
**Requirements:**
- Expose `POST /predict/anomaly` accepting a `ServerMetric` (or a rolling window of recent metrics for that server)
- Return an anomaly score (0–1) and boolean flag
- Start with a simple baseline (rolling z-score/EWMA), then move to Isolation Forest or an LSTM autoencoder once there's enough historical data
- Must account for daily/weekly seasonality (player counts are naturally higher on weekend evenings — this should not be flagged as anomalous)

**Expected result:** on a held-out window of historical data with injected synthetic anomalies (see Section 7), the model should catch a target recall (agree on a number together, e.g. 85%+) without excessive false positives on normal seasonal peaks.

---

### 6.3 Root-Cause Classification Service (ML Dev #2)
**Requirements:**
- Expose `POST /predict/rootcause` accepting a flagged anomaly + surrounding metric context
- Return a predicted category: `server_crash`, `ddos_pattern`, `patch_overload`, `regional_network_issue`, `unknown`
- Start as a rule-based classifier (e.g., "player count → 0 instantly" = crash; "ping spike across many servers, same region, same time" = regional issue) before training a real classifier once labeled examples accumulate
- Should incorporate external signals where available (e.g., known patch/update timestamps from Valve/PUBG patch notes as a feature)

**Expected result:** given a batch of historical flagged anomalies (can be manually labeled by the team early on), the classifier should correctly categorize the majority of clear-cut cases (e.g., instant-zero player count → crash).

---

### 6.4 Alerting Service
**Requirements:**
- Consume anomaly + root-cause results from the queue
- Deduplicate (don't re-alert on the same ongoing issue every poll cycle)
- Push formatted messages to a Discord webhook, including server, game, region, anomaly type, and a link to the dashboard

**Expected result:** a real anomaly (e.g., manually kill a test server or simulate one) results in exactly one Discord message within one polling interval, not a flood of repeated alerts.

---

### 6.5 Dashboard / Gateway API
**Requirements:**
- Aggregate live + recent historical data across all three games
- Expose a WebSocket or SSE endpoint for live updates to a frontend
- Basic filtering by game/region

**Expected result:** a simple live-updating view showing server health status (green/yellow/red) per monitored server, updating without a page refresh.

---

## 7. Handling API Access Delays (Synthetic Data Fallback)

PUBG's API key approval and Steam API key setup can take time. To avoid blocking the ML devs:

- Build a **synthetic data generator** that produces realistic `ServerMetric` streams with configurable injected anomalies (sudden drops, gradual degradation, seasonal patterns)
- ML devs should build and validate their models against synthetic data first, then validate against real data once ingestion is live
- This also gives you labeled ground truth for measuring model recall/precision, which real data won't have initially

**Expected result:** ML work starts on Day 1 regardless of API key approval status.

---

## 8. Infra & Dev Environment

- Each service in its own Docker container, orchestrated via `docker-compose` for local dev
- Shared Pydantic schema package (`shared-schemas`) imported by all services so the contract can't silently drift
- Redis for both the stream/queue and as the alerting dedup cache
- Postgres + TimescaleDB extension (or plain Postgres with time-based partitioning) for metric storage

---

## 9. Suggested Milestones

| Week | Deliverable |
|---|---|
| 1 | Shared schema finalized; synthetic data generator working; ingestion skeleton for one game (CS2, easiest via A2S) |
| 2 | Ingestion for all three games; anomaly detection baseline (z-score) running against synthetic + real data |
| 3 | Root-cause classifier (rule-based v1); alerting service wired to Discord |
| 4 | Dashboard live view; anomaly model upgraded (Isolation Forest/LSTM); end-to-end demo with a real or simulated server incident |

---

## 10. Sources — Quick Reference

| Game | Source | URL | Auth needed? |
|---|---|---|---|
| CS2 | A2S Query Protocol docs | `https://developer.valvesoftware.com/wiki/Server_queries` | No (UDP query to server) |
| CS2 | `python-a2s` library | `https://github.com/Yepoleb/python-a2s` | No |
| CS2 | Steam `GetServerList` | `https://api.steampowered.com/IGameServersService/GetServerList/v1/` | Yes — Steam Web API key |
| CS2/Dota2 | Steam Web API key signup | `https://steamcommunity.com/dev/apikey` | Free Steam account w/ a game owned |
| Dota 2 | OpenDota API docs | `https://docs.opendota.com/` | No (free tier, rate-limited) |
| Dota 2 | OpenDota `/live` endpoint | `http://api.opendota.com/api/live` | No |
| Dota 2 | Steam `GetLiveLeagueGames` | `IDOTA2Match_570/GetLiveLeagueGames/v1/` on `api.steampowered.com` | Yes — Steam Web API key |
| PUBG | PUBG Developer API docs | `https://documentation.pubg.com/en/index.html` | — |
| PUBG | API key signup | `https://developer.pubg.com` | Free, in-game-name tied key |
| PUBG | `pubg-python` library | `https://github.com/ramonsaraiva/pubg-python` | No (lib itself) |

---

## 11. Open Questions to Resolve as a Team

- Which specific public CS2/Dota 2 servers or community server lists will we monitor (need real IPs from the Vienna/Warsaw ranges)?
- Who applies for the PUBG API key, and what's the fallback timeline if approval is delayed?
- What Discord server/channel will alerts post to?
- What's the target anomaly-detection recall/precision bar for "done" on the ML side?
