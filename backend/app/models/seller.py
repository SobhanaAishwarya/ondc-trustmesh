import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class Seller(Base):
    __tablename__ = "sellers"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    wallet_address: Mapped[str | None] = mapped_column(String(42), index=True)
    # True only once ownership was proven by a signature over a one-time
    # nonce (POST /auth/wallet/link) — set alongside wallet_address so the
    # two can never disagree. See alembic/versions/0005_wallet_verified.py.
    wallet_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gstin: Mapped[str | None] = mapped_column(String(15))
    seller_age_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # One of app.core.geo.CITY_NAMES, or None if unset — feeds the
    # recommendation service's proximity signal (see 0004_add_location_fields).
    city: Mapped[str | None] = mapped_column(String(100))
    # How far this seller is willing/able to ship, in km — shapes how fast
    # the proximity score decays with distance (see recommendation_service).
    delivery_radius_km: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    current_trust_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("50.00"))
    is_onchain_registered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_flagged_fraud: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="seller")
