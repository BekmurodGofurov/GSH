# Development Workflow

How to work on GSH day to day: the edit/run loop, the branch and PR
rules, the test suites, and what to touch when adding code.

First run of the stack is covered in [setup.md](setup.md) — copy
`.env.example` to `.env`, fill it in, `docker compose up -d --build`.
Shipping to the server is [deployment.md](deployment.md).

## The edit/run loop

None of the services bind-mount your source into the container. The
Dockerfiles `COPY` the code in, so **editing a file changes nothing
until the image is rebuilt**:

```bash
docker compose up -d --build gateway-api    # rebuild one service
docker compose logs -f gateway-api          # watch it come back
```

That is fine for a one-off change, and slow if you're iterating. For
real work, run the service you're editing natively against the
Dockerised database and Redis:

```bash
docker compose up -d timescaledb redis      # dependencies only
cd gateway-api
pip install -r requirements.txt -r ../requirements-dev.txt
DB_URL=postgresql://postgres:<password>@localhost:5434/game_monitor \
REDIS_URL=redis://localhost:6379 \
ADMIN_USERNAME=admin ADMIN_PASSWORD=admin \
FRONTEND_URL=http://localhost:3000 \
AGENT_LLM_API_KEY=<key> \
python main.py
```

The port in `DB_URL` is the **host** port (`TIMESCALE_HOST_PORT` in
your `.env`), not the container port — from outside Docker you go
through the published port. `ingestion-service/.env.example` shows the
same idea; note that no service calls `load_dotenv()`, so those files
are documentation for your shell or IDE, not something that loads
itself.

Every Python service reads its required env vars at **import** time and
raises a `ValueError` naming what's missing, so you find out
immediately rather than on the first request.

### Frontend

The `client` container runs `vite dev` with no bind mount either, so
develop the frontend natively — you get hot reload, and it can talk to
the Dockerised gateway:

```bash
docker compose up -d           # backend
cd client
cp .env.example .env           # then point VITE_API_URL at your gateway
npm install
npm run dev
```

`client/vite.config.js` throws at startup if `VITE_API_URL` or
`CLIENT_PORT` is empty, and it uses them to set up the `/api` and `/ws`
dev-server proxies, so the dev server and the built app hit the same
paths.

## Branches and PRs

```
feature/* ──PR──► developer ──PR──► main
              (CI must pass)   (CI must pass)
```

- `feature/*` — your working branch. Open the PR against `developer`.
- `developer` — integration branch. Merge only when CI is green.
- `main` — production. Only merges from `developer`, and every push to
  it **deploys** ([deployment.md](deployment.md)).

Branch protection lives in GitHub's settings, not in the repo: a PR and
a passing `CI passed` check are required on both `main` and
`developer`, and direct pushes are disallowed.

**Agents never commit on their own.** An AI agent must not run `git
commit`, `git push`, or open a PR unless the owner asks for it in that
message — finishing a task is not permission, and being asked once does
not cover the next one. Commits and PRs go out under the owner's name
alone, with no co-author or "generated with" trailers. See
[AGENTS.md](../AGENTS.md).

## Tests

```bash
pip install -r <service>/requirements.txt -r requirements-dev.txt
cd <service> && pytest -v      # any Python service

cd client && npm ci && npm test
```

`requirements-dev.txt` holds the shared test tooling (pytest,
pytest-asyncio, httpx) deliberately kept out of the services'
`requirements.txt`, so production images don't ship a test runner.
Each Python service has its own `pytest.ini` and `tests/`; the client
uses Vitest with tests under `client/src/__tests__/`.

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs every
service's suite in a matrix (each on the Python version its Dockerfile
pins — 3.11 everywhere except `alerting-service` on 3.12), plus the
client's tests and a production build. The `CI passed` job aggregates
them and is the check branch protection requires.

Two traps specific to this repo, both covered in
[skills/testing/SKILL.md](../skills/testing/SKILL.md): services raise at
import time on missing env vars, and the FastAPI lifespans open real
Postgres/Redis connections. Test modules therefore have to seed the
environment and neutralise the lifespan before importing the app —
follow the existing `tests/conftest.py` in the service you're working
in rather than inventing a second pattern.

Every new **agent tool** must ship with three tests: success, invalid
input, and database/service failure. The same three are worth writing
for a new endpoint.

## Rules that shape the code

From [AGENTS.md](../AGENTS.md) — these are the ones that actually come
up while writing code:

- **No cross-service imports.** Services talk over HTTP, Redis Streams,
  or shared schemas. Never `import` another service's application code.
- **Shared request/response models go in `shared_schemas/`.** Services
  reach them through a `sys.path` shim near the top of the file
  (`sys.path.insert(0, <repo root>)`) so the same import works inside
  the container — where the Dockerfile copies `shared_schemas/` in
  beside the service — and when running standalone from the repo.
- **`async def` for handlers that do I/O** (database, Redis, outbound
  HTTP). Pure in-memory logic can stay synchronous.
- **Validate every external input with Pydantic v2.**
- **Database access stays inside backend services** — the client never
  talks to Postgres.
- **The LLM never executes raw SQL**, and agent actions only ever go
  through explicitly whitelisted tools. See [agents.md](agents.md).
- **Extend the existing architecture** rather than replacing it.

## Changing the database schema

Schema changes go through `migrations/`, never a hand-edited
`init.sql` and never an ad-hoc `ALTER TABLE` against a running
database:

1. Add a numbered file, e.g. `migrations/002_<what_it_does>.sql`.
2. Write it **idempotently** (`ADD COLUMN IF NOT EXISTS`,
   `CREATE INDEX IF NOT EXISTS`). The `db-migrations` container replays
   every file in the directory on every `docker compose up`, locally
   and in production — a non-idempotent migration fails the second
   time it runs.
3. Update `init.sql` too if a fresh database should have the change
   from the start, and update [database.md](database.md).

## Adding a new service

Compose is the source of truth; a new service needs all of:

- its own directory with `main.py`, `requirements.txt`, `Dockerfile`,
  `pytest.ini`, `tests/`;
- a block in `docker-compose.yml` reading **every** port and setting
  from `.env` (`${VAR:?VAR is required in .env}` for the required ones
  — no hardcoded ports), with `depends_on` + healthcheck conditions;
- the new variables documented in `.env.example` and in
  [setup.md](setup.md);
- a row in the CI matrix in `.github/workflows/ci.yml`, with the same
  Python version its Dockerfile pins;
- a mention in [architecture.md](architecture.md).

If it needs to be reachable from the browser in production, it also
needs an nginx proxy rule on the server — see
[deployment.md](deployment.md#nginx).

## Environment variables

`docker-compose.yml` reads everything from the root `.env`. Required
values are marked `${VAR:?…}` so compose fails once, with a clear
message, instead of leaving a container in a restart loop. Optional
values use `${VAR:-default}`, and the URL defaults follow the
`${HOST:-${DOMAIN:-localhost}}` chain — point the stack at another
host by changing `HOST` in `.env`, never by editing URLs inside
`docker-compose.yml`. Details in
[skills/deployment/SKILL.md](../skills/deployment/SKILL.md).

When you add a variable: add it to `docker-compose.yml`, to
`.env.example` (with a comment saying what it's for), and to the table
in [setup.md](setup.md). If it's required in production, say so in
[deployment.md](deployment.md) — a missing one fails the deploy.

## Secrets

Never commit API keys, Telegram tokens, database passwords, or LLM
provider keys. `.env` and `.env.*` are gitignored (`.env.example` is
the deliberate exception); keep it that way. Production `.env` values
are the owner's to edit — an agent doesn't change them, print them, or
commit them.

## Keeping the docs honest

[AGENTS.md](../AGENTS.md) asks that these files be updated when the
architecture or the rules change. The docs in this directory are
written to state plainly when something is a spec rather than an
implementation (see the "not built yet" sections) — keep that habit; a
doc that quietly describes code that doesn't exist is worse than no
doc.
