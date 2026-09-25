# Deployment

GSH runs on a single AWS EC2 box, in two environments:

| Environment | Branch | URL | Directory on the box | Workflow |
|---|---|---|---|---|
| **production** | `main` | `https://gsh.bekmurod.uz` | `/home/ubuntu/GSH` | `.github/workflows/cd.yml` |
| **dev** | `developer` | `https://gsh-dev.bekmurod.uz` | `/home/ubuntu/projects/gsh-dev` | `.github/workflows/cd-dev.yml` |

Both deploy automatically, and only after CI has passed. Dev is where a
change is seen running for real before it is promoted to `main`. For
running the stack on your own machine see [setup.md](setup.md), and for
the day-to-day workflow that gets code as far as `main` see
[development.md](development.md).

## Topology

Both environments have the same shape; only the names and ports differ.

```
                  https://gsh.bekmurod.uz
                            │
                     ┌──────▼──────┐
                     │    nginx    │  TLS terminates here
                     └──┬───────┬──┘
          static files   │       │   /api/ + /ws/
                         │       │   proxied to 127.0.0.1:8000
              ┌──────────▼─┐   ┌─▼─────────────────────────────┐
              │/var/www/   │   │ docker compose (gsh-*)        │
              │gsh-frontend│   │ gateway-api, ingestion,       │
              └────────────┘   │ anomaly/root-cause ML,        │
                               │ bridge, alerting, timescaledb,│
                               │ redis                         │
                               └───────────────────────────────┘
```

The React app is **not** served by a container. The `client` service in
`docker-compose.yml` only runs the Vite dev server, so the deploy builds
the app to static files and stops that container — nginx serves the
result. Everything else runs exactly as it does locally, under Docker
Compose.

Because nginx proxies the API on the same origin, the browser only ever
talks to the site's own `https://` address. That is why `client/.env` on
the server holds `https://` / `wss://` URLs and not `http://<ip>:8000`.

## What lives where on the server

| Path | What it is | In git? |
|---|---|---|
| `/home/ubuntu/GSH` | production checkout (`main`) | yes |
| `/home/ubuntu/projects/gsh-dev` | dev checkout (`developer`) | yes |
| `<checkout>/.env` | backend secrets and ports, read by `docker-compose.yml` | **no** — gitignored, lives only on the box |
| `<checkout>/client/.env` | the frontend build's `VITE_*` values (`https://` URLs) | **no** — same |
| `/var/www/gsh-frontend`, `/var/www/gsh-dev-frontend` | the built static apps nginx serves | no — build output |
| `/etc/nginx/sites-available/gsh.bekmurod.uz`, `…/gsh-dev.bekmurod.uz` | TLS, static root, API/WS proxy | **no** — not version-controlled |

The `.env` files and the nginx configs are the only state that is not
reproducible from this repo. Back them up; a lost `client/.env` breaks
the next deploy (see Troubleshooting).

## The CD pipeline

```
merge into developer ──► CI ──green──► cd-dev.yml ──► ~/projects/gsh-dev
merge into main      ──► CI ──green──► cd.yml     ──► ~/GSH
                               └─red──► no deploy
```

Each workflow starts when a [CI](../.github/workflows/ci.yml) run
finishes (`workflow_run`) and deploys only if that run **succeeded** and
came from a **push** to its branch. CI runs on pull requests never
deploy. Both can also be started by hand: Actions → **CD developer** /
**CD main** → *Run workflow*.

`workflow_run` always uses the copy of a workflow file on the default
branch (`developer`), so a change to either file takes effect as soon as
it is merged into `developer` — for `main`'s deploy too.

Required repository secrets:

| Secret | Value |
|---|---|
| `EC2_HOST` | the box's public IP or hostname |
| `EC2_USERNAME` | `ubuntu` |
| `EC2_SSH_KEY` | the private half of the key pair in `~/.ssh/authorized_keys` on the box |

Everything else — directories, branches, the frontend path — is written
in the workflow files themselves.

The job SSHes in (`appleboy/ssh-action`) and runs one script:

1. `git fetch` + `git reset --hard origin/<branch>` + `git checkout -B
   <branch>` — the box lands exactly on the branch tip.
   `reset --hard` only touches tracked files, so both `.env` files
   survive it.
2. `docker compose up -d --build` — rebuilds changed images and
   restarts them. `db-migrations` runs everything in `migrations/`
   here, then exits.
3. `docker compose stop client` — the dev-server container stays down.
4. `npm ci && npm run build` in `client/` — `npm ci` installs the exact
   versions from `package-lock.json`.
5. `sudo cp -r dist/* /var/www/<frontend>/` — the new app goes live the
   moment this finishes.
6. `docker image prune -f` — drops the layers the rebuild orphaned, so
   the disk doesn't fill up.

`set -e` (plus `script_stop: true`) stops the script at the first
failing command, so a failed `npm run build` can't be followed by a
copy of the *previous* `dist/`. `concurrency` queues a second deploy
to the same environment instead of running two at once.

### The build's env vars come from the server, not from CI

`client/vite.config.js` throws when `VITE_API_URL` or `CLIENT_PORT` is
empty. Vite reads `client/.env` from the working directory, which is
why the deploy script just runs `npm run build` with nothing exported.

Do not add `export VITE_API_URL=…` to a workflow. An exported shell
variable wins over the `.env` file in Vite's `loadEnv`, so it would
silently override the `https://` URLs — and the browser would block the
resulting mixed content.

## Deploying

1. Merge a `feature/*` PR into `developer`. CI runs, and when it is
   green **CD developer** updates `https://gsh-dev.bekmurod.uz`.
2. Check the change there.
3. Merge a PR `developer` → `main`. CI runs again, and when it is green
   **CD main** updates `https://gsh.bekmurod.uz`.

### Manual deploy

The same steps by hand, when Actions is unavailable (production shown;
for dev use `~/projects/gsh-dev`, `developer` and
`/var/www/gsh-dev-frontend/`):

```bash
ssh ubuntu@<EC2_HOST>
cd /home/ubuntu/GSH
git fetch origin main && git reset --hard origin/main
docker compose up -d --build
docker compose stop client
cd client && npm ci && npm run build
sudo cp -r dist/* /var/www/gsh-frontend/
```

### Rolling back

Roll back by moving `main`:

```bash
git revert <bad-commit>     # on a branch, PR into developer, merge to main
```

That keeps history honest and re-runs CI. For a fast emergency stop,
pin the box to a known-good commit directly — and remember the next
deploy will undo it:

```bash
ssh ubuntu@<EC2_HOST>
cd /home/ubuntu/GSH
git reset --hard <good-sha>
docker compose up -d --build
cd client && npm ci && npm run build && sudo cp -r dist/* /var/www/gsh-frontend/
```

## Dev environment

Dev is a second, complete copy of the stack on the same box: its own
checkout, its own `.env` files, its own containers, its own database
and its own site.

### How two stacks share one box

`docker-compose.yml` names every container
`${COMPOSE_PROJECT_NAME:-gsh}-<service>`. Production doesn't set
`COMPOSE_PROJECT_NAME`, so it keeps the `gsh-*` containers and the
`gsh_timescale_data` volume. Dev's `.env` sets
`COMPOSE_PROJECT_NAME=gsh-dev`, which gives it `gsh-dev-*` containers,
its own network and its own `gsh-dev_timescale_data` volume.

Without that line dev asks for container names production already owns,
and `docker compose up` fails with `container name "/gsh-…" is already
in use`.

Both stacks reach their database as `timescaledb:5432`, but that name
resolves inside each project's own network, so dev never touches
production's data.

### Ports

Every published port must differ, since both stacks publish on the
same machine:

| | production (`~/GSH`) | dev (`~/projects/gsh-dev`) |
|---|---|---|
| `CLIENT_PORT` | 3000 | 3030 |
| `GATEWAY_PORT` | 8000 | 8030 |
| `INGESTION_PORT` | 8001 | 8031 |
| `ANOMALY_ML_PORT` | 8002 | 8032 |
| `ROOT_CAUSE_ML_PORT` | 8003 | 8033 |
| `REDIS_PORT` | 6379 | 6380 |
| `TIMESCALE_HOST_PORT` | 5434 | 5436 |

`TIMESCALE_CONTAINER_PORT` stays `5432` in both — it is the port inside
the container. Keep the database and Redis ports closed in the AWS
firewall; nothing outside the box needs them, and Redis has no password.

### What must be different in dev's `.env`

| | Why |
|---|---|
| `COMPOSE_PROJECT_NAME=gsh-dev` | see above |
| the ports in the table above | both stacks publish on the same machine |
| `FRONTEND_URL=https://gsh-dev.bekmurod.uz` | CORS origin for dev's site |
| **its own `TELEGRAM_BOT_TOKEN`** and a test `TELEGRAM_CHAT_ID` | Telegram allows one polling client per bot. Two `alerting-service` containers on one token fight with `TelegramConflictError`, and production's bot stops answering. |
| `SEND_ON_STARTUP=false` | otherwise every deploy posts a report |
| its own `AGENT_LLM_API_KEY` (recommended) | the free Gemini tier is ~10 agent questions a day; a shared key lets dev use up production's quota |

Dev's `client/.env`:

```env
VITE_API_URL=https://gsh-dev.bekmurod.uz
VITE_WS_URL=wss://gsh-dev.bekmurod.uz/ws/live
VITE_ADMIN_PATH=/secret-admin
CLIENT_PORT=3030
```

On a fresh database `ingestion-service` seeds its default list of
servers (`ingestion-service/db.py`) on startup, so dev has data to show
within seconds.

Commands on the box need the right directory — `docker compose` reads
the project name from that directory's `.env`:

```bash
cd ~/projects/gsh-dev && docker compose ps     # dev
cd ~/GSH              && docker compose ps     # production
```

## Database migrations

`db-migrations` replays **every** file in `migrations/` on every
deploy, in filename order. Migrations must therefore be idempotent —
`ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, and so on —
or the second deploy fails. See
[database.md](database.md#migrations). A new migration runs on dev
first, when it lands in `developer`.

`init.sql` is a different mechanism: Postgres runs it only when the
`timescale_data` volume is first created. It will never run again on
an existing environment, so schema changes always go in `migrations/`,
never into `init.sql`.

## nginx

The live configs are not in this repo. Production's, without the
certbot-managed TLS lines:

```nginx
server {
    server_name gsh.bekmurod.uz;

    location / {
        root /var/www/gsh-frontend;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
    }
}
```

Dev's (`gsh-dev.bekmurod.uz`) is identical except for `server_name`,
`root /var/www/gsh-dev-frontend` and port `8030` in both `proxy_pass`
lines. A new site is enabled with:

```bash
sudo ln -s /etc/nginx/sites-available/<site> /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d <domain>
```

The gateway port in `proxy_pass` is `GATEWAY_PORT` from that
environment's `.env`; if one changes, the other has to change with it.
`FRONTEND_URL` in the `.env` must be the site's public origin —
`gateway-api/main.py` feeds it into the CORS `allow_origins` list.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| A merge landed but no **CD** run appeared | CD only follows a **successful** CI run from a push. Check the CI run for that commit first; a red or cancelled CI deploys nothing. |
| Site shows `403 Forbidden` | the static folder in `/var/www/` is empty — the build ran but `sudo cp -r dist/* …` didn't. |
| Deploy fails at `npm run build` with `VITE_API_URL environment variable is not set` | `client/.env` is missing on the server. Recreate it; the old frontend is still live, nothing was overwritten. |
| Deploy fails at `docker compose up` with `… is required in .env` | a new required variable was added to `docker-compose.yml` but not to that environment's `.env`. |
| Dev `docker compose up` fails with `container name "/gsh-…" is already in use` | `COMPOSE_PROJECT_NAME=gsh-dev` is missing from dev's `.env`. Production is untouched; add the line and run it again. |
| `docker compose up` fails with `port is already allocated` | a port in dev's `.env` is the same as production's (see [Ports](#ports)). |
| Alerting logs show `TelegramConflictError` | two running `alerting-service` containers share one bot token — dev, production, or someone's local `docker compose up`. Compare with `docker compose exec alerting-service printenv TELEGRAM_BOT_TOKEN \| cut -d: -f1` in each. |
| A changed `.env` value has no effect | `docker compose restart` doesn't reread `.env`. Use `docker compose up -d <service>` — it should say `Recreated`. |
| Site loads but every request fails with a CORS or mixed-content error | `FRONTEND_URL` in the root `.env`, or the `VITE_*` URLs in `client/.env`, don't match the site's origin. |
| Dashboard renders but never updates | `/ws/` isn't proxied with the upgrade headers, or `gateway-api` is down — `docker compose logs -f gateway-api`. |
| Frontend looks stale after a green deploy | the browser cached `index.html`; hard-reload. |
| The agent answers "LLM provider error ... 429 RESOURCE_EXHAUSTED" | the Gemini free tier allows 20 requests per day **per model**, and one question costs two. Switch `AGENT_LLM_MODEL` in `.env` or enable billing. |
| The agent answers "LLM provider error ... 404 ... no longer available" | Google retired that model id; the message names the replacement. Put it in `AGENT_LLM_MODEL` and `docker compose up -d gateway-api`. |
| Disk full on the box | `docker system df`, then `docker system prune -a`. Two stacks and a growing `server_metrics` table (no retention policy yet) both take space. |

Useful once you're on the box:

```bash
docker compose ps                    # what's up, what's restarting
docker compose logs -f gateway-api   # any service
docker compose logs db-migrations    # did migrations apply?
```

## Secrets

Per [AGENTS.md](../AGENTS.md) and
[skills/deployment/SKILL.md](../skills/deployment/SKILL.md), production
configuration and secrets are the owner's to edit. An agent must not
change `.env` values, print them back, or commit them — API keys,
Telegram tokens, database passwords and LLM provider keys included. If
a deployment task needs one of them changed, say what needs changing
and stop.
