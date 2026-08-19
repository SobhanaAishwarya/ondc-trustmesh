"""Transaction status updates that live outside the buyer/seller-facing
order flow itself — currently just the refund sync a dispute/return
resolution needs so `TransactionStatus.refunded` (read by trust_service's
refund_ratio) actually gets written, not just defined and always empty.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionStatus


def mark_refunded_if_buyer_won_any_share(db: Session, order_id: uuid.UUID, seller_share_bps: int) -> None:
    """A resolution where the buyer keeps any share of the order amount
    (seller_share_bps < 10000) means real money is meant to go back to the
    buyer — the order's transaction should reflect that. There's no
    "partially refunded" status in the schema, so a partial split still
    counts as refunded: from the buyer's side, some money came back.
    Touches the most recent transaction on the order — the schema creates
    exactly one per order today (see orders.create_order)."""
    if seller_share_bps >= 10000:
        return
    transaction = db.scalar(
        select(Transaction).where(Transaction.order_id == order_id).order_by(Transaction.created_at.desc())
    )
    if transaction is not None and transaction.status != TransactionStatus.refunded:
        transaction.status = TransactionStatus.refunded
