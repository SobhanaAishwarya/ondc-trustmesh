import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.product import ProductRead


class RecommendationItemRead(BaseModel):
    id: uuid.UUID
    product: ProductRead
    algorithm: str
    score: Decimal
    rank: int
    was_clicked: bool
    was_purchased: bool
    shown_at: datetime
    # Buyer-seller city distance and a coarse ETA bucket — None when either
    # party's city is unset. Computed at read time (app.core.geo), not
    # persisted, since it isn't a property of the impression itself.
    distance_km: float | None = None
    estimated_delivery_days: int | None = None


class CTRReport(BaseModel):
    algorithm: str | None
    impressions: int
    clicks: int
    purchases: int
    ctr: float
    click_to_purchase_rate: float
