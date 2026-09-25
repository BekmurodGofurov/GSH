# Agent Harness, Tools, and Security

GSH has an in-product LLM agent: the **Ask** panel in the dashboard. A
user asks a question in plain language ("What is the average latency
right now?"), the agent calls one of a fixed set of tools against the
live database, and answers from what the tool returned. It can also
perform one write action — re-labelling an incident's root cause.

Not to be confused with [AGENTS.md](../AGENTS.md): that file governs how
an AI *coding* assistant edits this repository. This doc is about the
agent that runs inside the product, for end users.

## Where it lives

The agent is part of `gateway-api`, not a separate service.

| File | What it holds |
|---|---|
| `gateway-api/app/agent/router.py` | `POST /api/v1/agent/ask`, the Gemini client, the tool whitelist (`_TOOL_REGISTRY`), retry and error handling |
| `gateway-api/app/agent/tools.py` | one async function per tool, each running fixed SQL |
| `gateway-api/app/agent/schemas.py` | Pydantic models: the request/response of the endpoint and each tool's arguments |
| `gateway-api/queries.py` | SQL shared by the REST API and the tools (`LATEST_SERVERS_QUERY`) |
| `gateway-api/main.py` | mounts the router (`app.include_router(agent_module.router)`) |
| `client/src/components/common/AskPanel.jsx` | the slide-in Ask panel and its floating button |
| `client/src/services/api.js` | `api.askAgent(question)` |
| `gateway-api/tests/test_agent_tools.py` | tool and endpoint tests |

## How a question is answered

```
AskPanel ──POST /api/v1/agent/ask {question}──► gateway-api
                                                    │
         ┌──────────────────────────────────────────┘
         ▼
  1. Gemini call #1: question + system instruction + tool declarations
         │
         ├─ no tool requested ──► answer = model text ──────────────┐
         │                                                          │
         ▼ function_call {name, args}                               │
  2. name in _TOOL_REGISTRY?  no ──► 400                            │
  3. args through the tool's Pydantic schema  invalid ──► 422       │
  4. run the tool function against the DB pool                      │
  5. Gemini call #2: question + tool result as JSON text,           │
     no tools offered, "answer using only the tool data"            │
         │                                                          │
         ▼                                                          ▼
  {answer, tool_used} ◄─────────────────────────────────────────────┘
```

Details worth knowing:

- **One tool per question.** Only the first `function_call` in the
  model's reply is executed, and call #2 offers no tools. A question
  that needs two tools gets answered from one of them (see
  [Known gaps](#known-gaps)).
- **The tool result goes back as text, not as a function response.**
  Gemini rejects a replayed `functionCall` part without the
  `thought_signature` it was issued with, and that signature is not
  available on the parsed response. Inlining the JSON works across
  model revisions. The comment in `router.py` explains this.
- **No memory.** Each request is independent; there is no
  conversation history on the server or in the panel.
- **Temperature 0.1** on both calls, to keep answers factual.
- The Gemini SDK is synchronous, so each call runs in
  `asyncio.to_thread` — calling it inline would block the event loop,
  the dashboard WebSocket included.

## Tools

| Tool | Kind | Arguments (validated) | What it does |
|---|---|---|---|
| `get_server_summary` | read | none | every monitored server with its latest metric — the same `LATEST_SERVERS_QUERY` that `GET /api/v1/servers` serves |
| `get_recent_events` | read | `limit` 1–50, default 10 (`EventQuery`) | latest rows from `server_events`: type, root cause, label source, message, anomaly score, diagnosis |
| `get_average_latency` | read | `minutes` 1–60, default 10; optional `server_id` (`LatencyQuery`) | 1-minute buckets of average ping and players per server — the same query as `GET /api/v1/analytics/ping-buckets`, plus the optional server filter |
| `relabel_event` | **write** | `event_id` int > 0; `root_cause` one of `SERVER_CRASH`, `HIGH_LATENCY`, `DDOS_ATTACK`, `REGIONAL_OUTAGE`, `PLAYER_DROP`, `MAINTENANCE` (`RelabelRequest`) | `UPDATE server_events SET root_cause = $1, label_source = 'manual'` — the same write as `POST /api/v1/events/{id}/label`. 404 if the event doesn't exist. The change shows up on the dashboard within one WebSocket tick (3s). |

## Safety model

The rule is a **whitelist, not a filter**: the model can only reach
code paths that were built for it.

- **The whitelist is enforced in code.** The model is shown only the
  tools in `_TOOL_REGISTRY`, and a request for any other name is
  refused with 400. A function in `tools.py` that isn't registered is
  invisible to the model.
- **Arguments are validated before the database is touched.** Each
  registered tool names its Pydantic schema; a hallucinated value
  (wrong type, out of range, unknown root cause) is a 422.
- **The model never writes SQL.** Every tool runs a fixed,
  parameterised query; arguments are only ever bound as `$1`, `$2`.
  `get_average_latency` has two fixed queries (with and without the
  server filter) rather than one built from input. No tool takes a
  free-form query or table name.
- **The model never sees credentials or SQL** — only the tool
  declarations and the JSON a tool returned.

The boundary itself comes from [AGENTS.md](../AGENTS.md):

- **May read:** server metrics, server status, anomalies, events.
- **May write:** test events, published to Redis Streams only.
- **May not modify:** users, production configuration, database
  schema, secrets.

`relabel_event` is a direct database write, which that list does not
allow — see [Known gaps](#known-gaps). A new capability that doesn't
fit the boundary needs AGENTS.md updated first, as a deliberate
decision, not a workaround in code.

## Configuration

| Variable | Required | Meaning |
|---|---|---|
| `AGENT_LLM_API_KEY` | **yes** | Gemini API key ([aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)). `router.py` raises at import without it, and `main.py` imports the router at load time, so the whole gateway refuses to start — not just the agent. `docker-compose.yml` marks it `:?` so the error shows once, up front. |
| `AGENT_LLM_MODEL` | no | Gemini model id. Empty uses the code default, `gemini-3.6-flash`. When Google retires a model the API answers 404 naming the replacement — change this value and restart `gateway-api`, no code change needed. |

**Cost:** every question that uses a tool is two Gemini requests. On
the free tier (20 requests per day per model) that is about **10
questions a day**. Enable billing, or give dev its own key (see
[deployment.md](deployment.md#dev-environment)), before relying on it for a
demo.

## Errors

The endpoint never lets a provider or tool exception escape as a bare
500: those are rendered outside the CORS middleware, and the browser
would report a misleading CORS error instead of the real cause.

| Status | When |
|---|---|
| 422 | `question` empty or longer than 500 characters |
| 503 | the database pool isn't ready yet |
| 400 | the model asked for a tool that isn't whitelisted |
| 422 | the model passed arguments the tool's schema rejects |
| 404 | `relabel_event` on an event id that doesn't exist |
| 500 | a tool raised (e.g. the database query failed) — `Tool '<name>' failed: …` |
| 502 | the LLM provider failed — `LLM provider error for model '<id>': …`. The message names the cause (bad key, retired model, quota). |

Provider retries: **503** (model temporarily overloaded) is retried up
to 3 attempts with 1s and 2s backoff. **429** is *not* retried — on this
API it usually means the quota for the period is spent, and each retry
would only burn more of it.

## Frontend

`AskPanel` is mounted once in `App.jsx` and rendered into
`document.body` through a portal (see [frontend.md](frontend.md)). It
shows a floating button bottom-right, example prompts, a loading state,
the answer, and **"Tool used: …"** under it so it is visible which tool
grounded the answer. Ctrl/Cmd+Enter sends.

`api.askAgent()` uses a 15s timeout instead of the usual 3.5s, since
two LLM round trips are much slower than a database read.

## Adding a tool

Step by step, with the rules, in
[skills/agent/SKILL.md](../skills/agent/SKILL.md). In short:

1. An async function in `tools.py` taking `db_pool` first, running
   fixed SQL. Shared SQL goes in `queries.py` — **never** `import main`
   from `app/`: `main` imports the router at load time, and the cycle
   crashes the service under `python main.py`.
2. A Pydantic schema in `schemas.py` for its arguments.
3. An entry in `_TOOL_REGISTRY` in `router.py`: `name`, a
   `description` the model will read, `fn`, `schema`, and the
   JSON-schema `parameters` shown to Gemini. Keep `parameters` and the
   Pydantic schema in agreement — the model follows `parameters`, the
   server enforces the schema.
4. The three tests AGENTS.md requires — success, invalid input,
   database failure — in `tests/test_agent_tools.py`
   ([skills/testing/SKILL.md](../skills/testing/SKILL.md)).
5. An example prompt in `AskPanel` if it's worth discovering.

## Tests

```bash
cd gateway-api && pytest tests/test_agent_tools.py -v
```

Covered: each tool's success, invalid-input and database-failure cases;
and the endpoint end to end with Gemini mocked — a tool call answered
from the tool result, an empty question, the database not ready, a
provider error surfacing as 502, a 503 being retried, and a 429 not
being retried.

Not yet covered: the refusal of an unknown tool name, a 422 for bad
model-supplied arguments through the endpoint, and anything about
authentication (there is none yet).

## Known gaps

What the harness does not do yet, roughly in order of importance.

1. **No authentication.** `/api/v1/agent/ask` is open, and the Ask
   panel is shown to every visitor. `POST /api/v1/events/{id}/label`
   requires an admin, but anyone can make the same write through the
   agent. It also means anyone can spend the Gemini quota.
2. **The write action breaks the AGENTS.md boundary.** AGENTS.md allows
   writing test events to Redis Streams only; `relabel_event` updates
   `server_events` directly. Either AGENTS.md is updated to allow it
   (with conditions — admin only, confirmation, audit) or the tool
   changes.
3. **Agent labels look like human labels.** The tool sets
   `label_source = 'manual'`, and `root-cause-ml/train.py` trains on
   `server_events.root_cause`. A relabel made through the agent —
   today, by anyone — becomes training data indistinguishable from an
   admin's correction. A separate value such as `'agent'` would let
   training filter it.
4. **No confirmation and no audit trail.** The write runs as soon as
   the model asks for it, and nothing records who asked or what
   changed.
5. **One tool per question, no memory.** "Summarize what's happening
   on the dashboard" needs servers, events and latency, but gets one.
   "Relabel the last DDoS event" needs `get_recent_events` then
   `relabel_event`, so it can't be done in one question. A real loop
   (call a tool, feed the result back, allow another, up to N steps)
   fixes both.
6. **Event ids aren't shown in the UI,** so a user has to ask for recent
   events first to find the id to relabel.
7. Small edge cases in `router.py`: a tool that has a schema but is
   called with no arguments skips validation (so `relabel_event` with
   no args is a 500, not a 422); a reply with no candidates or no
   content (e.g. blocked by Gemini's safety filter) raises instead of
   returning a clear error; and with retries, a slow provider can take
   longer than the panel's 15s timeout.
