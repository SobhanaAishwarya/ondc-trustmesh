import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.dispute import DisputeReason
from app.models.order import OrderStatus
from app.models.transaction import PaymentMethod, TransactionStatus


class OrderCreate(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(ge=1, default=1)
    payment_method: PaymentMethod


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class ReturnRequest(BaseModel):
    reason: DisputeReason
    description: str | None = None
    # "good" gets an automatic full refund (no seller counter-evidence
    # needed); anything else falls back to the standard contested-dispute
    # flow, since a damaged/incomplete return needs the seller's side too.
    item_condition: str = Field(default="good", pattern="^(good|damaged|missing_parts)$")


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    buyer_id: uuid.UUID
    seller_id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    amount: Decimal
    status: OrderStatus
    onchain_order_id: int | None
    escrow_tx_hash: str | None
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    buyer_id: uuid.UUID
    seller_id: uuid.UUID
    amount: Decimal
    payment_method: PaymentMethod
    status: TransactionStatus
    is_fraud_flagged: bool
    fraud_probability: Decimal | None
    onchain_tx_hash: str | None
    created_at: datetime


class OrderWithTransaction(BaseModel):
    order: OrderRead
    transaction: TransactionRead
