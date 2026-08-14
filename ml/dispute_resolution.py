"""Automated dispute resolution engine — the off-chain decision logic that
contracts/EscrowDispute.sol's autoResolve() applies on-chain using each
party's TrustScore. Exposed here so the rules can be tuned/tested in Python
before being ported to Solidity.
"""

REASON_ADJUSTMENTS = {
    "item_not_received": {"buyer": 0.20},
    "item_not_as_described": {"buyer": 0.10},
    "buyer_unresponsive": {"seller": 0.20},
    "damaged_in_transit": {"buyer": 0.05},
}


def resolve_dispute(
    seller_trust_score,
    buyer_trust_score,
    evidence_seller,
    evidence_buyer,
    delivery_confirmed,
    dispute_reason,
):
    """All *_trust_score inputs are 0-100; evidence_* are 0-1 confidence scores
    (e.g. from uploaded proof-of-delivery, chat logs, photos)."""
    seller_case = 0.4 * (seller_trust_score / 100) + 0.6 * evidence_seller
    buyer_case = 0.4 * (buyer_trust_score / 100) + 0.6 * evidence_buyer

    if delivery_confirmed:
        seller_case += 0.15
    elif dispute_reason == "item_not_received":
        buyer_case += REASON_ADJUSTMENTS["item_not_received"]["buyer"]

    adjustment = REASON_ADJUSTMENTS.get(dispute_reason, {})
    seller_case += adjustment.get("seller", 0.0)
    buyer_case += adjustment.get("buyer", 0.0)

    total = seller_case + buyer_case
    seller_share = seller_case / total if total > 0 else 0.5
    buyer_share = 1 - seller_share

    if seller_share >= 0.65:
        outcome = "Release funds to seller"
    elif buyer_share >= 0.65:
        outcome = "Refund buyer"
    else:
        outcome = "Split settlement (partial refund)"

    return {
        "outcome": outcome,
        "seller_share": round(seller_share, 3),
        "buyer_share": round(buyer_share, 3),
    }
