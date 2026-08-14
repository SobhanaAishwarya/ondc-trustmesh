"""Trust score computation — the multi-factor formula database/schema.sql's
`trust_scores` table documents (transaction success, delivery success,
ratings, complaints, disputes, fraud probability, refund ratio, late
delivery, order completion, seller age), distinct from the simpler
on-chain event-delta model in contracts/TrustScore.sol.

One assumption worth being explicit about: there's no SLA/expected-delivery
column anywhere in the schema, so "late delivery" is computed against an
assumed fixed delivery window (LATE_DELIVERY_SLA_DAYS) rather than a
per-order deadline. That's a documented modeling assumption, not a made-up
number pretending to be real data — every input to the formula besides the
SLA constant comes from real rows.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import cache_delete
from app.models.dispute import Dispute
from app.models.order import Order, OrderStatus
from app.models.review import Review
from app.models.seller import Seller
from app.models.transaction import Transaction, TransactionStatus
from app.models.trust_score import TrustScore

BASE_SCORE = 50.0
DEFAULT_RATING = 3.0
LATE_DELIVERY_SLA_DAYS = 5
SELLER_AGE_BONUS_CAP_DAYS = 365
MAX_DISPUTE_PENALTY_COUNT = 10


@dataclass
class TrustMetrics:
    transaction_success_rate: float
    delivery_success_rate: float
    avg_customer_rating: float
    complaint_ratio: float
    dispute_count: int
    fraud_probability: float
    refund_ratio: float
    late_delivery_ratio: float
    order_completion_rate: float
    seller_age_days: int


def gather_trust_metrics(db: Session, seller_id) -> TrustMetrics:
    total_orders = db.scalar(select(func.count()).select_from(Order).where(Order.seller_id == seller_id)) or 0
    delivered_orders = db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.seller_id == seller_id, Order.status == OrderStatus.delivered)
    ) or 0

    late_orders = db.scalar(
        select(func.count())
        .select_from(Order)
        .where(
            Order.seller_id == seller_id,
            Order.status == OrderStatus.delivered,
            Order.delivered_at.is_not(None),
            Order.delivered_at - Order.created_at > timedelta(days=LATE_DELIVERY_SLA_DAYS),
        )
    ) or 0

    total_transactions = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.seller_id == seller_id)
    ) or 0
    successful_transactions = db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.seller_id == seller_id, Transaction.status == TransactionStatus.success)
    ) or 0
    refunded_transactions = db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.seller_id == seller_id, Transaction.status == TransactionStatus.refunded)
    ) or 0
    avg_fraud_probability = db.scalar(
        select(func.avg(Transaction.fraud_probability)).where(Transaction.seller_id == seller_id)
    )

    dispute_count = db.scalar(
        select(func.count())
        .select_from(Dispute)
        .join(Order, Dispute.order_id == Order.id)
        .where(Order.seller_id == seller_id)
    ) or 0

    avg_rating = db.scalar(select(func.avg(Review.rating)).where(Review.seller_id == seller_id))

    seller = db.get(Seller, seller_id)
    seller_age_days = seller.seller_age_days if seller else 0

    return TrustMetrics(
        transaction_success_rate=_safe_ratio(successful_transactions, total_transactions, default=1.0),
        delivery_success_rate=_safe_ratio(delivered_orders, total_orders, default=1.0),
        avg_customer_rating=float(avg_rating) if avg_rating is not None else DEFAULT_RATING,
        complaint_ratio=_safe_ratio(dispute_count, total_orders, default=0.0),
        dispute_count=dispute_count,
        fraud_probability=float(avg_fraud_probability) if avg_fraud_probability is not None else 0.0,
        refund_ratio=_safe_ratio(refunded_transactions, total_transactions, default=0.0),
        late_delivery_ratio=_safe_ratio(late_orders, delivered_orders, default=0.0),
        order_completion_rate=_safe_ratio(delivered_orders, total_orders, default=1.0),
        seller_age_days=seller_age_days,
    )


def _safe_ratio(numerator: int, denominator: int, default: float) -> float:
    """No orders/transactions yet is a cold-start case, not a 0% success
    rate — defaulting to a neutral/optimistic value avoids punishing a
    brand-new seller who simply hasn't transacted yet."""
    return numerator / denominator if denominator > 0 else default


def compute_trust_score(m: TrustMetrics) -> float:
    """Weights are chosen so the two extremes are reachable exactly:
    a seller with perfect rates/rating/tenure and zero negatives scores
    100 (50 base + 15+10+15+10 positive terms); a seller with every rate
    at its worst and heavy negatives clamps to 0 with room to spare. The
    clamp still guards the general case since real inputs won't usually
    sit at either extreme.
    """
    seller_age_bonus = min(m.seller_age_days / SELLER_AGE_BONUS_CAP_DAYS, 1.0) * 10
    dispute_penalty = min(m.dispute_count, MAX_DISPUTE_PENALTY_COUNT) * 2

    score = (
        BASE_SCORE
        + 30 * (m.order_completion_rate - 0.5)
        + 20 * (m.transaction_success_rate - 0.5)
        + 15 * ((m.avg_customer_rating - 3) / 2)
        + seller_age_bonus
        - 15 * m.complaint_ratio
        - 10 * m.refund_ratio
        - 10 * m.late_delivery_ratio
        - 25 * m.fraud_probability
        - dispute_penalty
    )
    return round(max(0.0, min(100.0, score)), 2)


def trust_score_cache_key(seller_id) -> str:
    return f"trust_score:current:{seller_id}"


def recompute_trust_score(db: Session, seller: Seller) -> TrustScore:
    """Computes, persists a new time-series row, and syncs the fast-read
    `Seller.current_trust_score` column. Caller owns the commit.

    Also invalidates the cached current-score read (GET
    /trust/sellers/{id}) right here, at the single choke point every
    trust-affecting event (delivery, review, dispute, admin recompute)
    already funnels through — callers don't each need to remember to
    invalidate it themselves.
    """
    cache_delete(trust_score_cache_key(seller.id))
    metrics = gather_trust_metrics(db, seller.id)
    score = compute_trust_score(metrics)

    trust_score = TrustScore(
        seller_id=seller.id,
        score=Decimal(str(score)),
        transaction_success_rate=Decimal(str(round(metrics.transaction_success_rate, 4))),
        delivery_success_rate=Decimal(str(round(metrics.delivery_success_rate, 4))),
        avg_customer_rating=Decimal(str(round(metrics.avg_customer_rating, 2))),
        complaint_ratio=Decimal(str(round(metrics.complaint_ratio, 4))),
        dispute_count=metrics.dispute_count,
        fraud_probability=Decimal(str(round(metrics.fraud_probability, 4))),
        refund_ratio=Decimal(str(round(metrics.refund_ratio, 4))),
        late_delivery_ratio=Decimal(str(round(metrics.late_delivery_ratio, 4))),
        order_completion_rate=Decimal(str(round(metrics.order_completion_rate, 4))),
    )
    db.add(trust_score)

    seller.current_trust_score = Decimal(str(score))
    return trust_score
