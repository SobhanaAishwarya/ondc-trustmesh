"""Automated dispute resolution — ported from the Streamlit prototype's
`ml/dispute_resolution.py` (same rules `contracts/EscrowDispute.sol`'s
`autoResolve()` applies on-chain), adapted to pull the real, persisted
seller trust score.

`schema.sql`'s `trust_scores` table only has a `seller_id` column — there's
no buyer-side trust storage. Rather than add a table for it, buyer trust
here is an ephemeral heuristic (fraud flag + account age) computed on the
fly and never persisted — a deliberately lighter-weight signal than the
seller's multi-factor score, not a stand-in claiming to be equivalent.
"""

from app.models.buyer import Buyer
from app.models.dispute import DisputeReason

REASON_ADJUSTMENTS = {
    DisputeReason.item_not_received: {"buyer": 0.20},
    DisputeReason.item_not_as_described: {"buyer": 0.10},
    DisputeReason.buyer_unresponsive: {"seller": 0.20},
    DisputeReason.damaged_in_transit: {"buyer": 0.05},
}

AUTO_RESOLVE_THRESHOLD = 0.65
BUYER_TRUST_BASE = 70.0
BUYER_TRUST_FRAUD_PENALTY = 30.0
BUYER_TRUST_AGE_BONUS_CAP_DAYS = 365
BUYER_TRUST_AGE_BONUS = 10.0


def ephemeral_buyer_trust(buyer: Buyer) -> float:
    score = BUYER_TRUST_BASE
    if buyer.is_flagged_fraud:
        score -= BUYER_TRUST_FRAUD_PENALTY
    score += min(buyer.account_age_days / BUYER_TRUST_AGE_BONUS_CAP_DAYS, 1.0) * BUYER_TRUST_AGE_BONUS
    return max(0.0, min(100.0, score))


def resolve(
    seller_trust_score: float,
    buyer_trust_score: float,
    evidence_seller: float,
    evidence_buyer: float,
    delivery_confirmed: bool,
    reason: DisputeReason,
) -> dict:
    seller_case = 0.4 * (seller_trust_score / 100) + 0.6 * float(evidence_seller)
    buyer_case = 0.4 * (buyer_trust_score / 100) + 0.6 * float(evidence_buyer)

    if delivery_confirmed:
        seller_case += 0.15
    elif reason == DisputeReason.item_not_received:
        buyer_case += REASON_ADJUSTMENTS[DisputeReason.item_not_received]["buyer"]

    adjustment = REASON_ADJUSTMENTS.get(reason, {})
    seller_case += adjustment.get("seller", 0.0)
    buyer_case += adjustment.get("buyer", 0.0)

    total = seller_case + buyer_case
    seller_share = seller_case / total if total > 0 else 0.5
    seller_share = max(0.0, min(1.0, seller_share))

    if seller_share >= AUTO_RESOLVE_THRESHOLD:
        outcome = "Release funds to seller"
    elif (1 - seller_share) >= AUTO_RESOLVE_THRESHOLD:
        outcome = "Refund buyer"
    else:
        outcome = "Split settlement (partial refund)"

    return {"outcome": outcome, "seller_share_bps": round(seller_share * 10000)}
