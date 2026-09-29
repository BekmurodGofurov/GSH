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
Its design principle is a **whitelist, not a filter**: the LLM can only reach
code paths that were built for it. These rules enforce that principle.

## Where the Harness Lives

```
gateway-api/
  app/
    agent/
      tools.py    (one async function per tool)
      schemas.py  (Pydantic models for tool inputs and endpoint payloads)
      router.py   (POST /api/v1/agent/ask, LLM client, tool registry)
```

The router is mounted in `gateway-api/main.py`.

## Autonomy Tiers (from AGENTS.md)

Every agent tool must explicitly belong to one of two autonomy tiers:

### Level P1: Autonomous (Read & Diagnostic)
Tools that read data or execute safe diagnostic queries without modifying server or alert states.
May execute immediately without user confirmation:
- Read server metrics and status (`get_server_summary`)
- Read incident events and anomalies (`get_recent_events`)
- Calculate latency buckets (`get_average_latency`)
- Trigger immediate live server polls (`poll_server_now`)
- Read cached daily reports (`generate_daily_report`)
- Publish test events to Redis Streams only (never directly to PostgreSQL)

### Level P2: Controlled (Write & State Changes)
Tools that modify server configuration, incident states, or suppress alerts.
Must require explicit user confirmation before executing:
- Temporarily silence server alerts (`mute_server_alerts`)
- Acknowledge incident events (`acknowledge_event`)
- Re-label incident root causes (`relabel_event`)
- Send on-demand daily reports to Telegram (`send_daily_report`)

### Explain and Propose Workflow
When diagnosing instability or incident events:
1. Explain the root cause based on data returned by P1 tools.
2. Propose the appropriate P2 action (e.g. muting alerts for N minutes).
3. Wait for explicit user confirmation before calling the P2 tool.

### Audit Trail
Every executed P2 action must emit an audit log entry:
```
[AUDIT] Action: <ACTION> | Target: <TARGET> | Result: <RESULT> | Source: <agent>
```

Agent may NEVER modify:
- `users` table or authentication records
- Production configuration or secrets
- Database schema

## How to Add a New Tool

### 1. Write the Function in `tools.py`

Every tool is an async Python function:
- Accept `db_pool` (asyncpg pool) as first argument for DB access, or call internal services via HTTP (`httpx`).
- Accept strictly typed arguments matching a Pydantic schema. Never use `**kwargs` or free-form SQL strings.
- Use pre-written parameterised SQL queries. Reuse queries in `gateway-api/queries.py`.
- Never `import main` from `app/` (avoids circular import crashes).
- Return a plain Python dict or list serialisable to JSON.
- Raise `HTTPException` for client-side errors (e.g. 404 for missing IDs).

### 2. Add Pydantic Schemas in `schemas.py`

Every tool with arguments requires an input schema with strict validation bounds:

```python
class MuteRequest(BaseModel):
    server_id: str
    minutes: int = Field(ge=1, le=10080)
    reason: str | None = None
```

### 3. Register the Tool in `router.py`

Add an entry to `_TOOL_REGISTRY`:
- `name`: exact tool name.
- `description`: clear functional description the model reads. For P2 tools, state in description that confirmation is required.
- `fn`: callable in `tools.py`.
- `schema`: Pydantic model class (or `None`).
- `parameters`: JSON schema dictionary matching the Pydantic schema. Keep both in sync.

If the tool is P2, verify audit logging is executed after tool execution in `router.py`.

### 4. Write Three Tests (Required by AGENTS.md)

Every agent tool must have:
1. **Success test**: valid input, assert expected result.
2. **Invalid input test**: invalid bounds or types rejected by Pydantic before DB is touched.
3. **DB / Service failure handling**: simulated DB or connection error raises clean exception without crashing the service.

Run tests:
```bash
cd gateway-api && pytest tests/test_agent_tools.py -v
```

## Security Constraints

- A tool like `run_query(sql: str)` or `execute_command(cmd: str)` is strictly prohibited.
- The LLM context never receives credentials, raw connection strings, or internal secrets.
- Transient model provider errors (503) are retried with backoff. Quota errors (429) are surfaced immediately as 502.
