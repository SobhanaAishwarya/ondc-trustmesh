"""Synthetic ONDC-style datasets.

No public ONDC transaction/fraud dataset exists, so this module generates
realistic-but-synthetic data with a designed signal (seller trust, dispute
history, velocity, payment method, etc. drive fraud likelihood) so the
fraud model and recommender have something meaningful to learn from. Swap
these generators for real ONDC network data when it's available.
"""

import numpy as np
import pandas as pd

CATEGORIES = [
    "Grocery", "Electronics", "Fashion", "Home & Kitchen",
    "Beauty", "Pharmacy", "Food & Beverage", "Books",
]
PAYMENT_METHODS = ["UPI", "Card", "COD", "Wallet"]


def generate_transactions(n=6000, seed=42):
    """Synthetic buyer-seller transactions with an engineered fraud label."""
    rng = np.random.default_rng(seed)

    seller_trust = rng.beta(5, 2, n) * 100
    is_new_seller = rng.random(n) < 0.15
    seller_trust = np.where(is_new_seller, rng.uniform(20, 55, n), seller_trust)

    amount = rng.gamma(shape=2.0, scale=450, size=n) + 50
    buyer_account_age_days = rng.exponential(200, n).clip(1, 2500)
    delivery_time_hours = rng.gamma(2.0, 10, n)
    num_previous_disputes = rng.poisson(0.3, n)
    velocity_1h = rng.poisson(1.2, n)
    payment_method = rng.choice(PAYMENT_METHODS, n, p=[0.45, 0.25, 0.2, 0.1])
    category = rng.choice(CATEGORIES, n)
    distance_km = rng.gamma(2.0, 8, n)
    seller_rating = (seller_trust / 20 + rng.normal(0, 0.3, n)).clip(1, 5)

    fraud_score = (
        -0.05 * seller_trust
        + 0.015 * amount / 100
        + 2.2 * is_new_seller
        + 0.7 * num_previous_disputes
        + 0.9 * velocity_1h
        + 0.02 * delivery_time_hours
        + 1.1 * (payment_method == "COD")
        + 0.6 * (amount > 3000)
        - 0.01 * buyer_account_age_days / 10
        + rng.normal(0, 1.4, n)
    )
    threshold = np.quantile(fraud_score, 0.92)
    is_fraud = (fraud_score > threshold).astype(int)

    return pd.DataFrame(
        {
            "transaction_amount": amount.round(2),
            "buyer_account_age_days": buyer_account_age_days.round(0),
            "seller_trust_score": seller_trust.round(2),
            "delivery_time_hours": delivery_time_hours.round(2),
            "num_previous_disputes": num_previous_disputes,
            "velocity_1h": velocity_1h,
            "payment_method": payment_method,
            "category": category,
            "distance_km": distance_km.round(2),
            "seller_rating": seller_rating.round(2),
            "is_new_seller": is_new_seller.astype(int),
            "is_fraud": is_fraud,
        }
    )


def generate_catalog(n_products=300, n_sellers=60, seed=7):
    """Synthetic product/service catalog spread across sellers of varying trust."""
    rng = np.random.default_rng(seed)
    seller_ids = [f"SLR-{i:03d}" for i in range(n_sellers)]
    seller_trust = dict(zip(seller_ids, rng.beta(5, 2, n_sellers) * 100))

    rows = []
    for i in range(n_products):
        category = rng.choice(CATEGORIES)
        seller = rng.choice(seller_ids)
        price = float(rng.gamma(2.0, 300))
        rows.append(
            {
                "product_id": f"PRD-{i:04d}",
                "category": category,
                "price": round(price, 2),
                "seller_id": seller,
                "seller_trust_score": round(seller_trust[seller], 2),
                "tags": category.lower().replace(" & ", " "),
            }
        )
    return pd.DataFrame(rows)


def generate_buyers(n_buyers=200, seed=11):
    """Synthetic buyer profiles with latent category preferences."""
    rng = np.random.default_rng(seed)
    buyers = []
    for i in range(n_buyers):
        preferred = rng.choice(CATEGORIES, size=int(rng.integers(1, 3)), replace=False)
        buyers.append(
            {
                "buyer_id": f"BYR-{i:04d}",
                "preferred_categories": list(preferred),
                "price_sensitivity": round(float(rng.uniform(0.3, 1.0)), 2),
            }
        )
    return buyers
