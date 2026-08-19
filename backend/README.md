# Backend core

FastAPI + PostgreSQL backend for the Blockchain-AI Enhanced ONDC project.
This is **module 1** of the production stack described in the project
brief — database models, migrations, config, and JWT authentication for
all three roles (buyer/seller/admin). Later modules (product catalog,
orders, fraud/recommendation services, blockchain integration, dispute
resolution) build on top of what's here.

The existing Streamlit prototype at the repo root (`app.py`, `pages/`,
`ml/`, `blockchain/`) is unrelated and untouched — it stays as a fast,
dependency-light demo of the same trust/fraud/recommendation/dispute
concepts. This backend is the real, deployable implementation.

## Why this structure

`database/schema.sql` (one level up) is the documented source of truth for
the relational model — it explains *why* each table looks the way it does
(UUID keys, `trust_scores` as a time series, `blockchain_hashes` as an
append-only audit trail, etc.). Everything under `app/models/` and
`alembic/versions/0001_initial_schema.py` mirrors it exactly. If the schema
ever needs to change, update `schema.sql` first, then the ORM models, then
write a migration — in that order, so there's always one place that
describes intent and two places that implement it identically.

## Folder-by-folder

| Path | What it is |
|---|---|
| `app/core/config.py` | `Settings` (pydantic-settings) — the only place environment variables are read. Everything else calls `get_settings()`. |
| `app/core/security.py` | Password hashing (`bcrypt` directly — see below) and JWT issuance/verification. Every token carries a `jti`, used for refresh-token revocation. |
| `app/core/cache.py` | Thin Redis wrapper (hot-read caching, refresh-token revocation blocklist) — fails open if Redis is unreachable, same no-op pattern as `blockchain_service.py`. |
| `app/core/geo.py` | City-level buyer/seller distance for the recommendation engine's proximity signal (haversine over a fixed list of major Indian cities — no geocoding provider wired up). |
| `app/db/types.py` | `GUID` and `StringArray` — TypeDecorators that render as native `UUID`/`ARRAY` on Postgres and as portable equivalents on SQLite, so the same models back both production and the test suite. |
| `app/db/base.py` | The shared `DeclarativeBase` every model inherits. |
| `app/db/session.py` | Engine, `SessionLocal`, and the `get_db` FastAPI dependency. |
| `app/models/` | One file per table in `schema.sql` (12 tables) — `User`, `Buyer`, `Seller`, `Product`, `Order`, `Transaction`, `BlockchainHash`, `TrustScore`, `Dispute`, `Recommendation`, `FraudLog`, `Review`. |
| `app/schemas/user.py`, `product.py`, `order.py` | Pydantic request/response models. Separate from the ORM models on purpose — request/response shape and DB shape drift over time and shouldn't be forced to match. |
| `app/schemas/common.py` | `Page[T]` — the generic paginated-list envelope (`items`, `total`, `limit`, `offset`) used by every list endpoint. |
| `app/api/deps.py` | `get_current_user`/`require_role(...)` for auth, plus `get_current_buyer`/`get_current_seller` which resolve the role-specific profile row (`Buyer`/`Seller`) for the authenticated user — every product/order endpoint that needs "the caller's own X" depends on these. |
| `app/api/v1/endpoints/auth.py` | `/register/buyer`, `/register/seller`, `/login`, `/me`, `/refresh` (rotates + revokes the used refresh token), `/logout` (revokes on demand), and `/wallet/nonce`+`/wallet/link`+`/wallet/login` — decentralized identity via a signed challenge (`eth_account.Account.recover_message`), not a pasted address. |
| `app/api/v1/endpoints/products.py` | Seller-owned catalog CRUD + public search/browse. Listing and detail reads are Redis-cached (short TTL, invalidated on write). |
| `app/api/v1/endpoints/orders.py` | Placing orders (which also creates the Transaction), tracking, seller-driven status transitions, and `POST /{id}/return` — the self-service return/refund flow (return-window + condition check, auto-refund or falls back to a contested dispute). |
| `app/ml/features.py` | The fraud model's feature schema — one definition shared by training and live scoring so they can't drift apart (train/serve skew). |
| `app/ml/synthetic_data.py` | Generates labeled synthetic transactions over that exact feature schema (no real ONDC fraud dataset exists — same situation as the Streamlit prototype). |
| `app/ml/model.py` | Trains the RandomForest pipeline, saves/loads the artifact, and exposes `get_fraud_model()` — a process-wide singleton with a train-on-demand fallback if no artifact is on disk. |
| `app/services/fraud_service.py` | Scores one transaction: pulls live features from the DB, calls the model, writes `Transaction.fraud_probability`/`is_fraud_flagged`, and records a `FraudLog` with lightweight explainability. |
| `app/api/v1/endpoints/fraud.py` | `/fraud/alerts` (role-scoped) and the admin fraud-log review endpoint. |
| `scripts/train_fraud_model.py` | Regenerates the training set and the model artifact, prints evaluation metrics. Run this after changing `features.py` or `synthetic_data.py`. |
| `scripts/evaluate_recommendation_ctr.py` | Self-contained synthetic CTR backtest for the real `recommendation_service.get_recommendations()` — see its docstring for what it does and doesn't prove. |
| `app/services/trust_service.py` | Trust-score computation — the multi-factor formula from `schema.sql`'s `trust_scores` table (completion rate, transaction success, ratings, complaints, refund ratio, late delivery, fraud probability, disputes, seller age), distinct from the simpler on-chain event-delta model in `contracts/TrustScore.sol`. Persists a time-series row and syncs `Seller.current_trust_score`. |
| `app/api/v1/endpoints/trust.py` | Public current-score lookup (lazy-computes on first read, Redis-cached with a short TTL and invalidated the moment a recompute happens), history, and a manual recompute trigger (seller-self or admin). |
| `app/api/v1/endpoints/reviews.py` | Buyer reviews on delivered orders — one per order; posting one recomputes the seller's trust score. |
| `app/services/recommendation_service.py` | Hybrid recommender: TF-IDF/cosine content-based scoring, item-based collaborative filtering (co-purchase counts), a seller-trust blend, a city-level proximity/delivery-capability blend (`app/core/geo.py`), and a popularity-based cold-start fallback. |
| `app/api/v1/endpoints/recommendations.py` | Ranked list for the caller (logs impressions), click tracking, and an admin CTR report. |
| `app/services/dispute_service.py` | Automated dispute resolution — ported from the prototype's `ml/dispute_resolution.py`, using the real persisted seller trust score plus an ephemeral (non-persisted) buyer-trust heuristic. |
| `app/api/v1/endpoints/disputes.py` | Raise a dispute, submit evidence (auto-resolves once both sides have), admin arbitration override, role-scoped listing. |
| `app/models/wishlist.py`, `app/api/v1/endpoints/wishlist.py` | Buyer wishlist — the one table added after the original 12 (see `alembic/versions/0002_add_wishlist.py`). |
| `app/api/v1/endpoints/admin.py` | User management (list/filter/deactivate) and a consolidated analytics endpoint (users/products/orders/revenue/fraud rate/avg trust/disputes), plus `/admin/blockchain-hashes` — the on-chain audit trail. |
| `app/blockchain/client.py` | Web3.py bridge to the deployed `TrustScore`/`EscrowDispute` contracts — connection, contract loading from `deployments/<network>.json`, the raw `register`/`recordEvent`/`scoreOf` calls, and the escrow lifecycle (`create_escrow_order`/`confirm_escrow_delivery`/`raise_escrow_dispute`/`autoresolve_escrow`/`arbitrate_escrow`). |
| `app/services/blockchain_service.py` | Ties DB entities to the client above: best-effort (catches and logs, never raises) so a down/unconfigured chain never breaks placing an order, delivering one, raising a dispute, or flagging fraud. `register_seller_onchain`/`register_buyer_onchain` are symmetric — `TrustScore.sol`'s `register()` doesn't distinguish participant roles. The matching escrow wrappers (`create_escrow_order`, `confirm_escrow_delivery`, `raise_escrow_dispute`, `resolve_escrow_dispute`) are what `orders.py`/`disputes.py` actually call — see `documentation/05_testing_and_results.md`'s "Escrow wiring" section for why this existed as unused contract code for a while and what closing that gap involved. |
| `app/services/transaction_service.py` | One function: syncs `Transaction.status` to `refunded` when a dispute/return resolution sends the buyer any share of the amount back — closes a real gap where `TransactionStatus.refunded` was defined and read by `trust_service`'s refund-ratio math but never actually written anywhere. |
| `app/core/logging.py` | Stdlib `logging` configuration (not JSON/structlog — a deliberate scope call, see the design-decisions section). |
| `app/core/limiter.py` | The shared `slowapi` `Limiter` instance, in its own module so endpoint files can import it for `@limiter.limit(...)` without a circular import back to `main.py`. |
| `app/main.py` | FastAPI app instance: CORS, the rate-limit middleware/handler, a per-request logging middleware (method/path/status/latency + an `X-Request-ID`), global exception handlers (validation errors and unhandled exceptions both get a consistent `{"detail": ...}` envelope), router wiring, `/health`. |
| `alembic/` | Migration tooling. `env.py` reads the DB URL from `Settings` rather than a hardcoded string, so app and migrations always target the same database. Three migrations: `0001_initial_schema` (the 12 original tables), `0002_add_wishlist`, `0003_add_buyer_onchain_registered`. |
| `scripts/create_admin.py` | Creates the first admin account directly in the DB (see "Why no admin registration endpoint" below). |
| `scripts/export_openapi.py` | Writes the live OpenAPI schema to `frontend/openapi.json` — the input `npm run types:generate` (frontend) turns into `frontend/src/types/schema.ts`. No DB or running server needed. |
| `docker-compose.dev.yml` | Local Postgres + Redis only — enough to run migrations and the API locally. The full multi-service stack arrives in the `deployment/` module. |
| `tests/` | `conftest.py` swaps in an in-memory SQLite DB via dependency override, so `pytest` runs in-process with no external services, plus an `admin_token` fixture (creates an admin directly in the DB, mirroring `scripts/create_admin.py` — there's no public admin-registration endpoint to hit instead). One file per feature area. |

## Design decisions worth knowing for a viva

- **`bcrypt` directly, not `passlib`.** `passlib`'s bcrypt backend probes
  `bcrypt.__about__.__version__`, which was removed in `bcrypt>=4.1` — a
  well-known breakage. Calling `bcrypt.hashpw`/`checkpw` directly avoids it
  entirely and is only a few lines.
- **No public `/auth/register/admin` endpoint.** If admin signup were open,
  anyone could POST their way into an admin role. The first admin is
  created via `scripts/create_admin.py` (same idea as Django's
  `createsuperuser`); further admins would be provisioned by an existing
  admin through a future admin-management endpoint, not self-service.
- **UUID primary keys everywhere**, generated client-side
  (`default=uuid.uuid4`) with a Postgres `gen_random_uuid()` server-side
  fallback for any row inserted outside the ORM — matches `schema.sql`'s
  documented reasoning: safe to expose in URLs, no row-count leakage.
- **SQLite for tests, Postgres for everything else.** `GUID`/`StringArray`
  are the standard SQLAlchemy "backend-agnostic type" recipe, not a
  simplified schema — `alembic/versions/0001_initial_schema.py` still
  creates real Postgres `UUID[]`/`ARRAY`/`ENUM` columns for the actual
  database.
- **One product per order, no `order_items` table.** `schema.sql` models
  `orders` with a single `product_id` + `quantity`, not a cart-style
  line-items table — that's an existing schema decision, not a
  simplification made here, so `POST /orders` takes one product at a time.
- **`DELETE /products/{id}` soft-deletes** (`is_active = False`) instead of
  removing the row. Orders reference `product_id` by foreign key, so a hard
  delete would either fail (FK constraint) or silently break historical
  order data once real orders exist against that product.
- **No payment gateway yet, so `POST /orders` simulates settlement**: COD
  transactions are recorded `pending` (they settle on delivery), every
  other method is recorded `success` immediately. This is the seam where a
  real gateway (Razorpay/Stripe webhook, etc.) plugs in later — the rest of
  the order flow (stock, status transitions) doesn't change.
- **Order status transitions are a fixed state machine**
  (`created → confirmed/cancelled → shipped/cancelled → delivered`),
  enforced server-side in `orders.py`, not left to the client to get right.
  Cancelling restocks the product. `disputed`/`resolved` are deliberately
  not reachable from this endpoint — those belong to the dispute-resolution
  module, which will own that transition.
- **The fraud model's feature set is not the Streamlit prototype's.** The
  prototype (`ml/fraud_model.py`) scores completed transactions offline and
  can use `delivery_time_hours`/`distance_km`. This model scores a
  transaction the instant `POST /orders` creates it — before delivery
  happens and with no location data collected anywhere in the schema — so
  using either would mean training on information that doesn't exist yet
  at decision time. `app/ml/features.py` documents the full reasoning.
  Location-anomaly detection is a real follow-up, but it needs an
  address/geo column added to buyers/sellers first, not a faked feature.
- **Explainability is a lightweight ranking, not SHAP.** `fraud_service.py`
  ranks each feature by `global_importance × |z-score vs. training mean|`
  and stores the top 3 as `FraudLog.risk_factors`. That's honest about what
  it is: a fast, dependency-free approximation good enough to show "why was
  this flagged" in a demo, not a proper Shapley-value decomposition.
- **Fraud scoring runs synchronously inside `POST /orders`**, not on a
  queue. `predict_proba` on this model is low-single-digit milliseconds;
  a background worker would be solving a scale problem this project
  doesn't have yet.
- **Refresh tokens are single-use, enforced via a Redis blocklist keyed by
  `jti`.** `/auth/refresh` rotates both tokens *and* revokes the just-used
  refresh token in the same call, and `/auth/logout` revokes on demand —
  see the "Caching and refresh-token revocation both fail open" bullet
  below for what happens when Redis itself is unreachable.
- **Trust score weights are picked so the range is actually reachable**:
  a seller with perfect rates/rating/tenure and zero negatives scores
  exactly 100; a seller with every rate at its worst clamps to 0 with
  room to spare. This mattered — an earlier version of the formula could
  only reach ~82 in practice, which is a wrong ceiling for a 0–100 score.
- **"Late delivery" is measured against an assumed 5-day SLA**
  (`LATE_DELIVERY_SLA_DAYS` in `trust_service.py`), not a per-order
  deadline — there's no such column in `schema.sql`. A documented modeling
  assumption over real timestamps, not fabricated data.
- **Buyer trust for dispute resolution is ephemeral, not persisted.**
  `schema.sql`'s `trust_scores` table only has a `seller_id` column — there's
  no buyer-side trust storage, and adding one wasn't warranted for one
  formula input. `dispute_service.ephemeral_buyer_trust()` computes a
  lighter-weight heuristic (fraud flag + account age) on the fly instead.
- **Recommendation "user embeddings" are engineered, not neural.** The
  brief asks for user embeddings; at this data volume a learned embedding
  model would be undertrained noise. The buyer profile driving content
  scoring is preferred-categories + purchase-history categories through a
  TF-IDF vectorizer — a real, explainable vector representation, just not
  a deep one.
- **Collaborative filtering is item-based co-occurrence** ("buyers who
  bought X also bought Y" via `Order` history), not matrix factorization —
  the right-sized technique for sparse, small interaction data, and it
  degrades gracefully (empty dict, hybrid score falls back to
  content+trust+popularity) rather than erroring when a buyer has no
  purchase history yet.
- **CTR is measured from real logged impressions** (`Recommendation` rows
  written every time `/recommendations` is called), not the prototype's
  simulated backtest — `GET /recommendations/ctr` is honest live telemetry,
  which will read as 0 until real usage accumulates rather than showing a
  pre-baked "impressive" number. For an offline read on the Infosys ~20%
  CTR-lift KPI ahead of that real traffic existing, `scripts/evaluate_
  recommendation_ctr.py` runs a clearly-labeled synthetic backtest — a
  synthetic catalog and buyers, but the *actual* `get_recommendations()`
  code, not a reimplementation — and reports the real number that comes
  out, not a target. See the script's docstring for the full disclosure
  before quoting its output anywhere.
- **Proximity is city-level, not GPS.** No geocoding provider is wired up,
  so `buyers.city`/`sellers.city` are one of `app.core.geo.CITY_NAMES`
  (a fixed list of major Indian cities) rather than raw lat/lng — accurate
  enough to rank nearby, faster-shipping sellers higher without a maps API
  key or address-precision data this project doesn't have. Either city
  being unset scores neutral (0.5), never a penalty.
- **Caching and refresh-token revocation both fail open, deliberately.**
  `app/core/cache.py` catches every `redis.RedisError` and returns/no-ops
  as if the key were absent — Redis being down degrades to "no caching"
  (a DB read happens instead) and "no revocation enforced" (a revoked
  token would still work), never a 500. Access tokens are *not* checked
  against the revocation blocklist on every request — only the refresh
  flow does, so Redis never sits on the hot path of a normal authenticated
  request. This is the same tradeoff `blockchain_service.py` makes for an
  unreachable chain, applied to a second external dependency.
- **Returns reuse the `Dispute` model rather than adding a `Return`
  table.** A self-service return within the policy window and in good
  condition creates a `Dispute` row that's already `auto_resolved`
  (`resolved_by="auto_return"`, `seller_share_bps=0`) — same shape the
  admin/seller-facing dispute UI already renders, no new endpoint contract
  to learn. A damaged/incomplete-condition return creates an `open`
  dispute instead, falling back to the real evidence-weighted flow rather
  than approximating a decision the seller should get to weigh in on.
- **Dispute auto-resolution needs both sides' evidence before firing.**
  Raising a dispute only records the raiser's evidence; the other party
  calls `POST /disputes/{id}/evidence`, and resolution triggers the moment
  both scores exist — no manual "resolve now" button, matching "automated
  dispute resolution" literally rather than just providing the formula.
- **Autoflush is off** (`sessionmaker(..., autoflush=False)`), so any code
  path that writes a row and then immediately queries an aggregate over it
  in the same request (delivering an order → trust recompute; posting a
  review → trust recompute) needs an explicit `db.flush()` in between, or
  the aggregate silently reads stale data. Two real bugs of exactly this
  shape got caught by tests and fixed in `orders.py`/`reviews.py` — worth
  knowing before adding the next feature that chains a write into a read.
- **On-chain sync is best-effort, gated by `BLOCKCHAIN_ENABLED` (off by
  default).** Every function in `blockchain_service.py` catches and logs
  rather than raising — the chain being down must never break checkout, a
  delivery, a dispute, or a fraud flag. This was verified against a real
  local chain, not assumed: with the wrong operator key configured
  (an account the contract owner never authorized), a live end-to-end run
  logged `TrustScore: not authorized` and the API request still succeeded
  — exactly the intended degradation.
- **`wallet_address` can no longer be set as plain text at all.** It used
  to be format-validated (`0x` + 40 hex chars) but otherwise trusted —
  `PATCH /auth/me` would accept any string of the right shape with no
  proof the caller actually controlled that address, which is the exact
  gap a real "decentralized identity" claim needs closed. It's now only
  ever set by `POST /auth/wallet/link`, which requires a signature over a
  one-time server-issued nonce (`app/core/cache.py`'s `wallet_nonce_*`,
  deliberately fail-*closed* — see its docstring — unlike the rest of that
  module) recovered via `eth_account.Account.recover_message`. A
  malformed-address bug used to slip through the old free-text path and
  fail silently inside `register_seller_onchain`'s best-effort try/except;
  the new flow can't have that failure mode since nothing reaches
  `wallet_address` without a verified signature first.
- **`BLOCKCHAIN_PRIVATE_KEY` must be the contract owner (or an address it
  authorized via `setReporter`)**, not just any funded account —
  `TrustScore.sol`'s `register`/`recordEvent` are `onlyAuthorized`. Using
  the wrong key doesn't crash anything (see above) but silently no-ops
  every on-chain write, which is confusing to debug if you don't know to
  check `/admin/blockchain-hashes` for missing rows.
- **On-chain registration triggers off a *verified* wallet, not off seller
  registration.** A seller has no wallet at signup; the moment they
  successfully link one (`POST /auth/wallet/link`, real signature
  required), `register_seller_onchain` fires — gated on both
  `wallet_address` and `wallet_verified`, not `wallet_address` alone.
  MetaMask/client-side signing *does* exist now (`frontend/src/lib/
  wallet.ts` + `WalletConnectButton` — `personal_sign` over a server
  nonce), which is a real, if partial, decentralized-identity story:
  logging in/linking cryptographically proves the caller holds the
  private key for that address. What's still relayer-based, and worth
  being precise about in a demo: the *on-chain contract calls themselves*
  (`register`/`recordEvent`) are signed by the backend's own operator key,
  not the user's — a buyer/seller proves key ownership to authenticate,
  but doesn't sign their own blockchain transactions yet.
- **On-chain events reuse the exact vocabulary** `contracts/TrustScore.sol`
  and the Streamlit prototype's `blockchain/chain.py` already defined
  (`successful_delivery`, `dispute_raised`, `dispute_resolved_seller`,
  `dispute_resolved_buyer`, `fraud_flagged`) — triggered from the same
  places the backend's own `recompute_trust_score` already fires (order
  delivered, dispute raised/resolved, transaction flagged), so the two
  trust models move together even though they're computed differently.
- **The on-chain score and the backend's computed trust score are two
  different numbers by design**, not out of sync by accident. `TrustScore.sol`
  only supports delta adjustments (`recordEvent`), not setting an
  arbitrary value — there's no way to push the backend's multi-factor
  score onto it directly. `GET /trust/sellers/{id}` (computed) and
  `GET /trust/sellers/{id}/onchain` (ledger) are both real, just answering
  different questions: "what's this seller's holistic trust" vs. "what
  does the immutable on-chain event log say."
- **Buyers now get on-chain registration too, not just sellers.**
  `TrustScore.sol`'s `register()` is generic over any participant
  address — the backend just hadn't wired buyers to it (only sellers)
  until `register_buyer_onchain` was added, mirroring the seller path
  exactly, including its own `is_onchain_registered` column
  (`0003_add_buyer_onchain_registered`). Buyers don't get ongoing trust
  *events* recorded yet — the event vocabulary is seller-performance-
  centric — only this initial registration.
- **Rate limiting is per-route, not one global number.** `/auth/login`
  (5/minute) and `/auth/register/*` (10/hour) have their own tight limits
  — the actual brute-force/spam targets — under a generous global default
  (120/minute) for everything else. The limiter's in-memory counters are
  a process-wide singleton (`app/core/limiter.py`), which matters for
  testing: `tests/conftest.py`'s `_reset_rate_limits` autouse fixture
  clears them before/after every test, or a 100+-test suite that
  repeatedly registers/logs-in would start tripping 429s partway through
  a run for reasons that have nothing to do with what each test is
  actually checking.
- **Logging is plain stdlib `logging`, not structlog/JSON.** A
  timestamp+level+logger+message format plus a per-request correlation id
  (`X-Request-ID`, logged and echoed back) covers what this project
  actually needs — readable logs, traceable requests — without a new
  dependency. JSON output is the natural next step if this ever sits
  behind a log aggregator; not built speculatively here.
- **Validation errors and unhandled exceptions share the same
  `{"detail": ...}` envelope** every `HTTPException` in this API already
  uses, rather than FastAPI's default bare-array shape for 422s — a
  client branching on `detail` doesn't need a special case for validation
  failures. Unhandled exceptions (a bug, not an expected error path — every
  expected error is an explicit `HTTPException` throughout this codebase)
  log the full traceback server-side and return a generic message
  client-side, never a stack trace.

## Running it locally

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt

cp .env.example .env            # defaults match docker-compose.dev.yml

docker compose -f docker-compose.dev.yml up -d   # Postgres + Redis
alembic upgrade head                             # creates all 12 tables

python scripts/train_fraud_model.py   # trains + saves trained_models/fraud_model.joblib
                                       # (optional — the API trains a smaller model on the
                                       # fly if this hasn't been run, see app/ml/model.py)

uvicorn app.main:app --reload   # http://localhost:8000/docs
```

Create the first admin account (needs Postgres running and migrated):

```bash
python scripts/create_admin.py --email admin@ondc.example --name "Ops Admin"
```

### Blockchain bridge (optional — off by default)

```bash
cd ..                                                      # repo root
npx hardhat node                                           # separate terminal, keep running
npx hardhat run scripts/deploy.js --network localhost      # writes deployments/localhost.json
```

Then in `backend/.env`: set `BLOCKCHAIN_ENABLED=true` and
`BLOCKCHAIN_PRIVATE_KEY` to the **deployer's** private key (printed by
`npx hardhat node` as "Account #0" — a well-known, public dev-only key,
never use it for anything real). Restart `uvicorn`. Sellers who set a
`wallet_address` via `PATCH /auth/me` now get registered on `TrustScore.sol`
automatically, and `/admin/blockchain-hashes` starts showing real rows.

## Running the tests

No Docker or Postgres required — `tests/conftest.py` points the app at an
in-memory SQLite DB for the duration of the test run:

```bash
pip install -r requirements.txt
pytest -v
```

137 tests currently cover (129 pass with zero external services; the
other 8 need a live local chain, see "What's next" below): password
hashing/JWT round-tripping (incl.
refresh-token rotation, single-use revocation on both `/refresh` and
`/logout`, and type-confusion rejection — an access token can't be used
as a refresh token or vice versa), both registration flows, login,
profile editing with role-appropriate field scoping, the product catalog
(including cache read-through/invalidation with a fake in-memory Redis),
the full order lifecycle and its state machine, the self-service
return/refund flow (window/condition checks, auto-refund vs. falling
back to a contested dispute), the fraud model and its API wiring, the
trust-score formula (including the 0/100 clamp boundaries) and its API
(lazy compute, delivery/review-triggered recompute, ownership-gated
manual recompute, cache invalidation), reviews, the recommendation
engine (cold-start vs. content-based selection, city-level proximity/
vendor matching, click tracking, purchase attribution, admin-gated CTR
reporting), the full dispute lifecycle
(raise → evidence → auto-resolve, and admin arbitration, with access
control at every step), the wishlist, the admin module (user
listing/search/deactivation including self-deactivation prevention and
that deactivation immediately invalidates an existing token, plus the
analytics report against real seeded data), a dedicated security
regression file, per-route rate limiting (including that hitting one
route's limit doesn't lock out an unrelated route), and the global
exception handlers' error envelope. None of this needs a blockchain node,
Docker, or Postgres running.

A separate `tests/test_blockchain_bridge.py` (8 tests) exercises the
Web3.py bridge against a **real local chain** — auto-skipped if nothing
answers at `http://127.0.0.1:8545`. Start one and run them explicitly:

```bash
npx hardhat node                                            # repo root, separate terminal
npx hardhat run scripts/deploy.js --network localhost
pytest tests/test_blockchain_bridge.py -v
```

All 8 pass against a live node: registering a participant, rejecting a
double-registration, `successful_delivery`/`fraud_flagged` moving the
on-chain score by the documented deltas (50 → 52 → 32), the score
clamping at 0 after repeated `fraud_flagged` events, an unreachable RPC
raising `BlockchainUnavailable` cleanly, and — against the same live
chain — `blockchain_service.register_seller_onchain`/
`register_buyer_onchain` actually driving the real client and persisting
the on-chain registration (buyer and seller symmetric, idempotent on a
second call).

**Measured fraud-model accuracy** (from `scripts/train_fraud_model.py`,
n=6000 synthetic transactions, 75/25 train/test split): **90.3%** accuracy,
94.8% ROC-AUC, on an 8% base fraud rate — clears the >85% KPI target.
Precision is lower (44%) than recall (78%): `class_weight="balanced"`
deliberately trades some false positives for catching more real fraud,
which is the right tradeoff for a review queue (a human/admin looks at
flagged transactions) rather than an auto-block. The top three drivers by
global feature importance are `is_new_seller`, `seller_trust_score`, and
`seller_rating` — re-run the script after any change to `features.py` or
`synthetic_data.py` and these numbers will change; don't hand-edit them.

**Recommendation CTR backtest** (from `scripts/evaluate_recommendation_
ctr.py`, default settings — synthetic catalog, synthetic buyers): the
hybrid recommender beats the unpersonalized "current top_k, same for every
buyer" baseline by a wide margin in this synthetic setup. Re-run the script
for the exact current number and read its printed caveat before quoting
it — the size of the lift mostly reflects how weak a static, non-rotating
baseline is, not a tuned result. This is not a substitute for the real
number `GET /recommendations/ctr` will report once the deployed app has
actual buyer traffic; it exists so the ~20% KPI has *some* honest,
reproducible answer in the meantime.

## Security review

```bash
bandit -r app
```

Clean run: **0 medium/high severity findings** across 2,847 lines. Two
low-severity/low-confidence findings (`B105 hardcoded_password_string` on
`TOKEN_TYPE_ACCESS = "access"` and `TOKEN_TYPE_REFRESH = "refresh"` in
`core/security.py`) were reviewed and are false positives — bandit's
heuristic matches any short string assigned near password-handling code;
these are JWT token-type discriminators, not credentials.

`tests/test_security_review.py` (7 tests) checks what static analysis
can't: `password_hash` never appears in any API response, login doesn't
distinguish "wrong password" from "no such account" (email enumeration),
a JWT signed with the wrong secret is rejected, the classic `alg: none`
bypass is rejected, product search is safe against SQL-injection-shaped
input (proving the ORM's parameterization end-to-end, not just by
inspection), and a forged `role: admin` claim in an otherwise-valid buyer
JWT still gets 403 — `require_role` checks the DB row's role, not the
token payload's. `tests/test_rate_limiting.py` (3 tests) and
`tests/test_error_handling.py` (3 tests) cover the two hardening additions
below.

## Load testing

```bash
pip install -r requirements.txt   # includes locust
python loadtest/seed.py --host http://localhost:8000
locust -f loadtest/locustfile.py --host http://localhost:8000 \
    --headless -u 20 -r 5 -t 30s
```

Run for real (not estimated) against a live instance: **501 requests, 0
failures**. Full numbers and analysis in `loadtest/RESULTS.md` — the
short version: reads (`/products`, `/auth/me`) sit at a ~29ms median even
under load; `POST /orders` (stock check, order+transaction creation, and
a live fraud-model inference, all in one request) at ~260ms median; and
`POST /auth/register/buyer` at ~2.7s median under concurrency, which is
explained (bcrypt genuinely costs ~0.46s per hash on this hardware, and a
single `uvicorn` process without `--workers` doesn't parallelize that
CPU-bound work across concurrent requests) rather than hand-waved away,
with the actual fix (multiple worker processes) documented alongside it.

These numbers predate rate limiting (added afterward — see the security
section above). Re-running `loadtest/locustfile.py` today against the
20-concurrent-user profile would show `POST /auth/register/buyer` 429s
after each simulated user's first 10 registrations within an hour —
correct, intended behavior from the new per-route limit, not a
regression in the numbers above.

## API surface so far

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/v1/auth/register/buyer` | none | Create a buyer account, returns access + refresh JWTs |
| POST | `/api/v1/auth/register/seller` | none | Create a seller account, returns access + refresh JWTs |
| POST | `/api/v1/auth/login` | none | Exchange email+password for tokens |
| POST | `/api/v1/auth/refresh` | none (refresh token in body) | Exchange a refresh token for a new token pair (rotates both) |
| GET | `/api/v1/auth/me` | Bearer JWT | Current user + role-specific profile |
| PATCH | `/api/v1/auth/me` | Bearer JWT | Update own profile (name/phone + buyer or seller fields, role-scoped) — rejects `wallet_address`, see below |
| POST | `/api/v1/auth/wallet/nonce` | none | Issue a one-time challenge message for an address to sign |
| POST | `/api/v1/auth/wallet/link` | Bearer JWT | Prove ownership of a signed address and attach it to the caller's account |
| POST | `/api/v1/auth/wallet/login` | none | Exchange a signed challenge for tokens — no password, requires a wallet already verified via `/link` |
| POST / GET /mine / GET /{id} / PATCH /{id} / DELETE /{id} | `/api/v1/products...` | seller (owner) / none for reads | Catalog CRUD + public browse/search |
| POST | `/api/v1/orders` | buyer | Place an order — stock check/decrement, creates Order + Transaction, runs fraud scoring, attributes recommendation purchases |
| GET / GET /{id} / GET /{id}/transactions / PATCH /{id}/status | `/api/v1/orders...` | scoped | Tracking + seller-driven status state machine |
| GET | `/api/v1/fraud/alerts` | scoped | Fraud logs (buyer/seller → own, admin → all); `only_flagged`, pagination |
| PATCH | `/api/v1/fraud/logs/{id}/review` | admin | Record `admin_decision` on a fraud log |
| GET | `/api/v1/trust/sellers/{id}` | none | Current trust score (lazily computed if none exists yet) |
| GET | `/api/v1/trust/sellers/{id}/history` | none | Time series of past scores |
| POST | `/api/v1/trust/sellers/{id}/recompute` | seller (self) or admin | Manual recompute trigger |
| POST | `/api/v1/reviews` | buyer | Review a delivered order (one per order); recomputes seller trust |
| GET | `/api/v1/reviews/sellers/{id}` | none | A seller's reviews |
| GET | `/api/v1/recommendations` | buyer | Ranked, hybrid/cold-start recommendations; logs impressions |
| POST | `/api/v1/recommendations/{id}/click` | buyer (owner) | Mark a recommendation clicked |
| GET | `/api/v1/recommendations/ctr` | admin | CTR/conversion report, optional `algorithm` filter |
| POST | `/api/v1/disputes` | buyer/seller (party) | Raise a dispute on a confirmed/shipped/delivered order |
| POST | `/api/v1/disputes/{id}/evidence` | buyer/seller (party) | Submit evidence; auto-resolves once both sides have |
| PATCH | `/api/v1/disputes/{id}/arbitrate` | admin | Override with a manual seller/buyer split |
| GET / GET /{id} | `/api/v1/disputes...` | scoped | Listing + detail |
| POST / GET / DELETE /{product_id} | `/api/v1/wishlist...` | buyer | Save/list/remove wishlist items |
| GET | `/api/v1/admin/users` | admin | List/filter/search users |
| PATCH | `/api/v1/admin/users/{id}/status` | admin | Activate/deactivate (can't deactivate self) |
| GET | `/api/v1/admin/analytics` | admin | Users/products/orders/revenue/fraud-rate/avg-trust/disputes in one report |
| GET | `/api/v1/admin/blockchain-hashes` | admin | On-chain audit trail — real rows once `BLOCKCHAIN_ENABLED=true` |
| GET | `/api/v1/trust/sellers/{id}/onchain` | none | Live read from `TrustScore.sol` (`null` score if not registered/chain disabled) |
| GET | `/health` | none | Liveness check |

Full interactive docs (request/response schemas, try-it-out) are served at
`/docs` once the app is running.

## What's next

The backend covers every module in the original plan plus two hardening
passes that followed: auth (incl. refresh-token rotation *and*
single-use revocation via a Redis blocklist), catalog (Redis-cached hot
reads), orders (incl. the self-service return/refund flow), fraud
detection, trust scoring (also Redis-cached), recommendations (incl.
city-level buyer-seller proximity), reviews, disputes, wishlist, the
admin module, the blockchain bridge (buyer and seller registration,
symmetric), rate limiting, structured logging, and global exception
handling are all live and tested (137 tests total: 129 pass with zero
external services, the other 8 need a live local chain — see "Blockchain
bridge" in `documentation/05_testing_and_results.md`). What's left,
honestly:

- **Sepolia deployment** — needs a funded testnet wallet + RPC endpoint
  this project doesn't have provisioned; the contracts and deploy script
  are ready and proven against a real local chain, just not a public one.
- **Granular fraud sub-detectors** (duplicate-account detection, bot
  activity, location anomalies, explicit fake-buyer flagging) aren't
  separate from the general fraud classifier — `is_new_seller` and
  `velocity_1h` are the closest proxies today. Location anomaly
  specifically needs an address/geo column that doesn't exist in the
  schema; the others are additional models/rules layered on top of the
  existing classifier, not yet built.

What's outside the backend entirely: the React frontend, deployment
(Docker/CI/Render — see `deployment/README.md`), and the documentation
set (diagrams, ER/DFD, guides — see `documentation/`) are all separately
complete; see their own READMEs.
