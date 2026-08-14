import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class DisputeStatus(str, enum.Enum):
    open = "open"
    under_review = "under_review"
    auto_resolved = "auto_resolved"
    arbitrated = "arbitrated"
    closed = "closed"


class DisputeReason(str, enum.Enum):
    item_not_received = "item_not_received"
    item_not_as_described = "item_not_as_described"
    buyer_unresponsive = "buyer_unresponsive"
    damaged_in_transit = "damaged_in_transit"
    other = "other"


class Dispute(Base):
    __tablename__ = "disputes"
    __table_args__ = (CheckConstraint("seller_share_bps BETWEEN 0 AND 10000", name="ck_disputes_seller_share_bps"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raised_by_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    reason: Mapped[DisputeReason] = mapped_column(Enum(DisputeReason, name="dispute_reason"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    evidence_buyer_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), default=Decimal("0"))
    evidence_seller_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), default=Decimal("0"))
    status: Mapped[DisputeStatus] = mapped_column(
        Enum(DisputeStatus, name="dispute_status"), nullable=False, default=DisputeStatus.open, index=True
    )
    resolution_outcome: Mapped[str | None] = mapped_column(String(100))
    seller_share_bps: Mapped[int | None] = mapped_column(Integer)
    resolved_by: Mapped[str | None] = mapped_column(String(20))
    onchain_tx_hash: Mapped[str | None] = mapped_column(String(66))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
