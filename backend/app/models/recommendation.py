import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class Recommendation(Base):
    """Logged impression, one row per (buyer, product) shown — used to
    compute CTR: was_clicked / count(*)."""

    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("buyers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    algorithm: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    was_clicked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    was_purchased: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
