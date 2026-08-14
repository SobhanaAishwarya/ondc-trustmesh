# Algorithms and Pseudocode

Every algorithm below is transcribed from the actual implementation, not
idealized — variable names, constants, and control flow match the real
code (`backend/app/services/`, `backend/app/ml/`). Where a formula's
weights or thresholds were tuned (trust score, fraud threshold), the
reasoning is stated, not just the number.

## 1. Trust score computation

`backend/app/services/trust_service.py`. Combines nine real, DB-derived
metrics into a single 0–100 score. Weights are chosen so the range is
*actually reachable*: a seller with perfect rates, a 5-star rating, and
full tenure scores exactly 100; a seller with every rate at its worst
clamps to 0 with room to spare (see `backend/README.md` — an earlier
version of this formula could only reach ~82 in practice, which is a
documented, fixed mistake, not silently corrected).

```
function compute_trust_score(m: TrustMetrics) -> float:
    seller_age_bonus = min(m.seller_age_days / 365, 1.0) * 10
    dispute_penalty  = min(m.dispute_count, 10) * 2

    score = 50                                            # base
          + 30 * (m.order_completion_rate - 0.5)          # max +15
          + 20 * (m.transaction_success_rate - 0.5)       # max +10
          + 15 * ((m.avg_customer_rating - 3) / 2)        # max +15
          + seller_age_bonus                              # max +10
          - 15 * m.complaint_ratio
          - 10 * m.refund_ratio
          - 10 * m.late_delivery_ratio
          - 25 * m.fraud_probability
          - dispute_penalty                                # max -20

    return clamp(round(score, 2), 0, 100)
```

**Cold start**: a seller with zero orders/transactions gets
`order_completion_rate = transaction_success_rate = 1.0` (optimistic
defaults, not zero) — a brand-new seller who simply hasn't transacted yet
shouldn't score as if every possible order had failed. See
`_safe_ratio()`'s docstring for the explicit reasoning.

**Late delivery** is measured against an assumed 5-day SLA
(`LATE_DELIVERY_SLA_DAYS`) — there's no per-order deadline column in the
schema, so this is a stated modeling assumption applied to real
timestamps (`delivered_at - created_at`), not fabricated data.

## 2. Fraud detection

`backend/app/ml/model.py` (training) and
`backend/app/services/fraud_service.py` (live scoring). A `RandomForestClassifier`
(300 trees, max depth 10, `class_weight="balanced"`) over 7 numeric + 2
categorical features — deliberately *not* the Streamlit prototype's
feature set, which includes `delivery_time_hours`/`distance_km`: those
aren't knowable at the moment `POST /orders` has to decide whether to
flag a transaction, before delivery has happened.

```
features = {
    transaction_amount, buyer_account_age_days, seller_trust_score,
    num_previous_disputes,   # count(Dispute) on orders for this seller
    velocity_1h,             # count(Transaction) by this buyer in the last hour
    seller_rating,           # avg(Review.rating) for this seller, default 3.0
    is_new_seller,           # 1 if seller_age_days < 30 else 0
    payment_method, category,
}

probability = model.predict_proba(features)               # trained pipeline: StandardScaler
                                                            # + OneHotEncoder -> RandomForest
is_flagged  = probability >= FRAUD_FLAG_THRESHOLD          # default 0.5

write Transaction.fraud_probability, Transaction.is_fraud_flagged
write FraudLog(model_name, model_version, fraud_probability, is_flagged, risk_factors)
if is_flagged:
    record_trust_event(seller, "fraud_flagged")            # best-effort, on-chain
```

**Explainability** (`_top_risk_factors`) — a lightweight, dependency-free
ranking, not a Shapley-value decomposition:

```
for each numeric feature f:
    z = abs((value[f] - training_mean[f]) / training_std[f])
    contribution[f] = z * global_importance[f]
for each categorical feature f:
    contribution[f] = global_importance[f] * 0.5           # no z-score concept for a category

risk_factors = top 3 features by contribution, with their raw value
```

**Measured result** (`scripts/train_fraud_model.py`, n=6000 synthetic
transactions, 75/25 split): **90.3% accuracy, 94.8% ROC-AUC**, 8% base
fraud rate. Precision 44%, recall 78% — `class_weight="balanced"`
deliberately trades precision for recall, the right tradeoff when flagged
transactions go to a human review queue (`/fraud/alerts`,
admin-reviewable) rather than an automatic block.

## 3. Recommendation engine

`backend/app/services/recommendation_service.py`. Hybrid: content-based
(TF-IDF + cosine similarity) + item-based collaborative filtering
(co-purchase counts) + seller trust + popularity + proximity/vendor
matchmaking, with a distinct cold-start path.

```
function get_recommendations(buyer, top_k):
    products = all active products
    if products is empty: return []

    query_categories = buyer.preferred_categories + categories_of(buyer's past orders)

    content       = tfidf_cosine_similarity(query_categories, each product's category+tags+name)
    collaborative = co_purchase_scores(buyer)              # {} if buyer has no order history
    popularity    = order_count(product) / max(order_count) across all products
    trust         = seller.current_trust_score / 100
    proximity     = proximity_scores(buyer, products)      # see below

    is_cold_start = query_categories is empty AND collaborative is empty

    for each product:
        if is_cold_start:
            score = 0.5 * popularity[product] + 0.25 * trust[product.seller]
              + 0.25 * proximity[product.seller]
            algorithm = "popularity_cold_start"
        else:
            score = 0.35 * content[product] + 0.25 * collaborative[product]
              + 0.15 * trust[product.seller] + 0.10 * popularity[product]
              + 0.15 * proximity[product.seller]
            algorithm = "hybrid"

    return top_k products sorted by score, descending
```

**Proximity / vendor matchmaking** — the reference paper's clustering-style
vendor-matchmaking idea (rank sellers by location + delivery capability
alongside trust/reviews), implemented via city-level distance rather than
raw GPS (no geocoding provider is wired up; buyers/sellers pick a city
from a fixed list, `app/core/geo.py`):

```
function proximity_scores(buyer, products):
    for each distinct seller among products:
        distance_km = haversine(buyer.city, seller.city)   # None if either city is unset/unknown
        if distance_km is None:
            score = 0.5                                     # neutral, not a penalty
        else:
            score = 1 / (1 + distance_km / seller.delivery_radius_km)
    return {seller_id: score}
```

A same-city seller scores 1.0; a seller exactly at their own delivery
radius scores 0.5; the decay is smooth rather than a hard cutoff, so a
seller further out can still be shown, just less competitively. Each
recommendation response also carries `distance_km` and
`estimated_delivery_days` (a coarse distance-bucketed ETA) for display,
computed at read time rather than persisted.

**Collaborative filtering** ("buyers who bought X also bought Y"):

```
function co_purchase_scores(buyer):
    purchased = {product_id : buyer has ordered this product}
    if purchased is empty: return {}

    co_buyers = {other buyers who ordered any product in `purchased`} - {buyer}
    if co_buyers is empty: return {}

    candidates = products co_buyers ordered, excluding `purchased`, grouped with counts
    return {product_id: count / max(count)}                # normalized to [0, 1]
```

Chosen over matrix factorization or learned embeddings deliberately — at
this data volume, a learned model would be undertrained noise; co-purchase
counts degrade gracefully to an empty dict (falling back to
content+trust+popularity) rather than erroring on a buyer with no history.

**CTR** is measured from real logged impressions (one `Recommendation`
row per item shown, `was_clicked`/`was_purchased` updated on click and on
a subsequent matching order) via
`GET /recommendations/ctr` — not a simulated backtest.

## 4. Dispute resolution

`backend/app/services/dispute_service.py`. Fires automatically the moment
both parties have submitted evidence — mirrors the exact rules
`contracts/EscrowDispute.sol`'s `autoResolve()` applies on-chain.

```
function resolve(seller_trust, buyer_trust, evidence_seller, evidence_buyer,
                  delivery_confirmed, reason) -> (outcome, seller_share_bps):

    seller_case = 0.4 * (seller_trust / 100) + 0.6 * evidence_seller
    buyer_case  = 0.4 * (buyer_trust  / 100) + 0.6 * evidence_buyer

    if delivery_confirmed:
        seller_case += 0.15
    elif reason == "item_not_received":
        buyer_case += 0.20

    # reason-specific adjustment (mutually exclusive with the branch above
    # for item_not_received, applies independently for the other three):
    #   item_not_as_described -> buyer_case += 0.10
    #   buyer_unresponsive     -> seller_case += 0.20
    #   damaged_in_transit     -> buyer_case += 0.05

    total = seller_case + buyer_case
    seller_share = clamp(seller_case / total, 0, 1)  if total > 0 else 0.5

    if seller_share >= 0.65:       outcome = "Release funds to seller"
    elif 1 - seller_share >= 0.65: outcome = "Refund buyer"
    else:                          outcome = "Split settlement (partial refund)"

    return outcome, round(seller_share * 10000)      # basis points, 0-10000
```

**Buyer trust is ephemeral, not persisted** — `schema.sql`'s
`trust_scores` table only has a `seller_id` column, so there's no
buyer-side trust storage. Rather than add a table for one formula input,
`ephemeral_buyer_trust()` computes a lighter heuristic on the fly:

```
function ephemeral_buyer_trust(buyer) -> float:
    score = 70                                  # base — buyers start more trusted
                                                 # than sellers (less scrutiny by default)
    if buyer.is_flagged_fraud: score -= 30
    score += min(buyer.account_age_days / 365, 1.0) * 10
    return clamp(score, 0, 100)
```

After resolution: `recompute_trust_score(seller)` (dispute_count and
complaint_ratio both shifted) and `record_trust_event(seller,
"dispute_resolved_seller" | "dispute_resolved_buyer")` — the same
`SELLER_WIN_THRESHOLD_BPS = 6500` cutoff `EscrowDispute.sol` uses on-chain
decides which event fires, so the off-chain and on-chain records agree on
who "won" even though they're computed independently.
