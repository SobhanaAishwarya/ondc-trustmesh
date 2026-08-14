import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class PaymentMethod(str, enum.Enum):
    upi = "upi"
    card = "card"
    cod = "cod"
    wallet = "wallet"


class TransactionStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"
    refunded = "refunded"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("buyers.id"), nullable=False, index=True)
    seller_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("sellers.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod, name="payment_method"), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, name="transaction_status"), nullable=False, default=TransactionStatus.pending
    )
    is_fraud_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    fraud_probability: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    onchain_tx_hash: Mapped[str | None] = mapped_column(String(66))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
