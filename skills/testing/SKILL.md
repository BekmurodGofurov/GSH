---
name: gsh-testing
description: Use whenever adding a new LLM agent tool or a new backend endpoint in the GSH repo. AGENTS.md requires every new agent tool to ship with a success test, an invalid-input test, and a database/service-failure test — this skill covers what those three tests need to check, and the repo-specific traps in writing them: every service raises at import time on missing env vars, and every FastAPI lifespan opens real Postgres/Redis connections.
---

# GSH Testing Rules

## Why agent tools need three specific kinds of test

An agent tool isn't called by a careful developer reading the docs —
it's called by an LLM deciding on its own when and how to invoke it.
That changes what "tested" means:

1. **Success test** — the tool does what it claims on valid input.
   Table stakes, same as any other code.
2. **Invalid input test** — the model calling the tool can hallucinate
   arguments, pass the wrong type, or send an out-of-range value.
   The tool needs to reject that cleanly (a validation error the agent
   can recover from) rather than throwing an unhandled exception or,
   worse, silently doing the wrong thing.
3. **Database/service failure test** — Postgres or Redis being briefly
   unavailable shouldn't crash the agent loop or produce a response
   that looks successful but isn't. Simulate the dependency failing
   (mock the DB/Redis call to raise) and assert the tool surfaces a
   clear, structured failure instead of a stack trace or silent
   no-op.

The same three categories are worth applying to new backend endpoints
too — the reasoning is the same, just with an HTTP caller instead of an
LLM caller.

## The setup that already exists

Every Python service has `pytest.ini` + `tests/` at its own root, and
the client uses Vitest. Follow the existing convention rather than
introducing a second one:

```bash
cd <service> && pytest -v      # any Python service
cd client && npm test          # Vitest
```

- Test tooling lives in the **root `requirements-dev.txt`**, not in the
  services' `requirements.txt` — those are what the Dockerfiles install,
  and production images should not ship a test runner. Install both:
  `pip install -r <service>/requirements.txt -r requirements-dev.txt`.
- Each service's `pytest.ini` sets `pythonpath = .` so tests import the
  service modules directly (`from main import ...`). `shared_schemas`
  is the exception: it sets `pythonpath = ..` because it is imported as
  a package.
- `.github/workflows/ci.yml` runs all of this per service on every PR to
  `developer` and `main`, on the same Python version as that service's
  Dockerfile.

## Two traps specific to this repo

**1. Services raise at import time on missing env vars.** `gateway-api`
needs `DB_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `FRONTEND_URL`;
`ingestion-service` needs `DB_URL`, `REDIS_URL`, `FRONTEND_URL`;
`root-cause-ml` imports `train.py`, which needs `DB_URL`. Worse,
`alerting-service/config.py` calls `sys.exit(1)` — that kills the whole
pytest run, not just one test. So seed the env with dummies at the **top
of `tests/conftest.py`**, before any import of the service module. A
fixture is too late; conftest is imported before the test modules, but
module-level imports inside conftest still run in file order.

**2. `TestClient` runs the app's lifespan**, which opens real Postgres
and Redis connections and (in `ingestion-service`) starts the polling
loop. For `gateway-api` and `ingestion-service`, drive the app through
`httpx.ASGITransport` instead — it skips lifespan — and install a fake
pool over the module global. `anomaly-detection-ml` and `root-cause-ml`
define no lifespan, so plain `TestClient` is fine there.

One more: `gateway-api` sets its admin session cookie with
`secure=True`, so an `AsyncClient` on an `http://` base URL will
silently never send it back. Use `base_url="https://test"`.

## Shape of the three tests, once infra exists

- **Success**: call the tool/endpoint with a valid, representative
  payload; assert the expected result and any expected side effect
  (e.g. an event actually published to the Redis stream).
- **Invalid input**: call it with a missing field, wrong type, and an
  out-of-range/nonsensical value; assert a validation error is raised
  or returned — never a raw exception leaking internals.
- **Failure handling**: mock the DB session or Redis client to raise
  (connection error, timeout), call the tool, and assert it returns a
  clear error rather than crashing the caller or agent loop.
