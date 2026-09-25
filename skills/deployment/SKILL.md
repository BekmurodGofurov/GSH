---
name: gsh-deployment
description: Use whenever running, deploying, or changing docker-compose.yml, .env, or service configuration for GSH, or discussing how to point GSH at a new host/domain or take it to production. Covers the HOST/DOMAIN env-var pattern, why database schema changes must go through migrations instead of hand edits, and why secrets/production config are off-limits for the agent to touch — even if the user just says "deploy this" or "change the port."
---

# GSH Deployment Rules

## Running the stack locally

`docker compose up` brings up every service defined in
`docker-compose.yml` (TimescaleDB, Redis, gateway-api, ingestion-service,
alerting-service, anomaly-detection-ml, root-cause-ml, client). Useful
variants:

- `docker compose up -d` — detached.
- `docker compose up --build <service>` — rebuild a single service
  after changing its Dockerfile or dependencies.
- `docker compose logs -f <service>` — tail logs while debugging.

Every port and required setting in `docker-compose.yml` is read from
`.env` (e.g. `GATEWAY_PORT`, `TIMESCALE_PORT`, `REDIS_PORT` are marked
`:?...is required in .env`) — don't hardcode ports directly into the
compose file.

## Two environments share one box

Production (`main`, `/home/ubuntu/GSH`) and staging (`developer`,
`/home/ubuntu/GSH-staging`) run as two compose projects on the same
EC2 host; `.github/workflows/cd.yml` deploys each after CI passes on
its branch. That only works because nothing in `docker-compose.yml` is
globally unique:

- Every `container_name` is `${COMPOSE_PROJECT_NAME:-gsh}-<service>`.
  A new service must follow the same pattern — a bare
  `container_name: gsh-foo` would collide between the two stacks.
- Every published port comes from `.env`, so staging can shift them.
- Named volumes are left unprefixed; compose already scopes them to the
  project (`gsh_timescale_data` vs `gsh-staging_timescale_data`).
  Don't set an explicit `name:` on a volume or network.

Setup and troubleshooting for both are in `docs/deployment.md`.

## HOST / DOMAIN

`docker-compose.yml` builds URLs with this fallback chain:
`${HOST:-${DOMAIN:-localhost}}` — used for `FRONTEND_URL`,
`VITE_API_URL`, and `VITE_WS_URL`. In practice: set `HOST` in `.env` to
point the stack at a specific IP/hostname, set `DOMAIN` for a real
domain name, and if neither is set it falls back to `localhost`. When
changing where GSH is reachable from, change these values in `.env` —
don't edit the URLs inside `docker-compose.yml` itself.

## Schema changes go through migrations, never hand edits

If a change requires altering a table (new column, new index, changed
type), write a migration under `migrations/` — don't hand-edit
`init.sql` for an existing environment and don't run ad hoc `ALTER
TABLE` against a running database. `init.sql` only seeds a fresh
database; once an environment exists, migrations are the only path
that keeps dev, staging, and production schemas in sync with each
other and with what the application code expects.

## Secrets and production config are off-limits

Per AGENTS.md's Agent Safety section, the agent may not modify
production configuration or secrets — this includes `.env` values,
API keys, Telegram tokens, database passwords, and LLM provider keys.
Never commit them, never rewrite them into a file, and never print
their values back into a response. If a deployment task seems to
require changing one of these, stop and tell the user what needs to
change and why — let them make that edit themselves.
