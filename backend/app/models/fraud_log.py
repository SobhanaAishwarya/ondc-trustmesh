import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID

# JSONB on Postgres (matches schema.sql), plain JSON elsewhere (e.g. SQLite tests).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class FraudLog(Base):
    """Every scored transaction, not just flagged ones — the full audit
    trail a fraud model needs to be evaluated and re-trained against later,
    including admin feedback on false positives."""

    __tablename__ = "fraud_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    fraud_probability: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    is_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    risk_factors: Mapped[dict | None] = mapped_column(JSONType)
    reviewed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    admin_decision: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
