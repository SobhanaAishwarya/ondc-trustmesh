"""Ties DB entities to on-chain calls (contracts/TrustScore.sol via
app/blockchain/client.py). Every function here is best-effort: if the
chain isn't enabled/reachable, it logs a warning and returns `None` rather
than raising — placing an order, delivering it, raising a dispute, or
flagging fraud must never fail just because a blockchain node happens to
be down. A caught-but-logged `except Exception` is deliberate here, not
sloppy error handling: this module's entire job is to isolate an optional
side effect from the request that triggered it.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.blockchain import client
from app.core.config import get_settings
from app.models.blockchain_hash import BlockchainHash
from app.models.buyer import Buyer
from app.models.seller import Seller

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return get_settings().blockchain_enabled


def register_seller_onchain(db: Session, seller: Seller) -> BlockchainHash | None:
    if not is_enabled() or not seller.wallet_address or seller.is_onchain_registered:
        return None
    try:
        receipt = client.register_participant(seller.wallet_address)
    except Exception:  # noqa: BLE001 — best-effort side effect, see module docstring
        logger.warning("On-chain registration skipped for seller %s", seller.id, exc_info=True)
        return None

    seller.is_onchain_registered = True
    return _record_hash(db, "seller", seller.id, receipt, "seller_registered")


def register_buyer_onchain(db: Session, buyer: Buyer) -> BlockchainHash | None:
    """Mirrors `register_seller_onchain` — `TrustScore.sol`'s `register()`
    is generic over any participant address. Buyers don't yet get ongoing
    trust *events* recorded (the event vocabulary — successful_delivery,
    dispute_raised, etc. — is seller-performance-centric; see
    `record_trust_event`), only this initial on-chain registration."""
    if not is_enabled() or not buyer.wallet_address or buyer.is_onchain_registered:
        return None
    try:
        receipt = client.register_participant(buyer.wallet_address)
    except Exception:  # noqa: BLE001
        logger.warning("On-chain registration skipped for buyer %s", buyer.id, exc_info=True)
        return None

    buyer.is_onchain_registered = True
    return _record_hash(db, "buyer", buyer.id, receipt, "buyer_registered")


def record_trust_event(db: Session, seller: Seller, event_type: str) -> BlockchainHash | None:
    if not is_enabled() or not seller.wallet_address or not seller.is_onchain_registered:
        return None
    try:
        receipt = client.record_event(seller.wallet_address, event_type)
    except Exception:  # noqa: BLE001
        logger.warning("On-chain event '%s' skipped for seller %s", event_type, seller.id, exc_info=True)
        return None
    return _record_hash(db, "seller", seller.id, receipt, event_type)


def get_onchain_score(seller: Seller) -> int | None:
    if not is_enabled() or not seller.wallet_address:
        return None
    try:
        return client.get_onchain_score(seller.wallet_address)
    except Exception:  # noqa: BLE001
        logger.warning("On-chain score read skipped for seller %s", seller.id, exc_info=True)
        return None


def _record_hash(db: Session, entity_type: str, entity_id: uuid.UUID, receipt: dict, event_type: str) -> BlockchainHash:
    row = BlockchainHash(
        entity_type=entity_type,
        entity_id=entity_id,
        tx_hash=receipt["tx_hash"],
        block_number=receipt["block_number"],
        network=get_settings().blockchain_network,
        event_type=event_type,
    )
    db.add(row)
    return row
