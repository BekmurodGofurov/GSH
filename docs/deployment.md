# Deployment

GSH runs on a single AWS EC2 box, in two environments:

| Environment | Branch | URL | Directory on the box | Compose project |
|---|---|---|---|---|
| **production** | `main` | `https://gsh.bekmurod.uz` | `/home/ubuntu/GSH` | `gsh` |
| **staging** | `developer` | `https://staging.gsh.bekmurod.uz` | `/home/ubuntu/GSH-staging` | `gsh-staging` |

Both deploy automatically, and only after CI has passed on the commit
being deployed. Staging is where a change is seen running for real
before it is promoted to `main`. Most of this doc describes production;
[Staging](#staging) covers what differs and how to set it up. For
running the stack on your own machine see [setup.md](setup.md), and for
the day-to-day workflow that gets code as far as `main` see
[development.md](development.md).

## Topology

```
                  https://gsh.bekmurod.uz
                            │
                     ┌──────▼──────┐
                     │    nginx    │  TLS terminates here
                     └──┬───────┬──┘
          static files   │       │   /api/… + /ws/live
                         │       │   proxied to 127.0.0.1:8000
              ┌──────────▼─┐   ┌─▼─────────────────────────────┐
              │/var/www/   │   │ docker compose (gsh-*)        │
              │gsh-frontend│   │ gateway-api, ingestion,       │
              └────────────┘   │ anomaly/root-cause ML,        │
                               │ bridge, alerting, timescaledb,│
                               │ redis                         │
                               └───────────────────────────────┘
```

The React app is **not** served by a container in production. The
`client` service in `docker-compose.yml` only runs the Vite dev server,
so the deploy builds the app to static files and stops that container —
nginx serves the result. Everything else runs exactly as it does
locally, under Docker Compose.

Because nginx proxies the API on the same origin, the browser only ever
talks to `https://gsh.bekmurod.uz`. That is why `client/.env` on the
server holds `https://` / `wss://` URLs and not `http://<ip>:8000`.

## What lives where on the server

| Path | What it is | In git? |
|---|---|---|
| `/home/ubuntu/GSH` | the repo checkout the deploy updates | yes |
| `/home/ubuntu/GSH/.env` | all backend secrets and ports, read by `docker-compose.yml` | **no** — gitignored, lives only on the box |
| `/home/ubuntu/GSH/client/.env` | the frontend build's `VITE_*` values (production `https://` URLs) | **no** — same |
| `/var/www/gsh-frontend` | the built static app nginx serves | no — build output |
| nginx site config (`/etc/nginx/sites-available/…`) | TLS, static root, API/WS proxy | **no** — not version-controlled |

The two `.env` files and the nginx config are the only state that is
not reproducible from this repo. Back them up; a lost `client/.env`
breaks the next deploy (see Troubleshooting).

## The CD pipeline

[`.github/workflows/cd.yml`](../.github/workflows/cd.yml) runs when a
[CI](../.github/workflows/ci.yml) run finishes (`workflow_run`). It
deploys only if that run **succeeded** and was triggered by a **push**
to `developer` or `main` — CI runs on pull requests never deploy, and a
red CI run deploys nothing:

```
push to developer ──► CI ──(green)──► CD ──► staging
push to main      ──► CI ──(green)──► CD ──► production
```

It can also be started by hand from the Actions tab
(`workflow_dispatch`, choose `staging` or `production`); that deploys
the current tip of the environment's branch.

`workflow_run` always uses the copy of `cd.yml` on the default branch
(`developer`), so a change to the pipeline takes effect as soon as it
is merged there.

Required repository secrets (shared by both environments, since both
live on the same box):

| Secret | Value |
|---|---|
| `EC2_HOST` | the box's public IP or hostname |
| `EC2_USERNAME` | `ubuntu` |
| `EC2_SSH_KEY` | the private half of the key pair in `~/.ssh/authorized_keys` on the box |

Per-environment variables, under **Settings → Environments →
`<environment>` → Environment variables**:

| Variable | production | staging |
|---|---|---|
| `DEPLOY_DIR` | `/home/ubuntu/GSH` (default if unset) | `/home/ubuntu/GSH-staging` — **required** |
| `FRONTEND_DIR` | `/var/www/gsh-frontend` (default if unset) | `/var/www/gsh-staging-frontend` — **required** |

Staging has no defaults on purpose: a missing variable fails the deploy
instead of landing it in production's directory. If staging ever moves
to its own box, give the `staging` environment its own `EC2_*` secrets —
environment secrets override repository ones.

The job SSHes in (`appleboy/ssh-action`) and runs one script:

1. `git fetch` + `git reset --hard <sha>` — the box lands on exactly
   the commit CI tested, then `checkout -B` pins it to the
   environment's branch. `reset --hard` only touches tracked files, so
   both `.env` files survive it.
2. `docker compose up -d --build` — rebuilds changed images and
   restarts them. `db-migrations` runs everything in `migrations/`
   here, then exits.
3. `docker compose stop client` — the dev-server container stays down.
4. `npm ci && npm run build` in `client/` — `npm ci` installs the exact
   versions from `package-lock.json`, so production gets the same
   dependency tree CI tested.
5. `sudo cp -r dist/* $FRONTEND_DIR/` — the new app goes live the
   moment this finishes.
6. `docker image prune -f` — drops the layers the rebuild orphaned, so
   the EC2 disk doesn't fill up.

Guards worth knowing about:

- `set -e` (plus `script_stop: true`) stops the script at the first
  failing command. Without it a failed `npm run build` would be
  followed by a successful `cp` of the *previous* `dist/`, and the
  deploy would report green while shipping nothing.
- `concurrency: deploy-<environment>` with `cancel-in-progress: false`
  queues a second deploy to the same environment instead of running two
  `docker compose up`s in the same directory at once. Staging and
  production have separate groups, so neither waits on the other.
- A non-production deploy refuses to run unless its `.env` sets
  `COMPOSE_PROJECT_NAME` — see [Staging](#staging) for why.

### The build's env vars come from the server, not from CI

`client/vite.config.js` throws when `VITE_API_URL` or `CLIENT_PORT` is
empty, and the static build has no compose `environment:` block feeding
it. Vite reads `client/.env` from the working directory, which is why
the deploy script just runs `npm run build` with nothing exported.

Do not add `export VITE_API_URL=…` to the workflow. An exported shell
variable wins over the `.env` file in Vite's `loadEnv`, so it would
silently override the production `https://` URLs with whatever it
derived — and the browser would block the resulting mixed content.

## Deploying

Normal path:

1. Merge a `feature/*` PR into `developer`. CI runs on the push, and
   when it is green the change goes to staging.
2. Check it on `https://staging.gsh.bekmurod.uz`.
3. Open a PR `developer` → `main` and merge it. CI runs again on
   `main`, and when it is green the change goes to production.

Watch both in the Actions tab: each deploy shows up as a **CD** run
right after the **CI** run it follows.

### Manual deploy

Same steps, by hand, when Actions is unavailable (production shown; for
staging use its directory, branch and `FRONTEND_DIR`):

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

Re-running an older **CD** run from the Actions tab redeploys the exact
commit that run deployed, so it is a quick way back — but the next
green push to the branch deploys over it again. A manual
`workflow_dispatch` run always deploys the branch's current tip.

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

## Staging

Staging is a second, complete copy of the stack on the same box: its
own checkout, its own `.env` files, its own containers, its own
database and its own static frontend, behind its own subdomain. It
deploys from `developer`, so what is on staging is what the next
`developer` → `main` PR would ship.

### How two stacks share one box

`docker-compose.yml` names every container
`${COMPOSE_PROJECT_NAME:-gsh}-<service>`. Production leaves
`COMPOSE_PROJECT_NAME` unset, so nothing about it changes: the project
is still `gsh` (from the `GSH` directory name), the containers are
still `gsh-*`, and the database is still the `gsh_timescale_data`
volume. Staging sets `COMPOSE_PROJECT_NAME=gsh-staging` in its `.env`,
which gives it `gsh-staging-*` containers, its own network and its own
`gsh-staging_timescale_data` volume.

Without that line staging would try to create containers named `gsh-*`
that production already owns — which is why the deploy refuses to run
for a non-production environment whose `.env` doesn't set it.

The host ports must differ too, since both stacks publish on the same
machine. Staging's `.env` moves every one of them.

### What is deliberately different on staging

| | Why |
|---|---|
| **Its own database, starting empty** | Staging experiments (a migration, a relabel from the agent) never touch production data. Add a few servers through staging's admin panel after the first deploy so ingestion has something to poll. |
| **Its own Telegram bot token** | Telegram allows one long-polling client per bot. Two `alerting-service` containers on the same token fight each other with `409 Conflict`, and production alerts start getting lost. Create a second bot with @BotFather, and point it at a separate test group. |
| **Its own Gemini API key** (recommended) | The free tier is ~10 agent questions per day per model. Sharing a key means testing on staging uses up production's quota. |
| **Different host ports** | Both stacks publish on the same machine. |

### One-time setup

Done once, by the owner, on the box and in GitHub. None of it is in
this repo, and per [AGENTS.md](../AGENTS.md) an agent must not do it.

**0. Check the box has room.** Two stacks means two TimescaleDBs, two
sets of ML services and two Redis instances.

```bash
free -h      # want ~2 GB free with production running
df -h /      # and a few GB of disk for the second set of images
```

If it is tight, either move to a bigger instance or put staging on its
own small instance — the workflow supports that (see
[The CD pipeline](#the-cd-pipeline)).

**1. DNS.** Add an `A` record `staging.gsh.bekmurod.uz` → the box's IP.

**2. Checkout.**

```bash
cd /home/ubuntu
git clone https://github.com/BekmurodGofurov/GSH.git GSH-staging
cd GSH-staging && git checkout developer
```

**3. Root `.env`.** Start from production's and change what must
differ:

```bash
cp /home/ubuntu/GSH/.env /home/ubuntu/GSH-staging/.env
```

```env
COMPOSE_PROJECT_NAME=gsh-staging

# Every host port shifted so nothing collides with production.
TIMESCALE_HOST_PORT=5433
REDIS_PORT=6380
GATEWAY_PORT=9000
INGESTION_PORT=9001
ANOMALY_ML_PORT=9002
ROOT_CAUSE_ML_PORT=9003
CLIENT_PORT=3001

FRONTEND_URL=https://staging.gsh.bekmurod.uz
POSTGRES_PASSWORD=<a different password>
TELEGRAM_BOT_TOKEN=<the staging bot's token>
TELEGRAM_CHAT_ID=<the staging test group>
AGENT_LLM_API_KEY=<a separate key>
SEND_ON_STARTUP=false
```

If production's `.env` sets `TIMESCALE_CONTAINER_PORT` or any other
`*_HOST_PORT`, shift those as well.

**4. `client/.env`.** Same as production's, with staging's URLs:

```env
VITE_API_URL=https://staging.gsh.bekmurod.uz
VITE_WS_URL=wss://staging.gsh.bekmurod.uz/ws/live
VITE_ADMIN_PATH=/secret-admin
CLIENT_PORT=3001
```

**5. nginx.** A second site, identical to production's except for the
name, the static root and the gateway port:

```nginx
server {
    server_name staging.gsh.bekmurod.uz;

    root /var/www/gsh-staging-frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/live {
        proxy_pass http://127.0.0.1:9000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 300s;
    }
}
```

```bash
sudo mkdir -p /var/www/gsh-staging-frontend
sudo nano /etc/nginx/sites-available/gsh-staging     # paste the block above
sudo ln -s /etc/nginx/sites-available/gsh-staging /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d staging.gsh.bekmurod.uz
```

Consider protecting the staging site with HTTP basic auth
(`auth_basic`) — it is a full copy of the app, agent included.

**6. GitHub environments.** In **Settings → Environments**:

- `staging` — add the variables `DEPLOY_DIR=/home/ubuntu/GSH-staging`
  and `FRONTEND_DIR=/var/www/gsh-staging-frontend`. Under
  *Deployment branches*, allow only `developer`.
- `production` — optionally set the same two variables to production's
  paths (the workflow falls back to them anyway). Under *Deployment
  branches*, allow only `main`. Adding yourself as a *Required
  reviewer* makes every production deploy wait for a click.

**7. First deploy.** Actions → **CD** → *Run workflow* → `staging`.
Then open `https://staging.gsh.bekmurod.uz`, log into the admin panel
and add a couple of servers.

Useful commands on the box need the right directory — `docker compose`
picks up the project name from that directory's `.env`:

```bash
cd /home/ubuntu/GSH-staging && docker compose ps     # staging
cd /home/ubuntu/GSH         && docker compose ps     # production
```

## Database migrations in production

`db-migrations` replays **every** file in `migrations/` on every
deploy, in filename order. Migrations must therefore be idempotent —
`ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, and so on —
or the second deploy fails. See
[database.md](database.md#migrations).

`init.sql` is a different mechanism: Postgres runs it only when the
`timescale_data` volume is first created. It will never run again on
this box, so schema changes always go in `migrations/`, never into
`init.sql`.

## nginx

The live config is not in this repo. If it has to be rebuilt, this is
the shape it must have — static root with SPA fallback, the API and
the WebSocket proxied to `gateway-api` on the same origin:

```nginx
server {
    server_name gsh.bekmurod.uz;

    root /var/www/gsh-frontend;
    index index.html;

    # React Router: unknown paths must return index.html, not 404.
    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket needs the upgrade headers; without them /ws/live 400s.
    location /ws/live {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 300s;
    }

    # TLS (certbot-managed) below.
}
```

`8000` is `GATEWAY_HOST_PORT` / `GATEWAY_PORT` from the root `.env`;
if that changes, nginx has to change with it.

`FRONTEND_URL` in the root `.env` must be the public origin
(`https://gsh.bekmurod.uz`) — `gateway-api/main.py` feeds it straight
into the CORS `allow_origins` list and raises at import if it is unset.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Deploy fails at `npm run build` with `VITE_API_URL environment variable is not set` | `client/.env` is missing on the server. Recreate it (see the table above); the old frontend is still live, nothing was overwritten. |
| Deploy fails at `docker compose up` with `… is required in .env` | a new required variable was added to `docker-compose.yml` but not to the server's root `.env`. |
| Site loads but every request fails with a CORS or mixed-content error | `FRONTEND_URL` in the root `.env`, or the `VITE_*` URLs in `client/.env`, don't match the public origin. |
| Dashboard renders but never updates | `/ws/live` isn't proxied with the upgrade headers, or `gateway-api` is down — `docker compose logs -f gateway-api`. |
| Frontend looks stale after a green deploy | the copy landed but the browser cached `index.html`; hard-reload. The hashed assets under `dist/assets/` are new on every build. |
| The agent answers "LLM provider error ... 429 RESOURCE_EXHAUSTED" | the Gemini free tier allows 20 requests per day **per model**, and one question costs two of them (tool selection, then the grounded answer). Switch `AGENT_LLM_MODEL` in `.env` to another model id, or enable billing on the Google project. |
| The agent answers "LLM provider error ... 404 ... no longer available" | Google retired that model id; the message names the replacement. Put it in `AGENT_LLM_MODEL` and restart gateway-api -- no code change needed. |
| A push was merged but no **CD** run appeared | CD only follows a **successful** CI run from a push. Check the CI run for that commit first; a red or cancelled CI deploys nothing. |
| Staging deploy fails with `DEPLOY_DIR is not set for the staging environment` | the `staging` environment in GitHub is missing its `DEPLOY_DIR` / `FRONTEND_DIR` variables (setup step 6). |
| Staging deploy fails with `.env must set COMPOSE_PROJECT_NAME` | staging's root `.env` is missing `COMPOSE_PROJECT_NAME=gsh-staging` (setup step 3). |
| Staging `docker compose up` fails with `port is already allocated` | a host port in staging's `.env` is still the same as production's. |
| Telegram alerts stop arriving, alerting logs show `409 Conflict` | staging and production share a `TELEGRAM_BOT_TOKEN`. Give staging its own bot. |
| Disk full on the box | `docker system df`, then `docker system prune -a` (stops nothing that's running, but re-pulls on the next deploy). |

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
