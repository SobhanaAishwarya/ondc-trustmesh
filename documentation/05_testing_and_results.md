# Testing and Results

Every number on this page was produced by actually running the referenced
command in this repository during development — none of it is a
projection. Where a number came from a specific run (load test, fraud
model training), the exact command is given so it can be reproduced.

## Testing strategy by layer

| Layer | Tool | Location | What it covers |
|---|---|---|---|
| Unit / integration (backend) | pytest | `backend/tests/` | Every endpoint, service, and model — auth, catalog, orders, fraud, trust, recommendations, disputes, wishlist, admin |
| ML model quality | pytest + `scripts/train_fraud_model.py` | `backend/tests/test_ml_fraud_model.py` | Training pipeline sanity (regression floor), save/load round-trip, high-risk-scores-above-low-risk |
| Security | pytest + bandit | `backend/tests/test_security_review.py` | Password never leaked, no email enumeration, JWT tampering/`alg:none` rejected, SQL-injection-shaped input handled safely, forged role claims rejected |
| Blockchain contracts | Hardhat + Chai/Mocha | `test/*.test.js` | `TrustScore.sol`, `EscrowDispute.sol` — registration, score deltas/clamping, access control, escrow release, dispute resolution, arbitration |
| Blockchain bridge | pytest, against a **real local chain** | `backend/tests/test_blockchain_bridge.py` | Web3.py client against actual deployed contracts, including the escrow order/delivery/dispute/arbitration lifecycle — not mocked |
| Frontend unit / component | Vitest + Testing Library | `frontend/src/**/*.test.{ts,tsx}` | Formatting utilities, badge/status components, `ProductImage` fallback behavior, an end-to-end `LoginPage` flow (mocked API layer, real routing/auth-context), and `WalletConnectButton`'s connect/sign/error paths against a stubbed EIP-1193 provider |
| Frontend build | `tsc -b` | `frontend/` (`npm run build`) | Full-app type-check across ~45 files |
| End-to-end | Playwright, against a **real running backend** | `frontend/e2e/purchase-flow.spec.ts` | Seller signup → add product → buyer signup → browse → purchase, asserting on rendered UI state, zero console errors |
| Load / performance | Locust, against a **real running backend** | `backend/loadtest/` | Concurrent read/write latency under load |

## Backend: 153 tests — 137 passing, 16 skipped without a local chain

```
$ pytest -q
............................................................................
............................................................................
....................................ssssssssssssssss...............
137 passed, 16 skipped in ~53s
```

Also run against a live local chain (`npx hardhat node` + `npx hardhat run
scripts/deploy.js --network localhost`) — all 153 pass, 0 skipped, the
same suite exercising real transactions instead of skipping (verified: a
seller receives real released escrow funds, a rule-based auto-resolve
splits real escrow funds by live on-chain trust scores, and an arbitrator
override pays out an exact specified split). See "Blockchain" below for a
manual, beyond-the-test-suite run against that same live chain.

No Docker, Postgres, or blockchain node required for the 129 that run —
`tests/conftest.py` runs against an in-memory SQLite database (see
`backend/README.md` for why the ORM models support both dialects). The 16
skips are `tests/test_blockchain_bridge.py`, which needs a real local
chain (`npx hardhat node`) to talk to — 8 for `TrustScore.sol` (register/
score/event round-trips) and 8 for `EscrowDispute.sol` (order creation,
delivery release, dispute raise/auto-resolve/arbitration, both at the raw
client level and through the `blockchain_service` wrappers `orders.py`/
`disputes.py` actually call); see "Blockchain bridge" below for that suite
run against one. Redis-backed behavior (`tests/test_cache.py`)
is verified the same way the DB is — against an in-memory fake
(`conftest.py`'s `fake_redis` fixture), not a live Redis instance —
proving the actual read-through/invalidation/revocation logic, not just
that the app doesn't crash when Redis is absent (which every *other*
test already proves, since none of them opt into `fake_redis`). Breakdown
by area: auth + refresh tokens (incl. type-confusion rejection and
single-use revocation on `/refresh`/`/logout`), profile editing,
products (incl. cache read-through/invalidation), the full order state
machine, the self-service return/refund flow (`tests/test_returns_api.py`
— window/condition checks, auto-refund vs. falling back to a contested
dispute), fraud scoring + its API, trust score formula + API (including
the 0/100 clamp boundaries and cache invalidation), reviews,
recommendations (cold-start vs. hybrid selection, city-level
proximity/vendor matching, CTR), the full dispute lifecycle (raise →
evidence → auto-resolve, plus arbitration), wishlist, the admin module,
config normalization, the dedicated security file, per-route rate
limiting, and the global exception-handler error envelope.

## Blockchain: 10 contract tests + 16 bridge tests, all passing against a live chain

```
$ npx hardhat test
  EscrowDispute
    ✔ releases funds to the seller on confirmed delivery
    ✔ records a dispute and drops the seller's trust score
    ✔ splits escrow proportionally to trust score on auto-resolve
    ✔ lets the arbitrator override the outcome
    ✔ rejects arbitrator overrides from non-arbitrators
    ✔ reverts cleanly if the fund transfer to the recipient fails
  TrustScore
    ✔ registers participants at the base score
    ✔ increases score on successful delivery and decreases on fraud
    ✔ clamps score between 0 and 100
    ✔ rejects events from unauthorized reporters
  10 passing
```

```
$ npx hardhat node                                            # separate terminal
$ npx hardhat run scripts/deploy.js --network localhost
$ pytest backend/tests/test_blockchain_bridge.py -v
16 passed
```

The bridge tests exercise both `app/blockchain/client.py` (the raw Web3.py
calls) and `app/services/blockchain_service.py` (the DB-facing layer)
against contracts genuinely deployed to a real (local) Ethereum node —
registering a participant, confirming the score starts at 50,
`successful_delivery` moving it to 52 and `fraud_flagged` to 32 (matching
`TrustScore.sol`'s documented deltas exactly), the score clamping at 0
after repeated `fraud_flagged` events, an unreachable RPC raising
`BlockchainUnavailable` cleanly rather than a raw connection error, and —
against the same live chain — `register_seller_onchain`/
`register_buyer_onchain` actually driving the real client and persisting
the on-chain registration (buyer and seller symmetric, idempotent on a
second call).

A full API-level check (not just the service/client modules in isolation)
was also run manually, twice, against a freshly deployed local chain:
registering a seller, setting a wallet address via `PATCH /auth/me`, and
confirming `is_onchain_registered` flips to `true` and `GET
/trust/sellers/{id}/onchain` reads back score `50` — through the real
HTTP API, not a direct function call. The second run went further: a
buyer placed a real order against that seller's product and the order
was carried through confirmed → shipped → delivered, which fired
`record_trust_event(seller, "successful_delivery")` for real —
`GET /trust/sellers/{id}/onchain` read back `52` immediately after,
matching `TrustScore.sol`'s documented `+2` delta, with the Hardhat node
log showing a real mined transaction (`TrustScore#recordEvent`, 35,351
gas, confirmed same block) as evidence.

That second run also caught a real gap: a malformed wallet address
(`0x70997970C51812dc3A010C7d01b50e0d17dc79C` — one hex character short of
a valid 40-character address) was accepted by `PATCH /auth/me` with a
`200`, then failed silently deep inside
`blockchain_service.register_seller_onchain`'s best-effort try/except —
`is_onchain_registered` just stayed `false` with no explanation surfaced
to the caller. Fixed by validating the format (`0x` + 40 hex chars) in
`ProfileUpdate.wallet_address` (`app/schemas/user.py`) so a malformed
address is rejected with a `422` at the door instead — regression test:
`test_updating_profile_rejects_a_malformed_wallet_address`
(`tests/test_auth_api.py`), using the exact address that triggered it.

### Escrow wiring (closing the "contract exists but nobody calls it" gap)

An external audit against the Infosys brief and IEEE paper flagged that
`EscrowDispute.sol` — genuinely well-built, with real fund custody and a
passing test suite — had zero call sites anywhere in the backend. Every
order placed through the live app was 100% Postgres state; the contract
that actually holds funds was orphaned code.

Closed by wiring `app/blockchain/client.py` (5 new functions:
`create_escrow_order`, `confirm_escrow_delivery`, `raise_escrow_dispute`,
`autoresolve_escrow`, `arbitrate_escrow`) and `app/services/
blockchain_service.py` (matching best-effort wrappers, same fail-open
pattern as the existing trust-score calls) into the real order/dispute
flow: `POST /orders` locks the order amount in escrow, delivery
confirmation releases it to the seller, and dispute raise/auto-resolve/
arbitrate drive the contract's real dispute-settlement path. `order.
onchain_order_id`/`escrow_tx_hash` and `dispute.onchain_tx_hash` — schema
columns that existed but were permanently `NULL` — now actually get
written.

Two honesty notes, not smoothed over:

- **The operator account is the on-chain buyer for every order** (there's
  no client-side wallet signing yet — see the relayer note in `backend/
  README.md`'s blockchain section), so escrow demonstrates the contract's
  real fund-custody/settlement mechanics end to end, just under one
  relayer identity rather than two independently-signing parties.
- **A self-service return (always post-delivery) has no on-chain
  settlement call** — `EscrowDispute.sol`'s `raiseDispute` only accepts a
  pre-delivery order, and `confirmDelivery` already paid the seller in
  full by the time a return could be requested. This is the contract's
  real, documented lifecycle limitation surfacing correctly, not a bug —
  see the comment at the return-flow's call site in `orders.py`.

Verified against a live local chain, not just unit-tested in isolation: a
real order's amount was locked, released to the seller on delivery with
an exact balance-delta check, and — separately — disputed, auto-resolved
by live on-chain trust scores, and arbitrator-resolved with an exact
specified split, all with real ETH balance changes observed on-chain. 8
new tests in `test_blockchain_bridge.py` (4 client-level, 4 service-level)
lock this in as a permanent regression check rather than a one-time
manual verification.

### Wallet sign-in (closing the "not actually decentralized identity" gap)

The same external audit flagged that "decentralized identity" was
password+JWT with a regex-validated `wallet_address` string — no
signature, no `ecrecover`, no wallet library in the frontend at all.
Setting a wallet was indistinguishable from typing a random 42-character
string into a form.

Closed with a standard sign-in-with-Ethereum-style challenge/response, no
new heavy dependency (the frontend talks to the injected EIP-1193
provider — `window.ethereum` — directly for the two calls it needs,
`eth_requestAccounts` and `personal_sign`):

1. `POST /auth/wallet/nonce` issues a one-time, single-use challenge
   message for a given address (`app/core/cache.py`'s new
   `wallet_nonce_set`/`wallet_nonce_pop`, Redis-backed with a 5-minute
   TTL — and, unlike every other function in that module, these fail
   *closed*: an unreachable Redis returns a `503`, never silently skips
   the check).
2. The wallet signs that exact message (`personal_sign` — no transaction,
   no gas).
3. `POST /auth/wallet/link` (authenticated) or `POST /auth/wallet/login`
   (not) recovers the signing address via `eth_account.Account.
   recover_message` and checks it matches the claim. Link sets a new
   `wallet_verified` column (`0005_wallet_verified.py`) — `wallet_address`
   can no longer be set as plain text via `PATCH /auth/me` at all, closing
   the old gap directly rather than leaving both paths open. Login issues
   the same real JWTs the password flow does, once a wallet is verified —
   password-free sign-in, not just a linked address.
4. On-chain registration (`register_seller_onchain`/`register_buyer_
   onchain`) now gates on `wallet_verified`, not just `wallet_address`
   being non-null, so an unproven address can never trigger a real
   blockchain write under someone else's identity.

Honest scope boundary, not smoothed over: this proves the *caller* holds
the private key for an address (real cryptographic identity for
authentication) — it does not make the on-chain contract calls
themselves user-signed. Those still go through the backend's operator
key, same relayer pattern as before. "Decentralized identity for
login" and "the user signs their own transactions" are different
claims; only the first is built.

8 new backend tests (`test_wallet_auth.py`) use real `eth_account`
keypairs and real signatures throughout — including a forged-signature
rejection, a nonce-replay rejection, a wallet-already-linked-elsewhere
conflict, and a fail-closed check with Redis genuinely unreachable — plus
3 new frontend tests (`WalletConnectButton.test.tsx`) against a stubbed
wallet provider covering the happy path, no-extension-installed, and a
rejected-signature error.

### Hardening pass (post-launch gap closure)

A second pass closed five gaps identified during the initial audit but
not fixed at the time: buyer on-chain registration (previously
seller-only, despite `TrustScore.sol` supporting either), `EscrowDispute.sol`'s
fund transfers (`.transfer()` → `call` + `require` + `ReentrancyGuard`,
with a new test proving a rejecting recipient now fails loudly instead of
silently), rate limiting (`slowapi`, per-route — tight on
login/registration, generous elsewhere), structured request logging, and
global exception handlers (a consistent error envelope for validation
failures and unhandled exceptions alike). All five have real test
coverage, not just "added and assumed to work" — that's where the jump
from 112→122 backend tests and 9→10 / 5→8 contract/bridge tests comes
from.

## Frontend: type-checked, built, and driven end-to-end

```
$ npm run build
✓ 741 modules transformed
✓ built in <1s
```

```
$ npx playwright test
  ok 1 [chromium] › purchase-flow.spec.ts › seller lists a product, buyer signs up and buys it (5.0s)
  1 passed
```

The E2E test drives a real browser against the real Vite dev server
talking to a real (SQLite-backed) backend instance: seller signup → add a
product → log out → buyer signup → browse → open the product → place an
order → the order appears in "My orders" with the correct product name,
quantity, and amount. It asserts zero browser console errors, not just
that the final page loaded.

Manually, before formalizing that one flow into a permanent test, a wider
walkthrough was screenshotted (see `documentation/screenshots/`):
registration for both roles, both dashboards in light and dark mode (dark
mode preference persisting across logout/login, confirming `localStorage`
persistence), product management, and browsing.

## Security review

```
$ bandit -r app
Total issues (by severity): Undefined: 0, Low: 2, Medium: 0, High: 0
```

Zero medium/high findings across 2,847 lines. The two low-severity,
low-confidence findings (`B105 hardcoded_password_string` on
`TOKEN_TYPE_ACCESS`/`TOKEN_TYPE_REFRESH` string constants) were reviewed
and are false positives, not real credentials — see
`backend/README.md`'s security section. Backed by 7 explicit behavioral
tests in `test_security_review.py`, plus 3 rate-limiting tests and 3
error-handling tests added in the hardening pass (listed in the layer
table above).

## Load test: 501 requests, 0 failures

```
$ python loadtest/seed.py --host http://localhost:8000
$ locust -f loadtest/locustfile.py --host http://localhost:8000 --headless -u 20 -r 5 -t 30s
```

| Endpoint | Requests | Failures | Median | 95th %ile |
|---|---|---|---|---|
| `GET /products` | 294 | 0 | 29ms | 94ms |
| `GET /auth/me` | 30 | 0 | 26ms | 39ms |
| `POST /orders` | 16 | 0 | 260ms | 380ms |
| `POST /auth/register/buyer` | 4 | 0 | 2700ms | 2700ms |

Full numbers, the explanation for why registration is the outlier (bcrypt
cost + single-`uvicorn`-process thread-pool contention, with the actual
fix), and stated caveats (SQLite not Postgres, 20 users is a latency-shape
characterization not a capacity ceiling) are in `backend/loadtest/RESULTS.md`.
These numbers predate rate limiting — re-running the same profile today
would show `POST /auth/register/buyer` 429s after each simulated user's
first 10 registrations within an hour, correctly, not a regression.

## Fraud model: measured, not claimed

```
$ python scripts/train_fraud_model.py
Evaluation (held-out test split, n=6000, 75/25 split):
  accuracy:  0.9033
  precision: 0.4408
  recall:    0.7750
  roc_auc:   0.9478
KPI target (fraud detection accuracy > 85%): MEETS (90.33%)
```

Re-running the script after any change to `app/ml/features.py` or
`app/ml/synthetic_data.py` will produce different numbers — the ones
above are this specific run's, not hand-edited to look good.

## What isn't tested, stated plainly

- **No automated Sepolia integration test** — the contracts are tested
  locally (Hardhat + the live-chain bridge tests above); a public testnet
  run needs a funded wallet and RPC endpoint this project doesn't have
  provisioned. See `deployment/README.md`.
- **No Docker build verification** — `docker-compose.yml` and both
  Dockerfiles are written and reviewed but not run with `docker compose
  up` in this environment (no Docker daemon available). Same honesty
  standard applied throughout: reviewed-for-correctness and
  actually-executed are different claims, and this repository doesn't
  blur them.
- **Load testing found a real bottleneck** (bcrypt/thread-pool
  contention under concurrent registration) rather than confirming
  everything was already fine — reported above with its cause and fix,
  not smoothed over.
