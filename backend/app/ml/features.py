"""Fraud-model feature schema, shared by training (synthetic_data.py) and
live scoring (services/fraud_service.py) so both produce exactly the same
columns — the classic train/serve-skew bug is a schema mismatch between the
two, so there is deliberately one definition of "what a feature is" here.

This is NOT the same feature set as the Streamlit prototype's
`ml/fraud_model.py`. That model scores completed transactions offline and
can use `delivery_time_hours`/`distance_km`. This one scores a transaction
the instant it's created, before delivery happens and with no location data
collected anywhere in the schema — using those fields here would mean
feeding the model information that doesn't exist yet at decision time.
`distance_km`/location-anomaly detection is tracked as a follow-up that
needs an address/geo column added to buyers/sellers first, not faked here.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dispute import Dispute
from app.models.order import Order
from app.models.review import Review
from app.models.transaction import Transaction

NUMERIC_FEATURES = [
    "transaction_amount",
    "buyer_account_age_days",
    "seller_trust_score",
    "num_previous_disputes",
    "velocity_1h",
    "seller_rating",
    "is_new_seller",
]
CATEGORICAL_FEATURES = ["payment_method", "category"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

NEW_SELLER_AGE_DAYS_THRESHOLD = 30
DEFAULT_SELLER_RATING = 3.0


@dataclass
class TransactionContext:
    """Everything needed to compute a live feature vector for one
    in-flight transaction — assembled by the caller (fraud_service) from
    already-loaded ORM rows so this module stays DB-session-aware only
    where it must query historical aggregates."""

    amount: Decimal
    payment_method: str
    category: str
    buyer_id: object  # uuid.UUID — typed loosely to avoid a circular import
    seller_id: object
    buyer_account_age_days: int
    seller_trust_score: Decimal
    seller_age_days: int


def compute_live_features(db: Session, ctx: TransactionContext) -> dict:
    return {
        "transaction_amount": float(ctx.amount),
        "buyer_account_age_days": float(ctx.buyer_account_age_days),
        "seller_trust_score": float(ctx.seller_trust_score),
        "num_previous_disputes": float(_count_seller_disputes(db, ctx.seller_id)),
        "velocity_1h": float(_count_recent_buyer_transactions(db, ctx.buyer_id)),
        "seller_rating": _avg_seller_rating(db, ctx.seller_id),
        "is_new_seller": 1.0 if ctx.seller_age_days < NEW_SELLER_AGE_DAYS_THRESHOLD else 0.0,
        "payment_method": ctx.payment_method,
        "category": ctx.category,
    }


def _count_seller_disputes(db: Session, seller_id) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Dispute)
        .join(Order, Dispute.order_id == Order.id)
        .where(Order.seller_id == seller_id)
    ) or 0


def _count_recent_buyer_transactions(db: Session, buyer_id) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    return db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.buyer_id == buyer_id, Transaction.created_at >= since)
    ) or 0


def _avg_seller_rating(db: Session, seller_id) -> float:
    avg_rating = db.scalar(select(func.avg(Review.rating)).where(Review.seller_id == seller_id))
    return float(avg_rating) if avg_rating is not None else DEFAULT_SELLER_RATING
