# Deployment

This folder documents deployment; the actual Dockerfiles and compose files
live next to what they build (`backend/Dockerfile`, `frontend/Dockerfile`,
`docker-compose.yml` at the repo root) — standard practice, and where
`docker build ./backend` etc. expect to find them.

**What's actually been verified vs. just written:** the backend (137
pytest tests, 129 with zero external services + 8 against a real local
Hardhat chain), the frontend (Playwright E2E against a live backend), and
the smart contracts (10 Hardhat tests) have all been run for real — plus
a full manual run against a live local chain (deploy → register a seller
on-chain → place and deliver a real order → watch the trust score move
on-chain via a real mined transaction).

**Render deployment has also actually been run**, not just written —
live at [ondc-frontend.onrender.com](https://ondc-frontend.onrender.com) /
[ondc-backend-5kxh.onrender.com](https://ondc-backend-5kxh.onrender.com).
Getting there caught three real bugs no amount of local review would
have (Postgres and Docker aren't available in every dev environment, and
none of these are things SQLite/localhost would ever surface):

1. **`alembic upgrade head` failed on Postgres** — a migration's
   revision id was 33 characters, one over Alembic's default
   `alembic_version.version_num VARCHAR(32)`. SQLite doesn't enforce
   column-length limits, so this was invisible until the first real
   Postgres deploy (`psycopg.errors.StringDataRightTruncation`).
   Revision id shortened.
2. **nginx refused to start** — it resolves `proxy_pass` hostnames at
   config-load time by default and hard-fails if they don't exist.
   `backend` (the docker-compose service name) doesn't exist on Render,
   where each service is isolated. Switched to nginx's lazy-resolution
   pattern (`resolver` + a variable) so it starts regardless.
3. **The deployed frontend silently couldn't reach the backend at all**
   — `render.yaml`'s placeholder `VITE_API_URL` (`ondc-backend.onrender.com`)
   didn't match the hostname Render actually assigned
   (`ondc-backend-5kxh.onrender.com` — the plain name was already taken
   by another Render account; hostnames are global). The app *looked*
   fine — it loaded, nothing crashed — every API call just failed. Found
   by fetching the deployed JS bundle and grepping for the actual baked-in
   URL rather than trusting the dashboard's "live" status.

All three were diagnosed using real deploy logs/bundles pulled via the
Render API, not guessed at from first principles.

## Three ways to run this, in increasing order of "production-like"

### 1. Host-native (what was actually used to develop and test this)

Backend: `backend/README.md`'s "Running it locally" section (venv +
`uvicorn`). Frontend: `frontend/README.md` (`npm run dev`). Fastest
iteration loop, what you want for development.

### 2. Docker Compose (single machine, containerized)

```bash
cp .env.example .env    # fill in JWT_SECRET_KEY at minimum
docker compose up --build
```

Brings up Postgres, Redis, the backend, and the frontend (nginx serving
the built React app, proxying `/api/` to the backend container — see
`frontend/nginx.conf`). The backend's `docker-entrypoint.sh` runs
`alembic upgrade head` before starting, so a fresh container always
matches the current schema. Frontend at `http://localhost:8080`, backend
directly at `http://localhost:8000` (mostly for `/docs`; the frontend
talks to it through the nginx proxy, not this port).

The fraud model artifact, training dataset, and blockchain contract
ABIs/deployment addresses are mounted read-only from the host
(`./trained_models`, `./datasets`, `./artifacts`, `./deployments`) rather
than baked into the backend image — all four are optional (see
`backend/README.md`'s design-decisions section for what happens when
they're absent), and mounting them means retraining the model or
redeploying contracts doesn't require rebuilding the image.

### 3. Render (managed hosting) — what's actually deployed

`render.yaml` at the repo root is a
[Render Blueprint](https://render.com/docs/blueprint-spec) — connecting
this repo on Render provisions Redis and both Docker services from that
one file. Unlike Docker Compose's same-origin nginx proxy, each Render
service gets its own public hostname, so this configuration is
cross-origin instead: the frontend is built with an absolute
`VITE_API_URL` pointing at the backend's real Render URL (there's no
Blueprint mechanism to reference another service's *public* hostname
dynamically — `fromService`'s `host` property is the internal one — so
this had to be hardcoded once the real hostname was known, see
`render.yaml`'s comment), and the backend's `CORS_ORIGINS` is set to the
frontend's Render URL. `JWT_SECRET_KEY` is `generateValue: true` — Render
generates a real random secret rather than using any placeholder.

**Postgres is deliberately not a Render-managed `databases:` entry.**
Render's free Postgres expires 30 days after creation and is deleted 14
days after that
([render.com/docs/free](https://render.com/docs/free#free-postgresql-databases))
— the opposite of what a project meant to keep running wants. `DATABASE_URL`
is a `sync: false` env var instead, pointing at a free-forever
[Neon](https://neon.tech) Postgres instance (never deletes data; scales
compute to zero when idle and wakes itself automatically on the next
request — no manual "resume" step, unlike some alternatives). `sync:
false` means the value is set once via the Render dashboard/API and never
stored in `render.yaml` or git history — the actual connection string is
a real credential and doesn't belong in a public repo.

Redis stayed on Render's free tier — its free-tier terms don't include
Postgres's expiration policy (worst case, an occasional forced restart
clears cached data, which the app already tolerates gracefully by
design; see `backend/app/core/cache.py`).

Railway works the same way conceptually (build each Dockerfile as a
service, add managed Postgres + Redis, wire the env vars) but Railway
doesn't have an equivalent single-file blueprint format as of this
writing, so it'd be configured through their dashboard/CLI directly
rather than a committed file here.

## CI

`.github/workflows/ci.yml` runs on every push/PR: backend tests (pytest,
SQLite, zero external services), frontend type-check + build, and the
Hardhat contract test suite — three independent jobs so one toolchain's
failure doesn't hide the other two's results. It does not build or push
the Docker images — that's a reasonable next step once this is connected
to a real registry, not added speculatively here.

## Environment variables reference

| Variable | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | backend | Postgres connection string. Accepts a plain `postgres://`/`postgresql://` URL (what Render/Railway/Neon hand out) — `app/core/config.py` normalizes it to the `+psycopg` driver SQLAlchemy needs. On Render, this is a `sync: false` var set directly via the dashboard/API, not stored in `render.yaml` — see the Render section above for why. |
| `REDIS_URL` | backend | Backs hot-read caching (trust scores, product listings) and refresh-token revocation — see `app/core/cache.py`. Fails open if unreachable (falls straight through to the DB / revocation just isn't enforced), so it's never a hard dependency. |
| `JWT_SECRET_KEY` | backend | **Must** be a real random secret in any non-local deployment — never the checked-in placeholder. |
| `CORS_ORIGINS` | backend | Comma-separated origins allowed to call the API from a browser. |
| `BLOCKCHAIN_ENABLED` / `BLOCKCHAIN_RPC_URL` / `BLOCKCHAIN_NETWORK` / `BLOCKCHAIN_PRIVATE_KEY` | backend | Off by default. See `backend/README.md`'s blockchain-bridge section — the private key must be the contract owner's, not just any funded account. |
| `VITE_API_URL` | frontend (build-time) | Where the browser sends API requests. Relative (`/api/v1`) for the nginx-proxied Docker Compose setup; absolute for Render/anything cross-origin. |
| `SEPOLIA_RPC_URL` / `PRIVATE_KEY` | contracts | Only needed to run `npx hardhat run scripts/deploy.js --network sepolia` — see the root README's Smart Contracts section. |
