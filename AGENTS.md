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

## Agent Safety

Agent may READ:

- server metrics
- server status
- anomalies
- events

Agent may WRITE:

- test events — published to Redis Streams only, never written directly
  to the database

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

- `main` — production; only merges from `developer`.
- `developer` — integration branch; merge only when CI is green.
- `feature/*` — working branches; open the PR against `developer`.

Branch protection is configured in GitHub's settings, not in the repo:
require a PR and a passing `CI passed` check on both `main` and
`developer`, and disallow direct pushes.

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
