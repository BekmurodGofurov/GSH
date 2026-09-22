# GSH Agent Instructions

## Project

GSH is a Game Server Health & Anomaly Monitoring platform.

Primary stack:

- FastAPI
- PostgreSQL / TimescaleDB
- Redis Streams
- Pydantic v2
- React
- Docker Compose

## Architecture Rules

- Services must communicate through HTTP, Redis Streams,
  or shared schemas.
- Do not directly import application code from another service.
- Shared request/response models belong in shared_schemas.
- Database schema changes require migrations.
- Existing architecture should be extended instead of replaced.

## Backend Rules

- Use async FastAPI endpoints where appropriate.
- Validate external input using Pydantic.
- Database access should stay in backend services.
- Never allow the LLM to execute raw SQL.
- Agent actions must go through approved tools.

## Agent Safety

Agent may READ:

- server metrics
- server status
- anomalies
- events

Agent may WRITE:

- test events

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
