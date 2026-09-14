import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str = Field(min_length=1, max_length=100)
    tags: list[str] = Field(default_factory=list)
    price: Decimal = Field(gt=0, decimal_places=2)
    stock_quantity: int = Field(ge=0, default=0)
    image_url: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, min_length=1, max_length=100)
    tags: list[str] | None = None
    price: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    stock_quantity: int | None = Field(default=None, ge=0)
    image_url: str | None = None
    is_active: bool | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seller_id: uuid.UUID
    name: str
    description: str | None
    category: str
    tags: list[str]
    price: Decimal
    stock_quantity: int
    image_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class VendorMatchRead(BaseModel):
    """One row of `GET /products/compare` — a single seller's listing of
    the searched-for product, plus the sub-scores that produced its
    match_score, so the ranking is auditable rather than a black box."""

    product: ProductRead
    seller_id: uuid.UUID
    seller_name: str
    rating: float
    distance_km: float | None
    estimated_delivery_days: int | None
    match_score: float
    is_best_match: bool
