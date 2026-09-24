# Client (React Dashboard)

`client/` is a Vite + React 18 single-page app styled with Tailwind. It
is the only part of GSH that runs in a browser, and it talks to exactly
one service — `gateway-api` — over REST and one WebSocket.

For running it see [setup.md](setup.md) and
[development.md](development.md); for how it is built and served in
production see [deployment.md](deployment.md).

## Layout of the source

```
client/src/
  main.jsx               mounts <App/>
  App.jsx                view switching, panel/modal state, admin routing
  index.css              Tailwind layers, scrollbars, .glass-panel, grid bg
  components/
    layout/              Header, Sidebar, Layout (the app shell)
    common/              Button, Badge, Card, Modal, AskPanel, drawers…
    dashboard/           ServerCard, KpiStatsGrid, charts, ServerDetailModal
    views/               one component per screen (Overview, Servers, …)
  hooks/
    useServerData.js     all dashboard state: fetching, cache, filters
    useWebSocket.js      the live feed, with backoff and status
    useTheme.js          dark/light, persisted, toggles `.dark` on <html>
  services/api.js        every HTTP call to gateway-api
  utils/                 cn() class merging, formatters for ping/time/events
  __tests__/             Vitest suites + jsdom setup
```

There is no router. `App.jsx` keeps a `currentView` string
(`overview | servers | events | analytics | insights | admin`) and
renders one view component for it. The only URL-aware part is the admin
screen (see below).

## Data flow

```
gateway-api ──REST──► services/api.js ──► useServerData ──► views
            └─WS────► useWebSocket ─────┘        │
                                                 └─► localStorage cache
```

`useServerData` is the single source of truth for dashboard state:
servers, events, per-server metrics, ping buckets, the daily-insight
tables, plus the search/region/status/time-range filters. Views receive
data through props — they don't fetch.

`useWebSocket` holds the `/ws/live` connection. `gateway-api` pushes
`{servers, events}` every 3 seconds; the hook exposes `status`
(`connected | reconnecting | offline`) and a retry countdown, and
reconnects on a `3s → 6s → 12s → 20s` backoff. `ConnectionBanner` and
the header badge render that status.

### Everything survives the backend being down

Three mechanisms, worth knowing before changing any of them:

- **Circuit breaker** (`services/api.js`). A failed request records a
  timestamp; for the next 2.5s every call short-circuits with
  `{data: null, error: 'Gateway currently offline'}` instead of hitting
  the network. Without it a dead gateway means dozens of pending
  requests from the polling views. Auth calls pass
  `bypassCircuit: true` so a user can always try to log in.
- **Timeouts**. 3.5s by default via `AbortController`; the agent call
  uses 15s because an LLM round trip is much slower than a DB read.
- **localStorage cache** (`cs2_dashboard_cache`). The last good
  servers/events/metrics are written on every successful load and read
  synchronously on startup, so a reload with the gateway down still
  renders the last known state with the "OFFLINE MODE" banner.

## services/api.js is the only place that calls fetch

Every function returns `{ data, error }` and **never throws** — the
fetch, the timeout, the non-2xx status and the JSON parse are all
handled inside `fetchSafe`. Callers branch on `error`; they don't need
`try/catch`.

FastAPI's error body (`{detail: "..."}`) is unwrapped into `error`, so
the string the user sees is the one the backend wrote.

`credentials: 'include'` is set on every request — admin auth is a
session cookie issued by `POST /api/v1/admin/login`.

The routes it covers mirror [api.md](api.md): servers, metrics, events,
the four analytics endpoints, daily insights, admin login/logout/me,
server CRUD, and `askAgent()` for the agent panel.

## Environment variables

Vite inlines `import.meta.env.VITE_*` **at build time** — they are not
read at runtime. Changing one means rebuilding the app, which is why
the deploy runs `npm run build` on the server.

| Variable | Used by | Notes |
|---|---|---|
| `VITE_API_URL` | `services/api.js`, `vite.config.js` | required; both throw when it is missing |
| `VITE_WS_URL` | `useWebSocket.js` | falls back to `VITE_API_URL` with `http`→`ws` |
| `VITE_ADMIN_PATH` | `App.jsx` | default `/secret-admin` |
| `CLIENT_PORT` | `vite.config.js` | dev/preview port; required |

Locally they come from `client/.env`; under Docker Compose from the
root `.env` via the `client` service's `environment:` block; in
production from `client/.env` on the server.

**Anything prefixed `VITE_` ends up in the JavaScript bundle and is
readable by anyone who opens the site.** Never put an API key, token or
password behind that prefix.

## The admin screen

`App.jsx` compares `window.location.pathname` (and the hash) against
`VITE_ADMIN_PATH` and switches `currentView` to `admin`. It listens for
`popstate`/`hashchange`, so the back button works.

This is **obscurity, not security**: the path is in the bundle, and the
actual protection is `gateway-api`'s `verify_api_key` plus the session
cookie. Every admin route on the backend is guarded server-side — the
client just decides what to render.

## Styling

Tailwind, dark mode via the `class` strategy: `useTheme` toggles
`.dark` on `<html>` and persists the choice in `cs2_theme`
(default dark). Write both themes for anything new —
`bg-white dark:bg-slate-950` and so on.

Merge class names with `cn()` (`utils/cn.js`, clsx + tailwind-merge)
rather than template strings, so a caller's `px-4` can override a
component's `px-2` instead of both landing in `class`.

Shared visual patterns live in `index.css`: `.glass-panel`,
`.bg-grid-pattern`, the custom 6px scrollbars, and the toast/radar
keyframes.

### Overlays must be portaled

`AskPanel` renders its backdrop and panel into `document.body` with
`createPortal`. This is not cosmetic: the app shell puts views inside
`<main class="… space-y-6">`, and that utility applies
`margin-top: 1.5rem` to every child after the first — including
`position: fixed` ones. A fixed overlay left inside `<main>` is pushed
24px down and ends 24px short, leaving the sticky header uncovered at
the top of the screen.

`NotificationsDrawer` and `Modal` still render in place and have that
24px offset today.

## Tests

Vitest + Testing Library + jsdom:

```bash
cd client && npm ci && npm test
```

`vitest.config.js` is deliberately separate from `vite.config.js`: the
latter throws when `VITE_API_URL` / `CLIENT_PORT` are unset, which would
tie the test run to a developer's local `.env`. The test config supplies
those values itself — `services/api.js` throws at import without them.

`src/__tests__/setup.js` stubs `matchMedia` and `ResizeObserver`, which
jsdom does not implement and which the theme hook and the Recharts
components need.

## Build

```bash
npm run dev       # dev server, port from CLIENT_PORT
npm run build     # static bundle into dist/
npm run preview   # serve dist/ locally
```

`vite.config.js` splits `recharts` and `lucide-react` into their own
chunks — `charts` is the largest asset by a wide margin, and keeping it
separate stops every unrelated change from invalidating it in the
browser cache.
