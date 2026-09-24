---
name: gsh-frontend
description: Enforces GSH's client-side rules. Use whenever writing or editing anything under client/ — a React component, a hook, a call to gateway-api, Tailwind styling, or a Vitest suite — even if the user only says "add a button", "show this on the dashboard", or "fix the panel". Covers the {data, error} fetch contract and circuit breaker in services/api.js, why VITE_* variables are public and build-time only, the portal rule for overlays, dark-mode and cn() styling conventions, and the test setup traps.
---

# GSH Frontend Rules

The client is a Vite + React 18 SPA in `client/`, styled with Tailwind,
tested with Vitest. It talks to `gateway-api` and nothing else. Apply
these rules whenever you touch it, not only when the user mentions
architecture. Background and file map: [docs/frontend.md](../../docs/frontend.md).

## All HTTP goes through services/api.js

Never call `fetch` from a component or a hook. Add a method to the `api`
object instead, so every request inherits the timeout, the circuit
breaker, cookie credentials and the error unwrapping.

Every method returns `{ data, error }` and **never throws**. Keep that
contract when adding one:

```js
async getThing(bypassCircuit = false) {
  const res = await fetchSafe('/api/v1/thing', { bypassCircuit });
  return { data: Array.isArray(res.data) ? res.data : null, error: res.error };
},
```

Callers branch on `error` — don't wrap `api.*` calls in `try/catch`,
and don't make a component throw on a failed request. The dashboard is
expected to stay on screen when the gateway is down.

Two knobs, both deliberate:

- `bypassCircuit: true` only for calls a user triggers when the backend
  looks dead — login, logout, session check. Everything else must stay
  behind the breaker.
- A longer `timeout` only where the backend is genuinely slower; the
  agent endpoint uses 15s because of the LLM round trip. Don't raise it
  for ordinary reads.

## The client never talks to the database

No direct Postgres/Redis access, no SQL in the browser, no calling
`ingestion-service` or the ML services directly. `gateway-api` is the
only origin the client knows. If the dashboard needs data that no
endpoint exposes, add the endpoint (see the backend skill) rather than
reaching around it.

## VITE_* variables are public and baked in at build time

`import.meta.env.VITE_*` is inlined into the bundle by Vite. Two
consequences that matter:

- **Never put a secret behind `VITE_`.** API keys, tokens and passwords
  belong in a backend service's environment, where the browser cannot
  read them. `VITE_ADMIN_PATH` is obscurity, not access control — the
  real gate is `verify_api_key` on the server.
- **Changing one needs a rebuild**, not a restart. Production runs
  `npm run build` on the server for exactly this reason.

Required variables throw at import (`services/api.js`,
`vite.config.js`); keep that pattern for new ones rather than letting
`undefined` flow into a URL.

## State lives in hooks, views take props

`useServerData` owns dashboard state — data, filters, the localStorage
cache. `useWebSocket` owns the live connection and its status.
`useTheme` owns the theme. View components under `components/views/`
receive everything through props and don't fetch on their own; keep new
screens that way so there is one place where data enters the app.

When adding to the cached set, write through the same
`cs2_dashboard_cache` path, and wrap `localStorage` access in
`try/catch` the way the existing code does — it throws in private mode
and when the quota is full.

## Overlays render through a portal

Anything `position: fixed` that must cover the whole viewport — a
drawer, a modal, a backdrop — renders into `document.body` with
`createPortal`, like `AskPanel` does.

The app shell puts views inside `<main class="… space-y-6">`, and that
utility sets `margin-top: 1.5rem` on every child after the first.
Margins apply to fixed elements too, so an overlay left inside `<main>`
sits 24px too low and 24px too short, and the sticky header shows
through the gap at the top. A portal is the fix; `!mt-0` is a patch over
a structural mistake.

## Styling

- Tailwind utilities, not custom CSS files. Shared visual patterns that
  really are shared (`.glass-panel`, `.bg-grid-pattern`) live in
  `index.css`.
- **Always write both themes.** Dark mode is the `class` strategy on
  `<html>`; a component with only `bg-white` is invisible in dark mode,
  which is the default.
- Merge classes with `cn()` (clsx + tailwind-merge), never string
  concatenation, so a caller can override a component's defaults.
- Reuse `components/common/` (Button, Badge, Card, Modal, Pagination)
  before writing a new primitive.
- Check the layout at phone width: the shell has a mobile bottom nav
  bar, so anything anchored to the bottom needs to clear it.

## Tests

```bash
cd client && npm ci && npm test
```

Run them before handing work back — CI runs the same suite plus a
production build on every PR.

Repo-specific traps:

- `vitest.config.js` is separate from `vite.config.js` on purpose and
  supplies `VITE_API_URL` / `VITE_WS_URL` / `VITE_ADMIN_PATH`, because
  `services/api.js` throws at import without them. Add new required
  variables there too, or the whole suite fails to collect.
- `src/__tests__/setup.js` stubs `matchMedia` and `ResizeObserver`;
  jsdom has neither, and the theme hook and Recharts need them.
- Test behaviour through the rendered component (Testing Library
  queries), not implementation details.

## Quick checklist before opening a PR

- [ ] No `fetch` outside `services/api.js`
- [ ] New api methods return `{ data, error }` and never throw
- [ ] No secret behind a `VITE_` variable
- [ ] Full-screen overlays go through `createPortal`
- [ ] Every new class has a `dark:` counterpart
- [ ] Classes merged with `cn()`
- [ ] `npm test` passes and `npm run build` succeeds
