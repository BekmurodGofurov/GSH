# Production Deployment

GSH runs on a single AWS EC2 box. Everything below describes that one
environment; there is no staging. For running the stack on your own
machine see [setup.md](setup.md), and for the day-to-day workflow that
gets code as far as `main` see [development.md](development.md).

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

[`.github/workflows/cd.yml`](../.github/workflows/cd.yml) deploys on
every push to `main` — in practice, every merged PR from `developer`.
It can also be started by hand from the Actions tab
(`workflow_dispatch`).

Required repository secrets:

| Secret | Value |
|---|---|
| `EC2_HOST` | the box's public IP or hostname |
| `EC2_USERNAME` | `ubuntu` |
| `EC2_SSH_KEY` | the private half of the key pair in `~/.ssh/authorized_keys` on the box |

The job SSHes in (`appleboy/ssh-action`) and runs one script:

1. `git fetch origin main` + `git reset --hard origin/main` — the box
   lands on exactly the commit that was merged. `reset --hard` only
   touches tracked files, so both `.env` files survive it.
2. `docker compose up -d --build` — rebuilds changed images and
   restarts them. `db-migrations` runs everything in `migrations/`
   here, then exits.
3. `docker compose stop client` — the dev-server container stays down.
4. `npm ci && npm run build` in `client/` — `npm ci` installs the exact
   versions from `package-lock.json`, so production gets the same
   dependency tree CI tested.
5. `sudo cp -r dist/* /var/www/gsh-frontend/` — the new app goes live
   the moment this finishes.
6. `docker image prune -f` — drops the layers the rebuild orphaned, so
   the EC2 disk doesn't fill up.

Two guards worth knowing about:

- `set -e` (plus `script_stop: true`) stops the script at the first
  failing command. Without it a failed `npm run build` would be
  followed by a successful `cp` of the *previous* `dist/`, and the
  deploy would report green while shipping nothing.
- `concurrency: deploy-production` with `cancel-in-progress: false`
  queues a second deploy instead of running two `docker compose up`s
  against the same box at once.

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

Normal path: merge `developer` → `main` through a PR with CI green.
The push to `main` triggers the deploy; watch it in the Actions tab.

### Manual deploy

Same steps, by hand, when Actions is unavailable:

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

Note the gotcha first: re-running an **older** workflow run does *not*
redeploy that older commit. The script always resets to whatever
`origin/main` points at now, so a re-run just redeploys current `main`.

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
