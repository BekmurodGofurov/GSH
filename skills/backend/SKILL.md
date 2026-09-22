---
name: gsh-backend
description: Enforces GSH's backend architecture and agent-safety rules. Use this whenever writing or editing a FastAPI endpoint, backend service code, or an LLM agent tool in gateway-api, ingestion-service, alerting-service, anomaly-detection-ml, or root-cause-ml — even if the user just says "add an endpoint" or "add a tool" without mentioning rules or architecture explicitly.
---

# GSH Backend Rules

These rules exist so services stay independently deployable and the LLM
agent can't do anything unsafe by accident. Apply them any time you touch
backend code, not just when the user asks about architecture.

## Async for I/O, sync is fine otherwise

Use `async def` for any endpoint or function that awaits the database,
Redis, or an external HTTP call. FastAPI *can* run a sync `def` handler
in a threadpool, but that ties up a worker thread per request — under
load that threadpool is a much smaller resource than the event loop.
Pure in-memory logic (no I/O) can stay `def`; there's nothing to gain
from `async` there.

## Validate all external input with Pydantic v2

Anything entering from outside the process — HTTP request bodies, query
params, a message read off a Redis Stream — must be parsed into a
Pydantic model before it touches business logic. Don't hand a raw
`dict` or `request.json()` result to a service function. This is the
one gate that keeps malformed or adversarial input (including input
shaped by an LLM) from reaching the database layer.

## Database access stays inside backend services

Only backend services (gateway-api, ingestion-service, alerting-service
— wherever a given piece of data is owned) talk to Postgres/TimescaleDB
directly. `anomaly-detection-ml` and `root-cause-ml` should receive data
over HTTP or Redis Streams, not open their own connection to tables they
don't own. This keeps one place responsible for each table's access
patterns and migrations.

## The LLM agent never writes or executes raw SQL

No string-built queries, no "let the agent draft a WHERE clause."
Every path the agent can reach must end in a fixed, pre-written query or
service function with a known shape. This is a hard line, not a style
preference — an LLM constructing SQL is an injection vector even when
it's "just reading."

## Agent actions go through approved tools only

Every capability exposed to the LLM agent (see `gateway-api/app/agent/`)
must be a discrete, named function with a fixed input/output schema —
never open-ended code execution or query building. Before adding a new
tool, check it against AGENTS.md's Agent Safety section:

- READ tools may only cover: server metrics, server status, anomalies,
  events.
- WRITE tools may only cover: test events, and only by publishing to
  Redis Streams — never a direct database write.
- Never build a tool that can touch users, production configuration,
  database schema, or secrets.

If a requested tool doesn't fit inside those boundaries, stop and flag
it to the user — that's a decision to update AGENTS.md, not something
to route around in code.

## Cross-service communication

Services only talk to each other over HTTP, Redis Streams, or shared
schemas. Never `import` another service's application code directly
(e.g. gateway-api importing a module from ingestion-service). If two
services need the same request/response shape, define it once in
`shared_schemas` and import that from both sides — don't duplicate the
model.

## Quick checklist before opening a PR

- [ ] I/O-bound endpoints are `async def`
- [ ] External input goes through a Pydantic model
- [ ] No cross-service imports of application code
- [ ] No raw SQL reachable by the agent
- [ ] Any new agent tool fits the AGENTS.md READ/WRITE boundaries
- [ ] Shared models live in `shared_schemas`, not duplicated
