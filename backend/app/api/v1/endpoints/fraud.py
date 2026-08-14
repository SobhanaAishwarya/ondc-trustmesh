"""Fraud alerts: scoped read access for buyers/sellers over transactions
they're a party to, full visibility + an admin review workflow otherwise.
Scoring itself happens synchronously in orders.py at order-creation time —
this router only exposes what was already computed and recorded.
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentAdmin, CurrentUser, DbSession
from app.models.buyer import Buyer
from app.models.fraud_log import FraudLog
from app.models.seller import Seller
from app.models.transaction import Transaction
from app.models.user import UserRole
from app.schemas.common import Page
from app.schemas.fraud import FraudLogRead, FraudReviewUpdate

router = APIRouter(prefix="/fraud", tags=["fraud"])


@router.get("/alerts", response_model=Page[FraudLogRead])
def list_fraud_alerts(
    user: CurrentUser,
    db: DbSession,
    only_flagged: bool = True,
    limit: int = 20,
    offset: int = 0,
) -> Page[FraudLogRead]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    conditions = []
    if user.role == UserRole.buyer:
        buyer = db.scalar(select(Buyer).where(Buyer.user_id == user.id))
        conditions.append(Transaction.buyer_id == (buyer.id if buyer else None))
    elif user.role == UserRole.seller:
        seller = db.scalar(select(Seller).where(Seller.user_id == user.id))
        conditions.append(Transaction.seller_id == (seller.id if seller else None))
    if only_flagged:
        conditions.append(FraudLog.is_flagged.is_(True))

    base = select(FraudLog).join(Transaction, FraudLog.transaction_id == Transaction.id).where(*conditions)
    count_query = (
        select(func.count())
        .select_from(FraudLog)
        .join(Transaction, FraudLog.transaction_id == Transaction.id)
        .where(*conditions)
    )

    total = db.scalar(count_query) or 0
    logs = db.scalars(base.order_by(FraudLog.created_at.desc()).limit(limit).offset(offset)).all()

    return Page(items=[FraudLogRead.model_validate(log) for log in logs], total=total, limit=limit, offset=offset)


@router.patch("/logs/{fraud_log_id}/review", response_model=FraudLogRead)
def review_fraud_log(fraud_log_id: uuid.UUID, payload: FraudReviewUpdate, admin: CurrentAdmin, db: DbSession) -> FraudLogRead:
    fraud_log = db.get(FraudLog, fraud_log_id)
    if fraud_log is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fraud log not found")

    fraud_log.admin_decision = payload.admin_decision
    fraud_log.reviewed_by_admin_id = admin.id
    db.commit()
    db.refresh(fraud_log)
    return FraudLogRead.model_validate(fraud_log)
