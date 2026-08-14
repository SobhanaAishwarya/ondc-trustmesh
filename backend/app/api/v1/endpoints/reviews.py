"""Buyer reviews — one per delivered order (`reviews.order_id` is UNIQUE in
schema.sql). Posting a review recomputes the seller's trust score since
`avg_customer_rating` is one of its inputs.
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentBuyer, DbSession
from app.models.order import Order, OrderStatus
from app.models.review import Review
from app.models.seller import Seller
from app.schemas.review import ReviewCreate, ReviewRead
from app.services.trust_service import recompute_trust_score

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
def create_review(payload: ReviewCreate, buyer: CurrentBuyer, db: DbSession) -> ReviewRead:
    order = db.get(Order, payload.order_id)
    if order is None or order.buyer_id != buyer.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    if order.status != OrderStatus.delivered:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Can only review delivered orders")
    if db.scalar(select(Review).where(Review.order_id == order.id)) is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This order has already been reviewed")

    review = Review(
        order_id=order.id,
        buyer_id=buyer.id,
        seller_id=order.seller_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(review)
    db.flush()  # so the trust-score aggregate query below sees this review

    seller = db.get(Seller, order.seller_id)
    recompute_trust_score(db, seller)

    db.commit()
    db.refresh(review)
    return ReviewRead.model_validate(review)


@router.get("/sellers/{seller_id}", response_model=list[ReviewRead])
def list_seller_reviews(seller_id: uuid.UUID, db: DbSession) -> list[ReviewRead]:
    reviews = db.scalars(
        select(Review).where(Review.seller_id == seller_id).order_by(Review.created_at.desc())
    ).all()
    return [ReviewRead.model_validate(r) for r in reviews]
