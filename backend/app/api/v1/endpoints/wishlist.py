"""Buyer wishlist. See app/models/wishlist.py for why this table exists
outside the original 12-table schema."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentBuyer, DbSession
from app.models.product import Product
from app.models.wishlist import Wishlist
from app.schemas.product import ProductRead
from app.schemas.wishlist import WishlistItemCreate, WishlistItemRead

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.post("", response_model=WishlistItemRead, status_code=status.HTTP_201_CREATED)
def add_to_wishlist(payload: WishlistItemCreate, buyer: CurrentBuyer, db: DbSession) -> WishlistItemRead:
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    existing = db.scalar(
        select(Wishlist).where(Wishlist.buyer_id == buyer.id, Wishlist.product_id == product.id)
    )
    if existing is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Product already in wishlist")

    item = Wishlist(buyer_id=buyer.id, product_id=product.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return WishlistItemRead(id=item.id, product=ProductRead.model_validate(product), created_at=item.created_at)


@router.get("", response_model=list[WishlistItemRead])
def list_wishlist(buyer: CurrentBuyer, db: DbSession) -> list[WishlistItemRead]:
    rows = db.execute(
        select(Wishlist, Product)
        .join(Product, Wishlist.product_id == Product.id)
        .where(Wishlist.buyer_id == buyer.id)
        .order_by(Wishlist.created_at.desc())
    ).all()
    return [WishlistItemRead(id=w.id, product=ProductRead.model_validate(p), created_at=w.created_at) for w, p in rows]


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_wishlist(product_id: uuid.UUID, buyer: CurrentBuyer, db: DbSession) -> None:
    item = db.scalar(select(Wishlist).where(Wishlist.buyer_id == buyer.id, Wishlist.product_id == product_id))
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not in wishlist")
    db.delete(item)
    db.commit()
