import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FraudLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID
    model_name: str
    model_version: str
    fraud_probability: Decimal
    is_flagged: bool
    risk_factors: dict | None
    reviewed_by_admin_id: uuid.UUID | None
    admin_decision: str | None
    created_at: datetime


class FraudReviewUpdate(BaseModel):
    admin_decision: str = Field(pattern="^(confirmed_fraud|false_positive)$")
