import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None
    # Role-specific profile id — lets a caller (e.g. the admin Trust
    # Monitoring page) chain into /trust/sellers/{id} or a future
    # buyer-scoped endpoint without a second lookup. Populated by the
    # endpoint, not derived from a relationship (User has none to Buyer/Seller).
    seller_id: uuid.UUID | None = None
    buyer_id: uuid.UUID | None = None


class UserStatusUpdate(BaseModel):
    is_active: bool


class AnalyticsReport(BaseModel):
    total_users: int
    total_buyers: int
    total_sellers: int
    total_admins: int
    total_products: int
    active_products: int
    total_orders: int
    orders_by_status: dict[str, int]
    total_transactions: int
    total_revenue: Decimal
    fraud_flagged_transactions: int
    fraud_flag_rate: float
    average_seller_trust_score: float
    open_disputes: int
    total_disputes: int


class BlockchainHashRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    tx_hash: str
    block_number: int | None
    network: str
    event_type: str
    payload_hash: str | None
    confirmed_at: datetime | None
    created_at: datetime
