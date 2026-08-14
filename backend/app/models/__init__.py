"""Import every model so `Base.metadata` is fully populated for Alembic
autogenerate and for `Base.metadata.create_all()` in tests."""

from app.models.blockchain_hash import BlockchainHash
from app.models.buyer import Buyer
from app.models.dispute import Dispute, DisputeReason, DisputeStatus
from app.models.fraud_log import FraudLog
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.review import Review
from app.models.seller import Seller
from app.models.transaction import PaymentMethod, Transaction, TransactionStatus
from app.models.trust_score import TrustScore
from app.models.user import User, UserRole
from app.models.wishlist import Wishlist

__all__ = [
    "BlockchainHash",
    "Buyer",
    "Dispute",
    "DisputeReason",
    "DisputeStatus",
    "FraudLog",
    "Order",
    "OrderStatus",
    "Product",
    "Recommendation",
    "Review",
    "Seller",
    "Transaction",
    "PaymentMethod",
    "TransactionStatus",
    "TrustScore",
    "User",
    "UserRole",
    "Wishlist",
]
