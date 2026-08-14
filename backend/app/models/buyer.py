import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID, StringArray


class Buyer(Base):
    __tablename__ = "buyers"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    wallet_address: Mapped[str | None] = mapped_column(String(42), index=True)
    price_sensitivity: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=Decimal("0.5"))
    preferred_categories: Mapped[list[str]] = mapped_column(StringArray(), nullable=False, default=list)
    # One of app.core.geo.CITY_NAMES, or None if unset — feeds the
    # recommendation service's proximity signal (see 0004_add_location_fields).
    city: Mapped[str | None] = mapped_column(String(100))
    account_age_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_flagged_fraud: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Added alongside sellers.is_onchain_registered — see
    # alembic/versions/0003_add_buyer_onchain_registered.py. TrustScore.sol's
    # register() is generic over any participant address; the backend just
    # hadn't wired buyers to it yet (only sellers, until this migration).
    is_onchain_registered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="buyer")
