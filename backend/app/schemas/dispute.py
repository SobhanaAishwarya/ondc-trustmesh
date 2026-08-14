import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.dispute import DisputeReason, DisputeStatus


class DisputeCreate(BaseModel):
    order_id: uuid.UUID
    reason: DisputeReason
    description: str | None = None
    evidence_score: Decimal = Field(default=Decimal("0"), ge=0, le=1)


class DisputeEvidenceSubmit(BaseModel):
    evidence_score: Decimal = Field(ge=0, le=1)


class DisputeArbitrate(BaseModel):
    seller_share_bps: int = Field(ge=0, le=10000)


class DisputeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    raised_by_user_id: uuid.UUID
    reason: DisputeReason
    description: str | None
    evidence_buyer_score: Decimal | None
    evidence_seller_score: Decimal | None
    status: DisputeStatus
    resolution_outcome: str | None
    seller_share_bps: int | None
    resolved_by: str | None
    onchain_tx_hash: str | None
    created_at: datetime
    resolved_at: datetime | None
