# Agent Harness, Tools, and Security

## Current state: not built yet

`gateway-api/app/agent/` exists as an empty directory — no route file,
no tool definitions, no LLM client, nothing. No LLM provider SDK
(Anthropic, OpenAI, or otherwise) appears anywhere in any
`requirements.txt` in this repo. What follows is the specification this
layer needs to be built against — from [AGENTS.md](../AGENTS.md) — not
a description of running code. Update this doc as the implementation
lands so it stops being a spec and starts being documentation of what
exists.

Note: this repo's `AGENTS.md` also happens to be read by Claude Code
itself as coding-agent instructions. Don't confuse the two — that file
governs how an AI coding assistant edits this codebase; this doc is
about the in-product LLM agent GSH's backend is meant to expose to end
users (e.g. via the Telegram bot or the dashboard).

## What the agent is for

An LLM agent that can answer questions about server health using live
data — e.g. "why did the Warsaw server drop players an hour ago?" —
grounded in `server_metrics` / `server_events` / `monitored_servers`,
and able to trigger a small, safe set of write actions (currently:
publishing test events).

## Tool boundary (from AGENTS.md)

The agent must never act directly on the database or call raw SQL —
every capability it has must be a discrete, named, whitelisted
function ("agent tool") with a fixed input/output schema.

**May READ**, via tools, from:
- server metrics (`server_metrics`)
- server status (`monitored_servers.status`)
- anomalies / events (`server_events`)

**May WRITE**, via tools:
- test events only, and only by publishing to Redis Streams — never a
  direct database write. (Today, `server_metrics_stream` is the only
  Redis Stream in the codebase, and nothing consumes it yet — see
  [database.md](database.md#redis-streams). A "write test event" tool
  would need either a consumer for that stream or a new
  purpose-built stream, plus a clear definition of what a "test event"
  is downstream.)

**May NOT modify, under any circumstances:**
- `users`
- production configuration
- database schema
- secrets (API keys, Telegram tokens, DB passwords, LLM provider keys)

If a proposed capability doesn't fit inside this boundary, it doesn't
get built as a tool — that requires updating AGENTS.md first, as a
deliberate decision, not a workaround in code.

## Why the boundary is a whitelist, not a filter

The rule isn't "validate what the LLM tries to do" — it's "the LLM can
only reach code paths that were built for it." Concretely: no tool
should accept a free-form query string, build SQL from it, or pass
through to a generic "run this DB query" function. Each tool is a
fixed Python function with a fixed Pydantic schema for its arguments,
and the model can only ever call functions that exist. This is what
makes "never allow raw SQL" and "no unauthorized writes" true by
construction rather than by hoping validation catches everything.

## Testing requirement

Every new agent tool needs three tests before it ships — success,
invalid input, and database/service failure handling — see
[skills/testing/SKILL.md](../skills/testing/SKILL.md) for what each of
those needs to cover and what to do about the fact that no test
framework is set up in this repo yet.

## Suggested shape for a first implementation

Not prescriptive, but a reasonable starting point given the existing
`gateway-api` structure:

1. `gateway-api/app/agent/tools.py` — one function per tool, each
   wrapping an existing read path (e.g. reuse the same queries
   `/api/v1/servers`, `/api/v1/events` already use, rather than writing
   new SQL).
2. `gateway-api/app/agent/schemas.py` — Pydantic models for each tool's
   input/output, or reuse models from `shared_schemas` if the shapes
   already exist there.
3. A single agent entrypoint (HTTP route or internal function) that
   holds the LLM client and the fixed list of tools it's allowed to
   call — the whitelist should be enforced in code, not just by
   convention.
4. Wire the "write test event" tool to Redis only after deciding how
   test events are consumed downstream — writing to an unconsumed
   stream (like `server_metrics_stream` today) would just create a
   second orphaned write path.
