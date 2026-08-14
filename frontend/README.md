# Frontend

React + TypeScript + Vite + Tailwind CSS v4 client for the backend in
`../backend/`. Covers every role's UI from the project brief: buyer
(browse/buy, recommendations, wishlist, orders, fraud alerts, disputes),
seller (catalog/inventory, orders, trust dashboard, fraud risk, disputes),
and admin (users, analytics, fraud dashboard, disputes, trust monitoring,
blockchain explorer).

## Running it locally

```bash
cd frontend
npm install
cp .env.example .env.local     # VITE_API_URL, defaults to http://localhost:8000/api/v1
npm run dev                    # http://localhost:5173
```

Needs the backend running (see `../backend/README.md`) — CORS on the
backend already allows `http://localhost:5173` by default.

```bash
npm run build      # tsc -b && vite build — type-checks the whole app, then bundles
npm run preview    # serve the production build locally
```

After changing a backend Pydantic schema or route, regenerate the types
this app builds against:

```bash
npm run types:sync   # exports the backend's OpenAPI schema, then regenerates src/types/schema.ts
```

Needs the backend's Python environment active (`types:export` imports
`app.main` directly — no running server required, just the dependencies).

## Structure

| Path | What it is |
|---|---|
| `src/api/` | One typed module per backend resource (`auth.ts`, `products.ts`, `orders.ts`, `trust.ts`, `fraud.ts`, `recommendations.ts`, `disputes.ts`, `wishlist.ts`, `reviews.ts`, `admin.ts`) — thin wrappers over `client.ts`'s axios instance, not a generic fetch-everywhere pattern. |
| `src/api/client.ts` | The axios instance: attaches the access token to every request, and on a 401 does a single-flight refresh (concurrent 401s share one `/auth/refresh` call rather than each rotating the refresh token and invalidating the others) before retrying the original request once. |
| `src/types/index.ts` | Type aliases over `./schema.ts`'s generated types (one line per backend schema, plus a small `FraudLog.risk_factors` refinement OpenAPI can't express) — see `types:generate` below. |
| `src/types/schema.ts` | **Generated** — `npm run types:sync` (do not hand-edit). Reflects `backend/app`'s actual OpenAPI schema, so a renamed/removed backend field surfaces as a type error here on next regeneration instead of drifting silently. |
| `src/context/AuthContext.tsx` | Current user, login/register/logout, token bootstrap on load. |
| `src/context/ThemeContext.tsx` | Dark mode: a `.dark` class on `<html>`, persisted in `localStorage`, defaulting to `prefers-color-scheme`. |
| `src/components/layout/` | `PublicLayout` (landing/login/signup), `DashboardLayout` (role-aware nav + navbar, shared by all three roles), `ProtectedRoute` (redirects unauthenticated users to `/login`, wrong-role users to their own home). |
| `src/components/ui.tsx` | Design-system primitives: `Button`, `Card`, `Badge`, `Input`/`Select`/`TextArea`, `StatTile`, `Spinner`/`LoadingBlock`, `EmptyState`, `ErrorBanner`, `PageHeader`. Everything else is built from these rather than one-off styles per page. |
| `src/components/domain.tsx` | Small domain-specific badges (`TrustScoreBadge`, `FraudBadge`, `OrderStatusBadge`, `DisputeStatusBadge`) that translate a raw value into a colored, labeled pill consistently everywhere it appears. |
| `src/pages/buyer/`, `src/pages/seller/`, `src/pages/admin/` | Role-specific pages. |
| `src/pages/shared/` | `FraudAlertsPage`, `DisputesPage`, `SettingsPage` — the underlying backend endpoints are already role-scoped (a buyer/seller/admin hitting `GET /disputes` gets different data automatically), so one component adapts its available actions by role (`useAuth().user.role`) instead of three near-identical pages. |

## Design decisions worth knowing for a viva

- **Tailwind v4, config-in-CSS.** No `tailwind.config.js` — theme tokens
  (the brand palette, reused from the Streamlit prototype's `theme.py` so
  both surfaces read as one product) live in `src/index.css`'s `@theme`
  block, and dark mode is a `@custom-variant` keyed off a `.dark` class
  rather than `prefers-color-scheme` alone, so the in-app toggle works.
- **React Query, not manual `useEffect`+`useState` fetching.** Every page
  gets loading/error states, caching, and refetch-on-mutation for free via
  `useQuery`/`useMutation` — the alternative is the same boilerplate
  copy-pasted into every page.
- **Role-aware shared pages over role-duplicated ones.** `FraudAlertsPage`,
  `DisputesPage`, and `SettingsPage` are each one component mounted at
  three different routes (`/buyer/...`, `/seller/...`, `/admin/...`),
  branching on `user.role` for which actions to show (an admin sees
  arbitrate/review buttons; a buyer/seller sees evidence submission).
  Backend authorization does the actual data-scoping — the frontend branch
  is presentational, not a security boundary.
- **Types are generated from the backend's OpenAPI spec**, not
  hand-duplicated. `npm run types:sync` runs
  `backend/scripts/export_openapi.py` (no DB or running server needed —
  it just imports the FastAPI app) then `openapi-typescript` over the
  result, writing `src/types/schema.ts`. `src/types/index.ts` re-exports
  friendly names as aliases over it (`export type Product =
  components['schemas']['ProductRead']`) so every existing `import type
  {...} from '../types'` across the app kept working unchanged — the
  migration touched one file, not every call site. One field
  (`FraudLog.risk_factors`) is manually refined afterward since it's
  typed as a bare `dict` on the backend and OpenAPI can't express its
  actual per-key shape.
- **`openapi-typescript`'s `typescript` peer range (`^5.x`) lags this
  project's TypeScript version.** Rather than downgrading TypeScript or
  installing with `--legacy-peer-deps` (which silently disables npm's
  peer-dependency auto-install — it's what broke `recharts`' `react-is`
  peer during this migration until diagnosed), `package.json` has a
  targeted `overrides` entry pinning the peer typescript resolution to
  `$typescript` — the standard fix for exactly this "tool's peer range is
  behind a very new language release" situation, and it doesn't touch
  peer resolution for anything else in the tree.
- **Role-section pages are route-split.** `src/App.tsx` lazy-loads every
  buyer/seller/admin dashboard page via `React.lazy` + a single
  `<Suspense>` around the router; landing/login/signup stay eager since
  every visitor hits one of them regardless of role. Cut the initial JS
  chunk from ~750KB to ~266KB (gzipped: ~223KB → ~83KB) — `recharts`
  (the heaviest single dependency) now only loads for the trust/admin
  dashboards that actually render charts.

## Verified against the real backend

This was actually run, not just type-checked: with the backend live
against a fresh SQLite DB, a headless-browser script drove the app
end-to-end — landing page → seller signup → seller dashboard (trust score
correctly lazy-computed and displayed, "75 — Trusted") → dark mode toggle
(persists across logout/login, confirming `localStorage` persistence) →
add a product → log out → buyer signup → browse → open the product →
place an order → order appears in "My orders" with the correct amount and
`created` status. Zero browser console errors across the whole run. That
exercises the full stack per request: React form → axios → FastAPI →
SQLAlchemy → the fraud-scoring service → the order response → React
Query's cache → the rendered UI.
