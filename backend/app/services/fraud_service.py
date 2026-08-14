"""Scores a freshly-created transaction for fraud and records the result.

Called synchronously from `POST /orders` right after the Transaction is
created (see api/v1/endpoints/orders.py) — for the transaction volumes a
final-year project deals with, an in-process RandomForest predict_proba
call is low-single-digit milliseconds, so there's no need for a queue/async
worker here. Revisit if this ever needs to scale past a demo.
"""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ml.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, TransactionContext, compute_live_features
from app.ml.model import MODEL_NAME, MODEL_VERSION, TrainedFraudModel, get_fraud_model
from app.models.buyer import Buyer
from app.models.fraud_log import FraudLog
from app.models.product import Product
from app.models.seller import Seller
from app.models.transaction import Transaction
from app.services.blockchain_service import record_trust_event

RISK_FACTOR_TOP_N = 3
CATEGORICAL_CONTRIBUTION_WEIGHT = 0.5  # categoricals have no z-score; de-weighted vs. numeric deviations


def score_transaction(
    db: Session, transaction: Transaction, buyer: Buyer, seller: Seller, product: Product
) -> FraudLog:
    """Computes a fraud probability, writes it onto the transaction, and
    returns a FraudLog row (added to `db` but not committed — the caller
    owns the transaction boundary, same as the rest of orders.py)."""
    settings = get_settings()
    model = get_fraud_model()

    ctx = TransactionContext(
        amount=transaction.amount,
        payment_method=transaction.payment_method.value,
        category=product.category,
        buyer_id=buyer.id,
        seller_id=seller.id,
        buyer_account_age_days=buyer.account_age_days,
        seller_trust_score=seller.current_trust_score,
        seller_age_days=seller.seller_age_days,
    )
    features = compute_live_features(db, ctx)
    probability = round(model.predict_proba(features), 4)
    is_flagged = probability >= settings.fraud_flag_threshold

    transaction.fraud_probability = probability
    transaction.is_fraud_flagged = is_flagged

    fraud_log = FraudLog(
        transaction_id=transaction.id,
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        fraud_probability=probability,
        is_flagged=is_flagged,
        risk_factors=_top_risk_factors(model, features),
    )
    db.add(fraud_log)

    if is_flagged:
        record_trust_event(db, seller, "fraud_flagged")  # no-op if chain isn't enabled/reachable

    return fraud_log


def _top_risk_factors(model: TrainedFraudModel, features: dict) -> dict:
    """Lightweight, dependency-free explainability: ranks features by
    (global importance x how far this instance deviates from the training
    mean), not a proper Shapley-value decomposition — good enough to show
    "why was this flagged" without pulling in SHAP for a demo-scale model."""
    scores: dict[str, float] = {}
    for name in NUMERIC_FEATURES:
        mean = model.feature_means.get(name, 0.0)
        std = model.feature_stds.get(name, 1.0) or 1.0
        z = abs((features[name] - mean) / std)
        scores[name] = round(z * model.feature_importances.get(name, 0.0), 4)
    for name in CATEGORICAL_FEATURES:
        scores[name] = round(model.feature_importances.get(name, 0.0) * CATEGORICAL_CONTRIBUTION_WEIGHT, 4)

    ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:RISK_FACTOR_TOP_N]
    return {name: {"value": features[name], "contribution_score": score} for name, score in ranked}
