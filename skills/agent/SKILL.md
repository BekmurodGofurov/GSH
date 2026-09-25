---
name: gsh-agent
description: >
  Use this skill whenever adding a new LLM agent tool in gateway-api, extending
  the agent router, wiring the AskPanel to a new capability, or evaluating
  whether a proposed agent action is safe per AGENTS.md. Activate even when the
  user just says "add a tool" or "make the agent able to do X" without mentioning
  safety or architecture explicitly.
---

# GSH Agent Harness Rules

The agent harness exposes a controlled LLM interface inside the application.
Its design principle is a **whitelist, not a filter** — the LLM can only reach
code paths that were built for it. These rules enforce that principle.

## Where the harness lives

```
gateway-api/
  app/
    agent/
      tools.py    ← one function per tool
      schemas.py  ← Pydantic models for tool inputs/outputs and the ask endpoint
      router.py   ← POST /api/v1/agent/ask, LLM client, tool whitelist
```

The router is mounted in `gateway-api/main.py` as a standard FastAPI router.
There is no separate service — the agent runs inside `gateway-api`.

## READ / WRITE boundary (from AGENTS.md)

Before building any tool, check which side of this line it falls on:

**Agent may READ (via tools):**
- Server metrics (`server_metrics`)
- Server status (`monitored_servers.status`, ping, players)
- Anomalies and events (`server_events`)

**Agent may WRITE (via tools):**
- Test events — published to Redis Streams only, **never a direct DB write**

The existing `relabel_event` tool is an exception that AGENTS.md does not yet
cover: it writes `server_events` directly, with no authentication. Don't
copy it as a pattern for new write tools, and don't add another write tool
until the owner has decided how writes are allowed (see "Known gaps" in
`docs/agents.md`).

**Agent may NOT touch, under any circumstances:**
- `users` table or any auth data
- Production configuration or `.env` values
- Database schema
- Secrets (API keys, Telegram tokens, DB passwords, LLM provider keys)

If a requested tool doesn't fit inside the READ/WRITE boundary above, **stop**
and tell the user. That requires a conscious decision to update `AGENTS.md`,
not a workaround in code.

## How to add a new tool

### 1. Write the function in `tools.py`

Every tool is a plain async Python function. Rules:

- Accept a `db_pool` (asyncpg pool) as the first argument for DB reads, or a
  `redis_client` for write-to-stream tools.
- Accept only typed arguments matching a Pydantic schema — no `**kwargs`,
  no free-form strings that get passed to SQL.
- Use **pre-written, fixed SQL queries** — do not build query strings from
  user input. Reuse the query constants in `gateway-api/queries.py`, and put
  any query shared with a REST route there too. **Never `import main`** from
  anything under `app/`: `main.py` imports the agent router at load time, so
  that import closes a cycle that crashes the service under `python main.py`
  (how the Dockerfile starts it). `test_entrypoint.py` guards this.
- Return a plain Python dict or list that can be serialised to JSON.
- Raise a clear `ValueError` or `HTTPException` for invalid input —
  never let a raw exception propagate to the LLM context.

```python
# Example shape — do not build SQL from arguments
async def get_server_summary(db_pool) -> list[dict]:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(LATEST_SERVERS_QUERY)   # reuse existing constant
    return [dict(r) for r in rows]
```

### 2. Add Pydantic schemas in `schemas.py`

Each tool that accepts arguments needs an input schema. Output schemas are
optional but recommended for tools that return structured data.

```python
class LatencyQuery(BaseModel):
    minutes: int = Field(default=10, ge=1, le=60)
```

The agent uses these schemas to know what arguments to pass. Tight validation
here is what makes "never allow raw SQL" true by construction.

### 3. Add the tool to the whitelist in `router.py`

The whitelist is `_TOOL_REGISTRY` in `router.py`, a list of dicts. The LLM is
only shown tools on this list — it cannot call anything else, and a request
for any other name is refused with 400.

```python
_TOOL_REGISTRY = [
    ...,
    {
        "name": "get_average_latency",
        "description": "Returns average ping ... over the last N minutes. ...",  # the model reads this
        "fn": tools.get_average_latency,
        "schema": schemas.LatencyQuery,       # None if the tool takes no arguments
        "parameters": {                       # JSON schema shown to Gemini
            "type": "object",
            "properties": {
                "minutes": {"type": "integer", "description": "Time window in minutes (1–60). Default is 10."},
                "server_id": {"type": "string", "description": "Optional. ..."},
            },
            "required": [],
        },
    },
]
```

`parameters` is what the model follows; `schema` is what the server enforces.
Keep their names, types and limits in agreement — `RelabelRequest.event_id`
was once `str` while `parameters` said `integer`, and every relabel failed
validation.

Adding a function to `tools.py` without adding it here does nothing — the LLM
will never know the function exists.

### 4. Write three tests (required by AGENTS.md)

See `skills/testing/SKILL.md` for the full testing guide. Every agent tool
must have before it ships:

1. **Success test** — valid input, assert expected output and any expected side
   effect (e.g., Redis stream entry for write tools).
2. **Invalid input test** — missing field, wrong type, out-of-range value.
   Assert a validation error is returned, not a crash.
3. **DB/service failure test** — mock the DB pool or Redis client to raise.
   Assert the tool returns a clear structured error, not a raw exception.

## The ask endpoint

`POST /api/v1/agent/ask` receives:

```json
{ "question": "What is the average latency on the Warsaw server?" }
```

Returns:

```json
{
  "answer": "The average latency on the Warsaw server over the last 10 minutes is 42.3 ms.",
  "tool_used": "get_average_latency"
}
```

The endpoint:
1. Sends the question + tool descriptions to the LLM.
2. If the LLM requests a tool call, executes the matching whitelisted function.
3. Sends the tool result back to the LLM for a final grounded answer.
4. Returns the answer to the client.

The LLM never sees raw SQL, raw DB credentials, or anything outside the tool
outputs it explicitly requested.

## LLM API key

The LLM API key is read from the `AGENT_LLM_API_KEY` environment variable at
startup. It is listed in `.env.example` as an empty placeholder. It must never
be committed, logged, or returned in any response. If missing at startup,
`router.py` raises `ValueError` the same way `DB_URL` does in `main.py`.

## Do not add open-ended tools

A tool like `run_query(sql: str)` or `search(query: str, table: str)` is an
injection vector — it violates the whitelist principle even if you add
validation on top. If a legitimate use case requires a new data shape, write a
new named function for it.
