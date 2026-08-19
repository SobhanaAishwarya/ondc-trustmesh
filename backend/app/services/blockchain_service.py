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
from app.models.order import Order
from app.models.seller import Seller

logger = logging.getLogger(__name__)

# Demo wei-scaling convention for escrow amounts — see client.py's
# EscrowDispute section docstring for why this isn't a real currency
# conversion. Two decimal places of rupees survive the scale-up so
# per-order amounts stay distinct.
_ESCROW_WEI_PER_RUPEE = 100


def is_enabled() -> bool:
    return get_settings().blockchain_enabled


def register_seller_onchain(db: Session, seller: Seller) -> BlockchainHash | None:
    if not is_enabled() or not seller.wallet_address or not seller.wallet_verified or seller.is_onchain_registered:
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
    if not is_enabled() or not buyer.wallet_address or not buyer.wallet_verified or buyer.is_onchain_registered:
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


def create_escrow_order(db: Session, order: Order, seller: Seller) -> BlockchainHash | None:
    """Locks the order's amount in EscrowDispute.sol, on the seller's behalf.
    Requires the seller to have registered on-chain first (same wallet_
    address precondition as record_trust_event) — an unregistered seller
    just means this stays a no-op, not an error."""
    if not is_enabled() or not seller.wallet_address or not seller.is_onchain_registered:
        return None
    try:
        amount_wei = int(order.amount * _ESCROW_WEI_PER_RUPEE)
        receipt = client.create_escrow_order(seller.wallet_address, amount_wei)
    except Exception:  # noqa: BLE001
        logger.warning("Escrow order creation skipped for order %s", order.id, exc_info=True)
        return None
    order.onchain_order_id = receipt.get("onchain_order_id")
    order.escrow_tx_hash = receipt["tx_hash"]
    return _record_hash(db, "order", order.id, receipt, "escrow_order_created")


def confirm_escrow_delivery(db: Session, order: Order) -> BlockchainHash | None:
    """Releases the escrowed amount to the seller. A no-op if this order was
    never locked on-chain in the first place (order.onchain_order_id is
    None) — e.g. escrow was disabled at order-creation time."""
    if not is_enabled() or order.onchain_order_id is None:
        return None
    try:
        receipt = client.confirm_escrow_delivery(order.onchain_order_id)
    except Exception:  # noqa: BLE001
        logger.warning("Escrow delivery confirmation skipped for order %s", order.id, exc_info=True)
        return None
    return _record_hash(db, "order", order.id, receipt, "escrow_delivered")


def raise_escrow_dispute(db: Session, order: Order, reason: str) -> BlockchainHash | None:
    """The contract only accepts a dispute while the on-chain order is still
    `Created` (pre-delivery) — see contracts/EscrowDispute.sol's docstring.
    A dispute raised after this order's delivery was already confirmed
    on-chain will genuinely revert here and get caught below; that's the
    contract's real, documented lifecycle limitation surfacing honestly,
    not a bug in this wrapper."""
    if not is_enabled() or order.onchain_order_id is None:
        return None
    try:
        receipt = client.raise_escrow_dispute(order.onchain_order_id, reason)
    except Exception:  # noqa: BLE001
        logger.warning("Escrow dispute raise skipped for order %s", order.id, exc_info=True)
        return None
    return _record_hash(db, "order", order.id, receipt, "escrow_dispute_raised")


def resolve_escrow_dispute(db: Session, order: Order, seller_share_bps: int, *, arbitrated: bool) -> BlockchainHash | None:
    """Settles and pays out an on-chain dispute — rule-based (autoResolve,
    recomputed from live on-chain trust scores rather than trusting the
    off-chain split) or an arbitrator override with an explicit split.
    Only meaningful if raise_escrow_dispute actually succeeded earlier for
    this order (see its docstring on the pre-delivery-only constraint)."""
    if not is_enabled() or order.onchain_order_id is None:
        return None
    try:
        if arbitrated:
            receipt = client.arbitrate_escrow(order.onchain_order_id, seller_share_bps)
        else:
            receipt = client.autoresolve_escrow(order.onchain_order_id)
    except Exception:  # noqa: BLE001
        logger.warning("Escrow dispute resolution skipped for order %s", order.id, exc_info=True)
        return None
    return _record_hash(db, "order", order.id, receipt, "escrow_dispute_resolved")


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
