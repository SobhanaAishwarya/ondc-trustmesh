# Database Schema

The authoritative source is `database/schema.sql`, mirrored exactly by
`backend/app/models/` (SQLAlchemy ORM) and the Alembic migrations in
`backend/alembic/versions/`. This document explains *why* each table
looks the way it does; if it ever disagrees with `schema.sql` on a
column, `schema.sql` is right and this file is stale.

13 tables: the 12 originally specified, plus `wishlists`.

## users

Identity + auth for all three roles in one table (not three separate
tables), with `buyers`/`sellers` as 1:1 extension tables holding
role-specific fields. A `role` enum column, not a wide nullable-everything
table, and not three disjoint login tables that would need three copies of
every auth code path.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Client-generated (`uuid.uuid4`), server-default `gen_random_uuid()` as a fallback for rows inserted outside the ORM |
| `email` | varchar(255) UNIQUE | Indexed; login identifier |
| `password_hash` | varchar(255) | bcrypt, never returned by any API response — see `test_password_hash_is_never_returned_from_the_api` |
| `role` | enum(buyer, seller, admin) | Indexed; drives which extension table (if any) exists |
| `is_active` | bool | Admin-togglable; `false` invalidates every existing JWT immediately (checked on every request, not just at issue time) |

## buyers / sellers

1:1 extensions of `users` (`user_id` UNIQUE FK), not one wide table,
because buyer-specific and seller-specific fields don't overlap and
forcing them into one table means every row has a pile of nulls for the
role it isn't.

`sellers.current_trust_score` is a **denormalized fast-read column**,
kept in sync by `trust_service.recompute_trust_score()` every time the
full computation runs — reading it doesn't require joining/aggregating
`trust_scores`. `trust_scores` (below) is the time series; this is "what's
the answer right now."

`buyers.city` / `sellers.city` (added by `0004_add_location_fields.py`)
hold one of `app.core.geo.CITY_NAMES` or `NULL` — a fixed list of major
Indian cities rather than free text or raw lat/lng, since no geocoding
provider is wired up. `sellers.delivery_radius_km` (default 50) is how
far that seller ships; both feed `recommendation_service`'s proximity
signal (city-level haversine distance vs. delivery radius) — the
paper's location + delivery-capability vendor-matchmaking idea, without
needing precise GPS.

`wallet_verified` (added by `0005_wallet_verified.py`) tracks whether
`wallet_address` was proven via a signed challenge (`POST /auth/wallet/
link`) rather than just typed in — the two columns can never disagree
because `wallet_address` is only ever written alongside setting this to
`true` in that same code path. `PATCH /auth/me` can no longer set
`wallet_address` at all.

## products

Seller's catalog. `is_active` (not row deletion) is how `DELETE
/products/{id}` "removes" a product — see `backend/README.md`'s
design-decisions section for why: `orders.product_id` is a foreign key,
so hard-deleting a product with order history would either violate the FK
constraint or silently orphan historical order data.

## orders

One row per (buyer, seller, product, quantity) — **no `order_items`
table**. This is a deliberate, existing constraint of the schema (not a
simplification introduced later): a buyer places one order per product,
not a multi-item cart checkout. `status` is an enum enforced as a state
machine server-side (see the state diagram in
[02_architecture_and_diagrams.md](02_architecture_and_diagrams.md)), not
left to the client. `onchain_order_id`/`escrow_tx_hash` are reserved for
when order creation itself moves on-chain (currently only trust *events*
do — see the blockchain bridge section of `backend/README.md`).

## transactions

A **payment attempt** tied to an order — deliberately separate from
`orders` because one order can have multiple transaction attempts
(retries after a failed payment) in a real system, even though this
project's simulated payment path (no real gateway integrated — see
`orders.py`'s docstring) only ever creates one. `is_fraud_flagged` and
`fraud_probability` are written by `fraud_service.score_transaction()`
synchronously at creation time.

## fraud_logs

**Every scored transaction, not just flagged ones** — the audit trail a
fraud model needs to be evaluated and eventually retrained against, and
what lets `GET /fraud/alerts?only_flagged=false` show a seller/buyer their
full scoring history, not just the alarming subset. `risk_factors` (JSONB)
stores the top-3 explainability output from
`fraud_service._top_risk_factors()`. `reviewed_by_admin_id` +
`admin_decision` close the loop: an admin's `confirmed_fraud`/
`false_positive` call is itself data, not just a UI action.

## trust_scores

**A time series (one row per computation), not a single mutable column**
on `sellers` — `sellers.current_trust_score` (above) is the fast-read
mirror of the latest row here. Storing history is what makes
`GET /trust/sellers/{id}/history` and the seller trust-dashboard chart
possible, and lets an audit answer "what exactly changed the score on
this date," not just "what is it now." Every one of the brief's named
trust factors is its own column (`transaction_success_rate`,
`delivery_success_rate`, `avg_customer_rating`, `complaint_ratio`,
`dispute_count`, `fraud_probability`, `refund_ratio`,
`late_delivery_ratio`, `order_completion_rate`) — the formula combining
them into `score` is `trust_service.compute_trust_score()`, documented in
[04_algorithms_and_pseudocode.md](04_algorithms_and_pseudocode.md).

## disputes

`evidence_buyer_score`/`evidence_seller_score` are separate columns
(not one shared "evidence" field) because each party submits their own
independently — `dispute_service.resolve()` only fires once both are
present. `resolved_by` (`'rule_auto'` vs `'arbitrator'` vs `'auto_return'`)
records *how* a dispute was settled, not just what the outcome was —
meaningfully different provenance for an audit. `'rule_auto'` is a fixed
weighted formula (`dispute_service.resolve()`), not a learned model — named
`rule_auto` rather than `ai_auto` so the column doesn't overstate what
actually decided the split.

## recommendations

One row per **impression shown**, not per click — `was_clicked`,
`was_purchased`, `rank`, and `algorithm` on the same row are what make
honest CTR measurement possible
(`recommendation_service.compute_ctr()`): impressions and clicks are
counted from the same table, not reconciled across two.

## reviews

`order_id` is **UNIQUE** — one review per order, enforced at the database
level, not just checked in application code (`reviews.py` also checks,
but the DB constraint is the real guarantee under concurrent requests).

## blockchain_hashes

**Append-only audit trail**, referencing other rows by `(entity_type,
entity_id)` rather than a typed foreign key, because it's a single log
for events on multiple different entity types (currently `seller`
registration/trust events; see `app/services/blockchain_service.py`) —
a typed FK would mean a separate hash table per entity type, duplicating
the same five columns (`tx_hash`, `block_number`, `network`, `event_type`,
`confirmed_at`) each time.

## wishlists

**Not one of the original 12 tables** — added later for the buyer
wishlist feature, via one additive migration
(`backend/alembic/versions/0002_add_wishlist.py`) that touches nothing
else. `(buyer_id, product_id)` is UNIQUE, enforced at the database level
(mirrors the duplicate-add rejection in `wishlist.py`).

## Design principles that apply across all 13 tables

- **UUID primary keys everywhere**, not auto-increment integers — safe to
  expose in URLs, and don't leak row counts (`schema.sql`'s own stated
  reasoning, carried through unchanged into the ORM models).
- **`TIMESTAMPTZ` for every timestamp**, not naive datetimes — avoids an
  entire category of "whose timezone is this" bugs.
- **Foreign keys with explicit `ON DELETE` behavior** (`CASCADE` where a
  child row is meaningless without its parent — e.g. a `Buyer` row without
  its `User`; no action where it should be a hard error instead).
