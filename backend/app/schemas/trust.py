import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TrustScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seller_id: uuid.UUID
    score: Decimal
    transaction_success_rate: Decimal | None
    delivery_success_rate: Decimal | None
    avg_customer_rating: Decimal | None
    complaint_ratio: Decimal | None
    dispute_count: int
    fraud_probability: Decimal | None
    refund_ratio: Decimal | None
    late_delivery_ratio: Decimal | None
    order_completion_rate: Decimal | None
    onchain_tx_hash: str | None
    computed_at: datetime


class OnchainTrustRead(BaseModel):
    seller_id: uuid.UUID
    wallet_address: str | None
    is_onchain_registered: bool
    onchain_score: int | None
    blockchain_enabled: bool
