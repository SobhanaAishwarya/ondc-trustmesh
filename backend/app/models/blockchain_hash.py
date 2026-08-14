import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class BlockchainHash(Base):
    """Append-only audit trail linking an off-chain row (order, trust score
    update, dispute resolution) to the on-chain transaction that recorded
    it, so every state change that matters is independently verifiable."""

    __tablename__ = "blockchain_hashes"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    tx_hash: Mapped[str] = mapped_column(String(66), nullable=False, index=True)
    block_number: Mapped[int | None] = mapped_column(BigInteger)
    network: Mapped[str] = mapped_column(String(50), nullable=False, default="sepolia")
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_hash: Mapped[str | None] = mapped_column(String(66))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
