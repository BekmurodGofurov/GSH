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

## Testing

Every new agent tool must have:

- success test
- invalid input test
- database/service failure handling

## Secrets

Never commit:

- API keys
- Telegram tokens
- database passwords
- LLM provider keys
