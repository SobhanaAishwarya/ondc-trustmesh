"""Admin-only endpoints: user management and a consolidated analytics
dashboard — covers "Fraud Dashboard"/"Trust Monitoring"/"Analytics Dashboard"
from the brief in one place rather than three near-duplicate endpoints.
Fraud-log review lives in fraud.py and dispute arbitration in disputes.py —
both already admin-gated — this router doesn't re-implement either.
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select

from app.api.deps import CurrentAdmin, DbSession
from app.models.blockchain_hash import BlockchainHash
from app.models.buyer import Buyer
from app.models.dispute import Dispute, DisputeStatus
from app.models.fraud_log import FraudLog
from app.models.order import Order
from app.models.product import Product
from app.models.seller import Seller
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import User, UserRole
from app.schemas.admin import AdminUserRead, AnalyticsReport, BlockchainHashRead, UserStatusUpdate
from app.schemas.common import Page

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=Page[AdminUserRead])
def list_users(
    admin: CurrentAdmin,
    db: DbSession,
    role: UserRole | None = None,
    is_active: bool | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> Page[AdminUserRead]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    conditions = []
    if role is not None:
        conditions.append(User.role == role)
    if is_active is not None:
        conditions.append(User.is_active == is_active)
    if q:
        like = f"%{q}%"
        conditions.append(or_(User.email.ilike(like), User.full_name.ilike(like)))

    total = db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0
    users = db.scalars(
        select(User).where(*conditions).order_by(User.created_at.desc()).limit(limit).offset(offset)
    ).all()

    # User has no relationship to Buyer/Seller (see app/models/user.py), so
    # resolve role-specific profile ids with two bulk lookups rather than
    # per-row queries.
    user_ids = [u.id for u in users]
    seller_by_user = dict(db.execute(select(Seller.user_id, Seller.id).where(Seller.user_id.in_(user_ids))).all())
    buyer_by_user = dict(db.execute(select(Buyer.user_id, Buyer.id).where(Buyer.user_id.in_(user_ids))).all())

    items = []
    for u in users:
        item = AdminUserRead.model_validate(u)
        item.seller_id = seller_by_user.get(u.id)
        item.buyer_id = buyer_by_user.get(u.id)
        items.append(item)

    return Page(items=items, total=total, limit=limit, offset=offset)


@router.patch("/users/{user_id}/status", response_model=AdminUserRead)
def update_user_status(
    user_id: uuid.UUID, payload: UserStatusUpdate, admin: CurrentAdmin, db: DbSession
) -> AdminUserRead:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id and not payload.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot deactivate your own account")

    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return AdminUserRead.model_validate(user)


@router.get("/analytics", response_model=AnalyticsReport)
def analytics(admin: CurrentAdmin, db: DbSession) -> AnalyticsReport:
    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    total_buyers = db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.buyer)) or 0
    total_sellers = db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.seller)) or 0
    total_admins = db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.admin)) or 0

    total_products = db.scalar(select(func.count()).select_from(Product)) or 0
    active_products = db.scalar(select(func.count()).select_from(Product).where(Product.is_active.is_(True))) or 0

    total_orders = db.scalar(select(func.count()).select_from(Order)) or 0
    orders_by_status_raw = dict(db.execute(select(Order.status, func.count()).group_by(Order.status)).all())
    orders_by_status = {order_status.value: count for order_status, count in orders_by_status_raw.items()}

    total_transactions = db.scalar(select(func.count()).select_from(Transaction)) or 0
    total_revenue = (
        db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.status == TransactionStatus.success
            )
        )
        or Decimal("0")
    )

    fraud_flagged = db.scalar(select(func.count()).select_from(FraudLog).where(FraudLog.is_flagged.is_(True))) or 0
    total_fraud_logs = db.scalar(select(func.count()).select_from(FraudLog)) or 0

    avg_trust = db.scalar(select(func.avg(Seller.current_trust_score)))

    open_disputes = (
        db.scalar(
            select(func.count())
            .select_from(Dispute)
            .where(Dispute.status.in_([DisputeStatus.open, DisputeStatus.under_review]))
        )
        or 0
    )
    total_disputes = db.scalar(select(func.count()).select_from(Dispute)) or 0

    return AnalyticsReport(
        total_users=total_users,
        total_buyers=total_buyers,
        total_sellers=total_sellers,
        total_admins=total_admins,
        total_products=total_products,
        active_products=active_products,
        total_orders=total_orders,
        orders_by_status=orders_by_status,
        total_transactions=total_transactions,
        total_revenue=total_revenue,
        fraud_flagged_transactions=fraud_flagged,
        fraud_flag_rate=round(fraud_flagged / total_fraud_logs, 4) if total_fraud_logs else 0.0,
        average_seller_trust_score=round(float(avg_trust), 2) if avg_trust is not None else 0.0,
        open_disputes=open_disputes,
        total_disputes=total_disputes,
    )


@router.get("/blockchain-hashes", response_model=Page[BlockchainHashRead])
def list_blockchain_hashes(
    admin: CurrentAdmin, db: DbSession, limit: int = 20, offset: int = 0
) -> Page[BlockchainHashRead]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    total = db.scalar(select(func.count()).select_from(BlockchainHash)) or 0
    rows = db.scalars(
        select(BlockchainHash).order_by(BlockchainHash.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return Page(items=[BlockchainHashRead.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)
