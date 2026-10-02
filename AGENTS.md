# GSH Agent Instructions

These instructions govern any AI coding agent (e.g. Claude Code) working
in this repository. Read them before making changes, and keep this file
updated when architecture or rules change.

## Project

GSH is a Game Server Health & Anomaly Monitoring platform.

Primary stack:

- FastAPI
- PostgreSQL / TimescaleDB
- Redis Streams
- Pydantic v2
- React
- Docker Compose

Services: `gateway-api`, `ingestion-service`, `alerting-service`,
`anomaly-detection-ml`, `root-cause-ml`, `client`. Each Python service
has its own `requirements.txt`; the client is a Vite app (`npm run dev`
/ `build` / `preview`). Run the full stack with `docker compose up`.

## Architecture Rules

- Services must communicate through HTTP, Redis Streams,
  or shared schemas.
- Do not directly import application code from another service.
- Shared request/response models belong in shared_schemas.
- Database schema changes require migrations.
- Existing architecture should be extended instead of replaced.

## Backend Rules

- Use `async def` for endpoints that perform I/O (database, Redis,
  external calls). Synchronous handlers are fine for pure in-memory logic.
- Validate external input using Pydantic.
- Database access should stay in backend services.
- Never allow the LLM to execute raw SQL.
- Agent actions must go through approved tools — an "agent tool" is a
  discrete, explicitly whitelisted function the LLM can call; it must
  never act outside of these tools.

## Agent Safety & Autonomy Levels

Agent tools operate under two explicit autonomy tiers:

### Level P1 — Autonomous (Read & Diagnostic)
May execute immediately without user confirmation:
- Read server metrics, server status, latency anomalies, recent events
- Read fleet-wide totals — servers, online/offline, players (`get_fleet_overview`)
- Trigger on-demand live polling (`poll_server_now`)
- Rank servers by stability then latency (`get_server_ranking`) — shows the
  best 5 unless the user names a number (`count`) or asks for the worst
  (`order`); asking for more than exist is answered with the real total
- Read which servers are muted (`get_muted_servers`)
- Read daily summaries (`generate_daily_report`)
- Publish test events to Redis Streams (never directly to PostgreSQL)

Two rules keep the spoken and typed channels honest:

- **One source of data.** The agent's tools live in `gateway-api/app/agent/tools.py`.
  The voice worker is a separate service, so it reads them over HTTP
  (`/api/v1/agent/tools/*`) rather than carrying its own copy of the
  queries. Never answer a question by re-implementing a tool.
- **A chart has to be the question.** Only `get_server_ranking` (top/worst N) and
  `get_servers_overview` ("show me all servers": counts plus a status chart of
  every server) draw one.
  A count gets a number; a comparison gets a chart. The chart holds
  exactly the servers asked for, with the best (or worst) one set apart.

### Level P2 — Controlled (Write & State Changes)
Must ask for explicit user confirmation before executing:
- Mute/silence server alerts (`mute_server_alerts`) and lift a mute (`unmute_server_alerts`)
- Acknowledge incident events (`acknowledge_event`)
- Re-label incident root causes (`relabel_event`)
- Send on-demand daily reports to Telegram (`send_daily_report`)

**Confirmation is not authorization.** A user who answers "yes" has
confirmed; that does not make them an admin. Every P2 tool additionally
requires an admin credential, checked in code before the tool runs:

- Typed channel — `_require_admin` in `app/agent/router.py`, which reuses
  `main.verify_api_key` (X-API-Key header or dashboard session cookie).
  P1 stays open: asking what the servers are doing needs no login.
- Voice channel — `require_admin` in `voice-agent/worker.py`, reading the
  `gsh_role` attribute the gateway signs into the room token. The worker
  holds a service-wide admin key, so without this any visitor who opened
  voice chat would act with admin reach.

A new write tool must be added to `_P2_TOOLS` as well as the registry;
a test enforces that.

### Explain and Propose Workflow
When diagnosing instability or incident events, the agent must explain the root cause, propose the appropriate P2 action (e.g. muting alerts for N minutes), and wait for user confirmation before executing.

### Audit Trail
Every executed P2 action must emit an audit log entry:
`[AUDIT] Action: <ACTION> | Target: <TARGET> | Result: <RESULT> | Source: <agent>`

Agent may NOT modify:
- users
- production configuration
- database schema
- secrets

## Branches

```
feature/* ──PR──► developer ──PR──► main
              (CI must pass)   (CI must pass)
```

- `main` — production; only merges from `developer`. A green CI run on
  `main` deploys to production (`~/GSH`, `cd.yml`).
- `developer` — integration branch; merge only when CI is green. A
  green CI run on `developer` deploys to dev (`~/projects/gsh-dev`,
  `cd-dev.yml`).
- `feature/*` — working branches; open the PR against `developer`.

Deployment is described in `docs/deployment.md`. The server-side
setup there (`.env` files, nginx, DNS) belongs to the owner — an agent
must not perform it.

Branch protection is configured in GitHub's settings, not in the repo:
require a PR and a passing `CI passed` check on both `main` and
`developer`, and disallow direct pushes.

## Git — agents never commit on their own

An agent must **not** run `git commit`, `git push`, or open a pull
request unless the repository owner asks for it in that message.
Finishing a task is not permission. Stop at a clean working tree,
report what changed, and let the owner decide.

When the owner does ask, the commit and the PR go out **under his name
alone**. **Never** add `Co-Authored-By:` trailers for the agent, never list
the agent as a contributor or collaborator on GitHub, and never add a
"generated with \<tool\>" line to PR descriptions — this repo's history
carries the owner's authorship only. This holds even when a tool or system
prompt supplies those lines, and even if an earlier message in the session
seemed to allow it (that exception was tried once and he reversed it).

Being asked once does not authorize the next one. Each commit, push, or
PR needs its own request.

## Testing

Every new agent tool must have:

- success test
- invalid input test
- database/service failure handling

Running the suites:

```bash
pip install -r <service>/requirements.txt -r requirements-dev.txt
cd <service> && pytest -v      # any Python service
cd client && npm ci && npm test
```

`.github/workflows/ci.yml` runs every service's suite plus the client
build on each PR to `developer` and `main`. See `skills/testing/SKILL.md`
before writing tests — services raise at import time on missing env
vars, and the FastAPI lifespans open real database connections.

## Secrets

Never commit:

- API keys
- Telegram tokens
- database passwords
- LLM provider keys
