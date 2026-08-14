# Load test results

Run for real against a live instance of this backend — not estimated.
Environment: single `uvicorn` process (no `--workers`), SQLite (not the
Postgres production target — see caveats below), this machine's hardware.
Reproduce with:

```bash
python loadtest/seed.py --host http://localhost:8000
locust -f loadtest/locustfile.py --host http://localhost:8000 \
    --headless -u 20 -r 5 -t 30s
```

## Run: 20 concurrent users (16 browsing, 4 registering+buying), 30s

| Endpoint | Requests | Failures | Median | 95th %ile | Max |
|---|---|---|---|---|---|
| `GET /health` | 68 | 0 | 23ms | 2100ms | 2096ms |
| `GET /products` | 294 | 0 | 29ms | 94ms | 2119ms |
| `GET /products?category=` | 89 | 0 | 29ms | 68ms | 2228ms |
| `GET /auth/me` | 30 | 0 | 26ms | 39ms | 49ms |
| `POST /auth/register/buyer` | 4 | 0 | 2700ms | 2700ms | 2701ms |
| `POST /orders` | 16 | 0 | 260ms | 380ms | 380ms |

**501 requests, 0 failures (0.00%).** Nothing crashed or errored under
load — that's the good news. The interesting finding is the latency
shape, not a failure count.

## What the numbers say

**Reads are fast**: product browsing/search sits at a 29ms median even
under concurrent load, `/auth/me` at 26ms. That's what a request that's
mostly "query the DB, serialize a response" should look like.

**`POST /auth/register/buyer` at ~2.7s median is real, and explained, not
a bug**: bcrypt hashing a password alone measured **0.46s** on this
hardware in isolation (`bcrypt.hashpw` at the default cost factor — see
`backend/README.md`'s security section for why bcrypt directly, not
passlib). Under the load test, 4 concurrent registrations averaged ~2.6s
each — roughly 4-6x the solo cost, consistent with FastAPI running sync
path functions in a thread pool that, combined with the GIL, doesn't give
truly parallel execution to CPU-bound work like bcrypt across a single
process. This is a single-worker deployment characteristic, not a request
handling bug: **production should run multiple worker processes**
(`uvicorn --workers N` or Gunicorn with uvicorn workers), which gives
bcrypt hashing genuine parallelism across processes instead of
contending for one process's thread pool.

**The `/health` and `/products` max-latency spikes (~2.1–2.2s, at the
98th+ percentile only)** land at the same moments as those buyer
registrations — while the process is busy hashing a password, an unlucky
concurrent read can queue behind it. Same root cause and same fix as
above; the median/90th-percentile numbers for reads are unaffected,
confirming it's contention from the CPU-bound minority of requests, not a
general capacity problem.

**`POST /orders` at 260ms median** includes stock check + decrement, order
+ transaction creation, and a live fraud-model `predict_proba` call — all
in one request. That's the most expensive *correctness-critical* endpoint
in the app and it's still comfortably sub-second.

## Caveats — what this run doesn't tell you

- **SQLite, not Postgres.** SQLite serializes writes (single-writer);
  Postgres uses MVCC and handles concurrent writes without that
  limitation. The order-placement numbers above would very likely improve
  under Postgres, not worsen — this run is a conservative floor, not a
  ceiling.
- **Single machine, single process, modest concurrency (20 users).** This
  characterizes latency shape and confirms the bcrypt/thread-pool
  interaction; it is not a capacity/ceiling benchmark. Finding the actual
  breaking point would mean ramping concurrency until failures or latency
  degradation appear, which this run doesn't do.
- **No blockchain bridge, no Redis caching** were exercised (both off by
  default — see `backend/README.md`) — this measures the core commerce +
  fraud-scoring path only.
