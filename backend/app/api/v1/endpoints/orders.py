"""Order placement, tracking, and seller-driven status transitions.

Each order is for a single product + quantity (schema.sql has no
order_items table — that's a deliberate constraint of the existing model,
not a simplification made here). Placing an order also creates its
Transaction: there's no payment gateway integrated yet, so COD is recorded
as pending (settles on delivery) and every other method is treated as
confirmed instantly. Swap that branch for a real gateway webhook later.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentBuyer, CurrentSeller, CurrentUser, DbSession
from app.models.buyer import Buyer
from app.models.dispute import Dispute, DisputeStatus
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.seller import Seller
from app.models.transaction import PaymentMethod, Transaction, TransactionStatus
from app.models.user import User, UserRole
from app.schemas.common import Page
from app.schemas.dispute import DisputeRead
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate, OrderWithTransaction, ReturnRequest, TransactionRead
from app.services.blockchain_service import record_trust_event
from app.services.fraud_service import score_transaction
from app.services.recommendation_service import mark_purchased_if_recommended
from app.services.trust_service import recompute_trust_score

router = APIRouter(prefix="/orders", tags=["orders"])

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.created: {OrderStatus.confirmed, OrderStatus.cancelled},
    OrderStatus.confirmed: {OrderStatus.shipped, OrderStatus.cancelled},
    OrderStatus.shipped: {OrderStatus.delivered},
}

# The paper's "automated return & refund" stage: check the return window,
# check product condition, decide. 7 days is a policy constant, same as
# trust_service.LATE_DELIVERY_SLA_DAYS being a documented assumption
# rather than a per-seller configurable value the schema doesn't have yet.
RETURN_WINDOW_DAYS = 7
OPEN_DISPUTE_STATUSES = {DisputeStatus.open, DisputeStatus.under_review}


@router.post("", response_model=OrderWithTransaction, status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, buyer: CurrentBuyer, db: DbSession) -> OrderWithTransaction:
    product = db.get(Product, payload.product_id)
    if product is None or not product.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    if product.stock_quantity < payload.quantity:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Insufficient stock")

    amount = product.price * payload.quantity
    product.stock_quantity -= payload.quantity

    order = Order(
        buyer_id=buyer.id,
        seller_id=product.seller_id,
        product_id=product.id,
        quantity=payload.quantity,
        amount=amount,
        status=OrderStatus.created,
    )
    db.add(order)
    db.flush()  # assigns order.id before the transaction references it

    transaction_status = (
        TransactionStatus.pending if payload.payment_method == PaymentMethod.cod else TransactionStatus.success
    )
    transaction = Transaction(
        order_id=order.id,
        buyer_id=buyer.id,
        seller_id=product.seller_id,
        amount=amount,
        payment_method=payload.payment_method,
        status=transaction_status,
    )
    db.add(transaction)
    db.flush()  # assigns transaction.id before the fraud log references it

    seller = db.get(Seller, product.seller_id)
    score_transaction(db, transaction, buyer, seller, product)
    mark_purchased_if_recommended(db, buyer.id, product.id)

    db.commit()
    db.refresh(order)
    db.refresh(transaction)

    return OrderWithTransaction(
        order=OrderRead.model_validate(order), transaction=TransactionRead.model_validate(transaction)
    )


@router.get("", response_model=Page[OrderRead])
def list_orders(user: CurrentUser, db: DbSession, limit: int = 20, offset: int = 0) -> Page[OrderRead]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    conditions = _scope_to_own_orders(db, user)

    total = db.scalar(select(func.count()).select_from(Order).where(*conditions)) or 0
    orders = db.scalars(
        select(Order).where(*conditions).order_by(Order.created_at.desc()).limit(limit).offset(offset)
    ).all()

    return Page(items=[OrderRead.model_validate(o) for o in orders], total=total, limit=limit, offset=offset)


@router.get("/{order_id}", response_model=OrderRead)
def get_order(order_id: uuid.UUID, user: CurrentUser, db: DbSession) -> OrderRead:
    order = _get_order_or_404(db, order_id)
    _authorize_order_access(db, order, user)
    return OrderRead.model_validate(order)


@router.get("/{order_id}/transactions", response_model=list[TransactionRead])
def list_order_transactions(order_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[TransactionRead]:
    order = _get_order_or_404(db, order_id)
    _authorize_order_access(db, order, user)
    transactions = db.scalars(
        select(Transaction).where(Transaction.order_id == order_id).order_by(Transaction.created_at.desc())
    ).all()
    return [TransactionRead.model_validate(t) for t in transactions]


@router.patch("/{order_id}/status", response_model=OrderRead)
def update_order_status(
    order_id: uuid.UUID, payload: OrderStatusUpdate, seller: CurrentSeller, db: DbSession
) -> OrderRead:
    order = _get_order_or_404(db, order_id)
    if order.seller_id != seller.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not own this order")

    allowed = ALLOWED_TRANSITIONS.get(order.status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot move an order from '{order.status.value}' to '{payload.status.value}'",
        )

    if payload.status == OrderStatus.cancelled:
        product = db.get(Product, order.product_id)
        if product is not None:
            product.stock_quantity += order.quantity

    order.status = payload.status
    if payload.status == OrderStatus.delivered:
        order.delivered_at = datetime.now(timezone.utc)
        db.flush()  # so the trust-score aggregate queries below see this order's new status
        # order_completion_rate/delivery_success_rate/late_delivery_ratio all
        # shift the moment a delivery lands, so recompute trust right away
        # rather than waiting for the next unrelated trigger.
        recompute_trust_score(db, seller)
        record_trust_event(db, seller, "successful_delivery")  # no-op if chain isn't enabled/reachable

    db.commit()
    db.refresh(order)
    return OrderRead.model_validate(order)


@router.post("/{order_id}/return", response_model=DisputeRead, status_code=status.HTTP_201_CREATED)
def request_return(order_id: uuid.UUID, payload: ReturnRequest, buyer: CurrentBuyer, db: DbSession) -> DisputeRead:
    """Self-service return: within the policy window and in good
    condition, this auto-approves a full refund with no seller
    counter-evidence step — distinct from `POST /disputes`, which is for
    contested claims where both sides submit evidence. A damaged/
    incomplete-condition return still creates a dispute, but an open one
    the seller can respond to, since "the buyer says it's damaged" alone
    isn't grounds for an unconditional refund the way "I don't want it
    anymore, still sealed, day 3 of 7" is.
    """
    order = _get_order_or_404(db, order_id)
    if order.buyer_id != buyer.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not own this order")
    if order.status != OrderStatus.delivered or order.delivered_at is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only delivered orders can be returned")

    # SQLite (the test-suite dialect, see app/db/types.py's docstring)
    # doesn't round-trip tzinfo on DateTime(timezone=True) columns the way
    # Postgres does — a value written as UTC-aware comes back naive. Treat
    # a naive reading as UTC rather than letting the subtraction below
    # raise on aware-minus-naive.
    delivered_at = order.delivered_at
    if delivered_at.tzinfo is None:
        delivered_at = delivered_at.replace(tzinfo=timezone.utc)
    days_since_delivery = (datetime.now(timezone.utc) - delivered_at).days
    if days_since_delivery > RETURN_WINDOW_DAYS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Return window ({RETURN_WINDOW_DAYS} days) has passed — delivered {days_since_delivery} days ago",
        )

    existing = db.scalar(
        select(Dispute).where(Dispute.order_id == order.id, Dispute.status.in_(OPEN_DISPUTE_STATUSES))
    )
    if existing is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "An open dispute already exists for this order")

    seller = db.get(Seller, order.seller_id)
    dispute = Dispute(
        order_id=order.id,
        raised_by_user_id=buyer.user_id,
        reason=payload.reason,
        description=payload.description,
        evidence_buyer_score=Decimal("1"),
    )

    if payload.item_condition == "good":
        dispute.status = DisputeStatus.auto_resolved
        dispute.resolution_outcome = "Refund buyer (self-service return, within policy window)"
        dispute.seller_share_bps = 0
        dispute.resolved_by = "auto_return"
        dispute.resolved_at = datetime.now(timezone.utc)
        order.status = OrderStatus.resolved
        trust_event = "dispute_resolved_buyer"
    else:
        dispute.status = DisputeStatus.open
        order.status = OrderStatus.disputed
        trust_event = "dispute_raised"

    db.add(dispute)
    db.flush()

    recompute_trust_score(db, seller)
    record_trust_event(db, seller, trust_event)  # no-op if the chain isn't enabled/reachable
    db.commit()
    db.refresh(dispute)
    return DisputeRead.model_validate(dispute)


def _get_order_or_404(db: DbSession, order_id: uuid.UUID) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return order


def _scope_to_own_orders(db: DbSession, user: User) -> list:
    """Buyers/sellers only ever see their own orders; admins see everything."""
    if user.role == UserRole.buyer:
        buyer = db.scalar(select(Buyer).where(Buyer.user_id == user.id))
        return [Order.buyer_id == (buyer.id if buyer else None)]
    if user.role == UserRole.seller:
        seller = db.scalar(select(Seller).where(Seller.user_id == user.id))
        return [Order.seller_id == (seller.id if seller else None)]
    return []


def _authorize_order_access(db: DbSession, order: Order, user: User) -> None:
    if user.role == UserRole.admin:
        return
    if user.role == UserRole.buyer:
        buyer = db.scalar(select(Buyer).where(Buyer.user_id == user.id))
        if buyer is not None and buyer.id == order.buyer_id:
            return
    if user.role == UserRole.seller:
        seller = db.scalar(select(Seller).where(Seller.user_id == user.id))
        if seller is not None and seller.id == order.seller_id:
            return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this order")
