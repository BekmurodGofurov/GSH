---
name: gsh-testing
description: Use whenever adding a new LLM agent tool or a new backend endpoint in the GSH repo. AGENTS.md requires every new agent tool to ship with a success test, an invalid-input test, and a database/service-failure test — this skill covers what those three tests need to check and, since no test framework is wired up in any GSH service yet, how to handle that gap instead of silently skipping tests or guessing at a framework.
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

## Before writing a single test: check what already exists

No test framework is set up anywhere in this repo yet — there's no root
`pytest.ini`/`pyproject.toml` test config and no `tests/` directory in
any service as of now. So don't assume pytest, don't assume a fixture
pattern, and don't silently skip testing either. Instead:

1. Look inside the specific service you're changing (e.g.
   `gateway-api/requirements.txt`, or a `tests/`/`conftest.py` folder)
   for an existing test setup.
2. **If you find one**, follow its existing convention — same runner,
   same fixture/mocking style, same file layout.
3. **If you don't find one**, don't invent a test framework choice
   unilaterally and don't quietly skip the tests either. Tell the user
   directly: "this service has no test infrastructure yet — do you
   want me to set up pytest (with `pytest-asyncio` + `httpx.AsyncClient`
   for the FastAPI services) before writing these tests, or handle it
   differently?" Let them decide before you add new dependencies.

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
