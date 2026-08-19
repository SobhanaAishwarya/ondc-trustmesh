"""Dispute lifecycle: either party to an order can raise one. Once both
sides have submitted evidence, resolution happens automatically via
services/dispute_service.resolve() (mirrors contracts/EscrowDispute.sol's
autoResolve()); admins can override via arbitration at any point.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentAdmin, CurrentUser, DbSession
from app.models.buyer import Buyer
from app.models.dispute import Dispute, DisputeStatus
from app.models.order import Order, OrderStatus
from app.models.seller import Seller
from app.models.user import UserRole
from app.schemas.common import Page
from app.schemas.dispute import DisputeArbitrate, DisputeCreate, DisputeEvidenceSubmit, DisputeRead
from app.services.blockchain_service import raise_escrow_dispute, record_trust_event, resolve_escrow_dispute
from app.services.dispute_service import ephemeral_buyer_trust, resolve
from app.services.transaction_service import mark_refunded_if_buyer_won_any_share
from app.services.trust_service import recompute_trust_score

router = APIRouter(prefix="/disputes", tags=["disputes"])

RAISABLE_ORDER_STATUSES = {OrderStatus.confirmed, OrderStatus.shipped, OrderStatus.delivered}
OPEN_DISPUTE_STATUSES = {DisputeStatus.open, DisputeStatus.under_review}
TERMINAL_DISPUTE_STATUSES = {DisputeStatus.auto_resolved, DisputeStatus.arbitrated, DisputeStatus.closed}
# Matches EscrowDispute.sol's AUTO_RESOLVE_THRESHOLD_BPS — same cutoff
# on-chain and off-chain for which trust-score event a resolution fires.
SELLER_WIN_THRESHOLD_BPS = 6500


@router.post("", response_model=DisputeRead, status_code=status.HTTP_201_CREATED)
def raise_dispute(payload: DisputeCreate, user: CurrentUser, db: DbSession) -> DisputeRead:
    order = db.get(Order, payload.order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")

    buyer, seller = _resolve_parties(db, order)
    is_buyer_party = user.role == UserRole.buyer and buyer is not None and buyer.user_id == user.id
    is_seller_party = user.role == UserRole.seller and seller is not None and seller.user_id == user.id
    if not (is_buyer_party or is_seller_party):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not a party to this order")

    if order.status not in RAISABLE_ORDER_STATUSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Cannot raise a dispute on an order in '{order.status.value}' status"
        )
    existing = db.scalar(
        select(Dispute).where(Dispute.order_id == order.id, Dispute.status.in_(OPEN_DISPUTE_STATUSES))
    )
    if existing is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "An open dispute already exists for this order")

    dispute = Dispute(
        order_id=order.id,
        raised_by_user_id=user.id,
        reason=payload.reason,
        description=payload.description,
        status=DisputeStatus.open,
    )
    if is_buyer_party:
        dispute.evidence_buyer_score = payload.evidence_score
    else:
        dispute.evidence_seller_score = payload.evidence_score

    db.add(dispute)
    order.status = OrderStatus.disputed
    db.flush()

    recompute_trust_score(db, seller)
    record_trust_event(db, seller, "dispute_raised")
    escrow_hash = raise_escrow_dispute(db, order, payload.reason.value)  # no-op / honest failure, see its docstring
    if escrow_hash is not None:
        dispute.onchain_tx_hash = escrow_hash.tx_hash
    db.commit()
    db.refresh(dispute)
    return DisputeRead.model_validate(dispute)


@router.post("/{dispute_id}/evidence", response_model=DisputeRead)
def submit_evidence(
    dispute_id: uuid.UUID, payload: DisputeEvidenceSubmit, user: CurrentUser, db: DbSession
) -> DisputeRead:
    dispute = _get_dispute_or_404(db, dispute_id)
    if dispute.status not in OPEN_DISPUTE_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Dispute already {dispute.status.value}")

    order = db.get(Order, dispute.order_id)
    buyer, seller = _resolve_parties(db, order)

    if user.role == UserRole.buyer and buyer is not None and buyer.user_id == user.id:
        dispute.evidence_buyer_score = payload.evidence_score
    elif user.role == UserRole.seller and seller is not None and seller.user_id == user.id:
        dispute.evidence_seller_score = payload.evidence_score
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not a party to this dispute")

    dispute.status = DisputeStatus.under_review

    if dispute.evidence_buyer_score is not None and dispute.evidence_seller_score is not None:
        _auto_resolve(db, dispute, order, buyer, seller)

    db.commit()
    db.refresh(dispute)
    return DisputeRead.model_validate(dispute)


@router.patch("/{dispute_id}/arbitrate", response_model=DisputeRead)
def arbitrate_dispute(dispute_id: uuid.UUID, payload: DisputeArbitrate, admin: CurrentAdmin, db: DbSession) -> DisputeRead:
    dispute = _get_dispute_or_404(db, dispute_id)
    if dispute.status in TERMINAL_DISPUTE_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Dispute already {dispute.status.value}")

    order = db.get(Order, dispute.order_id)
    dispute.seller_share_bps = payload.seller_share_bps
    dispute.resolution_outcome = "Arbitrator override"
    dispute.resolved_by = "arbitrator"
    dispute.status = DisputeStatus.arbitrated
    dispute.resolved_at = datetime.now(timezone.utc)
    order.status = OrderStatus.resolved
    mark_refunded_if_buyer_won_any_share(db, order.id, payload.seller_share_bps)

    seller = db.get(Seller, order.seller_id)
    recompute_trust_score(db, seller)
    event = "dispute_resolved_seller" if payload.seller_share_bps >= SELLER_WIN_THRESHOLD_BPS else "dispute_resolved_buyer"
    record_trust_event(db, seller, event)
    escrow_hash = resolve_escrow_dispute(db, order, payload.seller_share_bps, arbitrated=True)
    if escrow_hash is not None:
        dispute.onchain_tx_hash = escrow_hash.tx_hash

    db.commit()
    db.refresh(dispute)
    return DisputeRead.model_validate(dispute)


@router.get("", response_model=Page[DisputeRead])
def list_disputes(user: CurrentUser, db: DbSession, limit: int = 20, offset: int = 0) -> Page[DisputeRead]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    conditions = []
    if user.role == UserRole.buyer:
        buyer = db.scalar(select(Buyer).where(Buyer.user_id == user.id))
        conditions.append(Dispute.order_id.in_(select(Order.id).where(Order.buyer_id == (buyer.id if buyer else None))))
    elif user.role == UserRole.seller:
        seller = db.scalar(select(Seller).where(Seller.user_id == user.id))
        conditions.append(
            Dispute.order_id.in_(select(Order.id).where(Order.seller_id == (seller.id if seller else None)))
        )

    total = db.scalar(select(func.count()).select_from(Dispute).where(*conditions)) or 0
    disputes = db.scalars(
        select(Dispute).where(*conditions).order_by(Dispute.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return Page(items=[DisputeRead.model_validate(d) for d in disputes], total=total, limit=limit, offset=offset)


@router.get("/{dispute_id}", response_model=DisputeRead)
def get_dispute(dispute_id: uuid.UUID, user: CurrentUser, db: DbSession) -> DisputeRead:
    dispute = _get_dispute_or_404(db, dispute_id)
    order = db.get(Order, dispute.order_id)
    buyer, seller = _resolve_parties(db, order)
    is_party = (user.role == UserRole.buyer and buyer is not None and buyer.user_id == user.id) or (
        user.role == UserRole.seller and seller is not None and seller.user_id == user.id
    )
    if not (is_party or user.role == UserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this dispute")
    return DisputeRead.model_validate(dispute)


def _auto_resolve(db: DbSession, dispute: Dispute, order: Order, buyer: Buyer, seller: Seller) -> None:
    result = resolve(
        seller_trust_score=float(seller.current_trust_score),
        buyer_trust_score=ephemeral_buyer_trust(buyer),
        evidence_seller=dispute.evidence_seller_score or 0,
        evidence_buyer=dispute.evidence_buyer_score or 0,
        delivery_confirmed=order.status == OrderStatus.delivered,
        reason=dispute.reason,
    )
    dispute.resolution_outcome = result["outcome"]
    dispute.seller_share_bps = result["seller_share_bps"]
    dispute.resolved_by = "rule_auto"
    dispute.status = DisputeStatus.auto_resolved
    dispute.resolved_at = datetime.now(timezone.utc)
    order.status = OrderStatus.resolved
    mark_refunded_if_buyer_won_any_share(db, order.id, result["seller_share_bps"])
    recompute_trust_score(db, seller)
    event = "dispute_resolved_seller" if result["seller_share_bps"] >= SELLER_WIN_THRESHOLD_BPS else "dispute_resolved_buyer"
    record_trust_event(db, seller, event)
    escrow_hash = resolve_escrow_dispute(db, order, result["seller_share_bps"], arbitrated=False)
    if escrow_hash is not None:
        dispute.onchain_tx_hash = escrow_hash.tx_hash


def _get_dispute_or_404(db: DbSession, dispute_id: uuid.UUID) -> Dispute:
    dispute = db.get(Dispute, dispute_id)
    if dispute is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dispute not found")
    return dispute


def _resolve_parties(db: DbSession, order: Order) -> tuple[Buyer, Seller]:
    return db.get(Buyer, order.buyer_id), db.get(Seller, order.seller_id)
