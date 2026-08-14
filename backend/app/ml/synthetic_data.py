"""Synthetic fraud-model training data.

No real ONDC transaction/fraud dataset exists (same situation as the
Streamlit prototype — see its README), so this generates labeled
transactions with a designed signal over exactly the columns in
features.py, so the trained model's input contract matches live scoring
exactly. See features.py's docstring for why this column set differs from
the prototype's `ml/data.py`.
"""

import numpy as np
import pandas as pd

from app.ml.features import ALL_FEATURES

CATEGORIES = [
    "Grocery", "Electronics", "Fashion", "Home & Kitchen",
    "Beauty", "Pharmacy", "Food & Beverage", "Books",
]
PAYMENT_METHODS = ["upi", "card", "cod", "wallet"]


def generate_synthetic_transactions(n: int = 6000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    seller_trust = rng.beta(5, 2, n) * 100
    is_new_seller = (rng.random(n) < 0.15).astype(float)
    seller_trust = np.where(is_new_seller.astype(bool), rng.uniform(20, 55, n), seller_trust)

    transaction_amount = rng.gamma(shape=2.0, scale=450, size=n) + 50
    buyer_account_age_days = rng.exponential(200, n).clip(1, 2500)
    num_previous_disputes = rng.poisson(0.3, n).astype(float)
    velocity_1h = rng.poisson(1.2, n).astype(float)
    payment_method = rng.choice(PAYMENT_METHODS, n, p=[0.45, 0.25, 0.2, 0.1])
    category = rng.choice(CATEGORIES, n)
    seller_rating = (seller_trust / 20 + rng.normal(0, 0.3, n)).clip(1, 5)

    # Designed signal: new/low-trust sellers, dispute history, high velocity,
    # COD, large amounts, and thin buyer history all push fraud likelihood up;
    # seller rating and buyer tenure pull it down. Matches the reasoning in
    # the Streamlit prototype's ml/data.py, minus the two features
    # (delivery_time_hours, distance_km) that aren't available at scoring time.
    fraud_score = (
        -0.05 * seller_trust
        + 0.015 * transaction_amount / 100
        + 2.2 * is_new_seller
        + 0.7 * num_previous_disputes
        + 0.9 * velocity_1h
        + 1.1 * (payment_method == "cod")
        + 0.6 * (transaction_amount > 3000)
        - 0.01 * buyer_account_age_days / 10
        - 0.15 * seller_rating
        + rng.normal(0, 1.4, n)
    )
    threshold = np.quantile(fraud_score, 0.92)
    is_fraud = (fraud_score > threshold).astype(int)

    df = pd.DataFrame(
        {
            "transaction_amount": transaction_amount.round(2),
            "buyer_account_age_days": buyer_account_age_days.round(0),
            "seller_trust_score": seller_trust.round(2),
            "num_previous_disputes": num_previous_disputes,
            "velocity_1h": velocity_1h,
            "seller_rating": seller_rating.round(2),
            "is_new_seller": is_new_seller,
            "payment_method": payment_method,
            "category": category,
            "is_fraud": is_fraud,
        }
    )
    return df[ALL_FEATURES + ["is_fraud"]]
