import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class TrustScore(Base):
    """One row per computation (not a single mutable column on `sellers`) so
    the dashboard can chart trust drift over time and audits can see exactly
    which factors moved the score at each point."""

    __tablename__ = "trust_scores"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    seller_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    transaction_success_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    delivery_success_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    avg_customer_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    complaint_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    dispute_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fraud_probability: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    refund_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    late_delivery_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    order_completion_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    onchain_tx_hash: Mapped[str | None] = mapped_column(String(66))
    # Client-side default (microsecond resolution) rather than relying only on
    # server_default=func.now() — SQLite's CURRENT_TIMESTAMP is second-grained,
    # so two rows computed within the same second would otherwise tie and make
    # "ORDER BY computed_at DESC" pick an arbitrary one as "latest".
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), index=True
    )
