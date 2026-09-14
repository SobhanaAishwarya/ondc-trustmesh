"""Rule-based fraud sub-detectors, layered on top of the general RandomForest
classifier in `model.py`.

`backend/README.md`'s "What's next" section called this out as a real gap:
the classifier is one general-purpose model, and `is_new_seller`/
`velocity_1h` are only *proxies* for duplicate-account and bot-activity
patterns, not dedicated detectors. These two rules are deliberately simple
and explainable (a human can say exactly why one fired, unlike a model
probability) and deliberately don't need any schema change — they read
columns that already exist (`users.phone`, `transactions.created_at`).

Explicit, separate scope: location-anomaly detection stays out. That needs
an address/geo column that doesn't exist on buyers/sellers yet — faking it
here would mean scoring against data that isn't real, which is exactly the
mistake `features.py` already documents avoiding for `distance_km`.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.buyer import Buyer
from app.models.transaction import Transaction
from app.models.user import User

# 2+ buyer accounts sharing one phone number is unusual enough to flag for
# review without being so strict it catches ordinary shared-household use
# (one number, two people) as fraud.
DUPLICATE_ACCOUNT_PHONE_THRESHOLD = 2

# Separate from, and tighter than, the continuous `velocity_1h` feature the
# ML model already sees — this is a hard, explainable line ("6+ orders by
# the same buyer inside an hour is not normal human shopping behaviour"),
# not a learned pattern.
VELOCITY_BOT_ORDER_THRESHOLD = 6


@dataclass(frozen=True)
class RuleSignal:
    triggered: bool
    detail: dict


def evaluate_rule_based_signals(db: Session, buyer: Buyer) -> dict[str, dict]:
    """Runs every rule-based sub-detector for one buyer and returns a dict
    shaped for `FraudLog.rule_signals` — always present (even when nothing
    triggered) so the absence of a signal is visible, not just missing."""
    duplicate = _duplicate_account_signal(db, buyer)
    velocity = _velocity_bot_signal(db, buyer)
    return {
        "duplicate_account_suspected": {"triggered": duplicate.triggered, **duplicate.detail},
        "high_velocity_bot_suspected": {"triggered": velocity.triggered, **velocity.detail},
    }


def any_rule_triggered(rule_signals: dict[str, dict]) -> bool:
    return any(signal["triggered"] for signal in rule_signals.values())


def _duplicate_account_signal(db: Session, buyer: Buyer) -> RuleSignal:
    phone = db.scalar(select(User.phone).where(User.id == buyer.user_id))
    if not phone:
        return RuleSignal(False, {"phone_shared_by_accounts": 0})

    matching_accounts = db.scalar(
        select(func.count()).select_from(User).where(User.phone == phone)
    ) or 0
    return RuleSignal(
        matching_accounts >= DUPLICATE_ACCOUNT_PHONE_THRESHOLD,
        {"phone_shared_by_accounts": matching_accounts},
    )


def _velocity_bot_signal(db: Session, buyer: Buyer) -> RuleSignal:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    orders_last_hour = db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.buyer_id == buyer.id, Transaction.created_at >= since)
    ) or 0
    return RuleSignal(
        orders_last_hour >= VELOCITY_BOT_ORDER_THRESHOLD,
        {"orders_last_hour": orders_last_hour},
    )
