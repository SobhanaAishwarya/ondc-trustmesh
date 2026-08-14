# Deployment

This folder documents deployment; the actual Dockerfiles and compose files
live next to what they build (`backend/Dockerfile`, `frontend/Dockerfile`,
`docker-compose.yml` at the repo root) — standard practice, and where
`docker build ./backend` etc. expect to find them.

**What's actually been verified vs. just written:** the backend (137
pytest tests, 129 with zero external services + 8 against a real local
Hardhat chain), the frontend (Playwright E2E against a live backend), and
the smart contracts (10 Hardhat tests) have all been run for real in this
environment — including a full manual run against a live local chain
(deploy → register a seller on-chain → place and deliver a real order →
watch the trust score move on-chain via a real mined transaction). The
Docker images,
`docker-compose.yml`, `render.yaml`, and the CI workflow have been written
and reviewed carefully but **not** run — there's no Docker daemon in this
environment. Same situation as the Sepolia contract deployment: the code
is real and ready, but "I wrote this correctly" and "I watched it run" are
different claims, and this README doesn't blur them.

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

### 3. Render (managed hosting)

`render.yaml` at the repo root is a
[Render Blueprint](https://render.com/docs/blueprint-spec) — connecting
this repo on Render provisions Postgres, Redis, and both Docker services
from that one file. Unlike Docker Compose's same-origin nginx proxy, each
Render service gets its own public hostname, so this configuration is
cross-origin instead: the frontend is built with an absolute
`VITE_API_URL` pointing at the backend's Render URL, and the backend's
`CORS_ORIGINS` is set to the frontend's Render URL. Both are placeholder
`ondc-backend`/`ondc-frontend` hostnames in the file — Render assigns the
real ones on first deploy, so a second deploy (or manually editing the
two env vars in the dashboard) is needed to point them at each other
correctly. `JWT_SECRET_KEY` is set to `generateValue: true` — Render
generates a real random secret rather than using any placeholder.

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
| `DATABASE_URL` | backend | Postgres connection string. Accepts a plain `postgres://`/`postgresql://` URL (what Render/Railway hand out) — `app/core/config.py` normalizes it to the `+psycopg` driver SQLAlchemy needs. |
| `REDIS_URL` | backend | Provisioned, not yet used by application code (see backend/README.md's "what's next"). |
| `JWT_SECRET_KEY` | backend | **Must** be a real random secret in any non-local deployment — never the checked-in placeholder. |
| `CORS_ORIGINS` | backend | Comma-separated origins allowed to call the API from a browser. |
| `BLOCKCHAIN_ENABLED` / `BLOCKCHAIN_RPC_URL` / `BLOCKCHAIN_NETWORK` / `BLOCKCHAIN_PRIVATE_KEY` | backend | Off by default. See `backend/README.md`'s blockchain-bridge section — the private key must be the contract owner's, not just any funded account. |
| `VITE_API_URL` | frontend (build-time) | Where the browser sends API requests. Relative (`/api/v1`) for the nginx-proxied Docker Compose setup; absolute for Render/anything cross-origin. |
| `SEPOLIA_RPC_URL` / `PRIVATE_KEY` | contracts | Only needed to run `npx hardhat run scripts/deploy.js --network sepolia` — see the root README's Smart Contracts section. |
