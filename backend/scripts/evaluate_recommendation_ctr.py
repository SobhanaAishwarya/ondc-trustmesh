"""Synthetic CTR backtest for the recommendation engine.

The Infosys brief targets a ~20% CTR improvement from personalized
recommendations. `GET /recommendations/ctr` (app/services/recommendation_
service.py:compute_ctr) measures this correctly from real logged
impressions/clicks — but as of writing, the deployed app has near-zero real
buyer traffic, so that endpoint reads ~0. Rather than leave the KPI
completely unverified, or manufacture fake clicks against the live
production system (which would misrepresent synthetic activity as real user
behavior — the exact problem this project's audit flagged elsewhere), this
runs the same kind of honest, clearly-labeled synthetic evaluation already
used for the fraud model (see app/ml/synthetic_data.py): a realistic-shaped
synthetic catalog, synthetic buyers, a simulated click model, and both arms
run through the *actual* deployed ranking code — not a reimplementation of
it.

This is fully self-contained (own in-memory SQLite DB, own seeded catalog)
so it needs no live Postgres/Neon connection and is reproducible on a fresh
checkout, the same way `scripts/train_fraud_model.py` is.

Two arms, same candidate pool, same buyers, same click model:
  BASELINE — `GET /products` default ordering (created_at desc), i.e. what a
              buyer sees today with no personalization at all.
  HYBRID   — `recommendation_service.get_recommendations()`, the real,
              deployed function — content (TF-IDF/cosine) + trust +
              popularity + proximity. Collaborative filtering does not
              engage here (synthetic buyers have no order history, same as
              any real first-time buyer), so this specifically measures the
              content/trust/popularity/proximity blend against an
              unpersonalized feed.

Click model: a buyer clicks a shown item with probability that decays by
on-screen rank position and is boosted when the item's category matches the
buyer's stated preference — a standard, explainable position-bias +
topical-relevance model, not tuned to hit any target number. Whatever lift
comes out is reported as-is.

This is a simulation over a synthetic catalog, not live user telemetry — do
not present its output as production analytics. It answers a narrower,
honest question: "does personalizing by stated category preference beat an
unpersonalized feed, using this project's actual ranking code?"

Usage:
    python scripts/evaluate_recommendation_ctr.py [--buyers-per-category 40] [--top-k 10] [--seed 42]
"""

import argparse
import sys
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.geo import CITY_NAMES
from app.db.base import Base
from app.models.product import Product
from app.models.seller import Seller
from app.models.user import User, UserRole
from app.services.recommendation_service import get_recommendations

# Rank-position click-through decay — attention drops off the further down
# the list an item sits, independent of relevance.
POSITION_DECAY = 0.75
CLICK_PROB_RELEVANT = 0.42
CLICK_PROB_IRRELEVANT = 0.06

# Same category set as the deployed catalog / app/ml/synthetic_data.py.
CATALOG: dict[str, list[str]] = {
    "Grocery": [
        "Organic Basmati Rice 5kg", "Whole Wheat Atta 5kg", "Cold Pressed Coconut Oil 1L",
        "Assorted Dry Fruits Pack", "Honey Pure 500g", "Rock Salt 1kg", "Masala Chai Powder",
        "Cornflakes 500g", "Toor Dal 1kg", "Mustard Oil 1L", "Brown Sugar 1kg", "Poha Flattened Rice 1kg",
    ],
    "Electronics": [
        "Wireless Earbuds Pro", "Smart Fitness Band", "USB-C Fast Charger 65W", "Portable SSD 1TB",
        "Webcam Full HD", "Smartphone Stand", "Screen Protector Pack", "Bluetooth Speaker",
        "Wireless Mouse", "Power Bank 20000mAh", "HDMI Cable 2m", "Smartwatch Series",
    ],
    "Fashion": [
        "Cotton Kurta Set", "Denim Jacket", "Running Shoes", "Women's Saree Silk",
        "Laptop Backpack 15.6 inch", "Leather Belt", "Formal Shirt Cotton", "Sports Sneakers",
        "Woolen Scarf", "Sunglasses UV Protection", "Analog Wrist Watch", "Canvas Tote Bag",
    ],
    "Home & Kitchen": [
        "Non-Stick Cookware Set", "Memory Foam Pillow", "LED Desk Lamp", "Ceramic Dinner Set",
        "Ceiling Fan 1200mm", "Blender Mixer Grinder", "Storage Containers Set", "Doormat",
        "Wall Clock Wooden", "Water Bottle Steel", "Curtains Set", "Study Table Foldable",
    ],
    "Beauty": [
        "Matte Lipstick", "Face Wash Neem", "Sunscreen SPF50", "Herbal Shampoo", "Body Lotion",
        "Nail Polish Set", "Perfume Eau de Parfum", "Face Moisturizer Cream", "Hair Oil Almond",
        "Kajal Eyeliner", "Deodorant Spray", "Lip Balm Pack",
    ],
    "Pharmacy": [
        "Digital Thermometer", "Digital Weighing Scale", "Glucometer Kit", "N95 Face Masks Pack",
        "Antiseptic Liquid", "Cough Syrup", "Whey Protein Powder", "Multivitamin Tablets",
        "First Aid Kit", "Blood Pressure Monitor", "Hand Sanitizer 500ml", "Pain Relief Spray",
    ],
    "Food & Beverage": [
        "Green Tea 100 Bags", "Instant Noodles Pack", "Popcorn Butter", "Granola Bars Pack",
        "Namkeen Mixture", "Cookies Pack", "Protein Bar", "Soft Drink 2L", "Energy Drink Can",
        "Herbal Tea Box", "Roasted Almonds Pack", "Dark Chocolate Bar",
    ],
    "Books": [
        "Atomic Habits", "Sapiens", "Rich Dad Poor Dad", "Clean Code",
        "Database System Concepts", "Operating System Concepts", "The Alchemist", "Wings of Fire",
        "Introduction to Algorithms", "Think and Grow Rich", "Ikigai", "Ignited Minds",
    ],
}

SELLERS_PER_CATEGORY = 2


def _seed_catalog(db: Session, rng: np.random.Generator) -> None:
    for category, product_names in CATALOG.items():
        sellers = []
        for s in range(SELLERS_PER_CATEGORY):
            user = User(
                id=uuid.uuid4(),
                email=f"{category.lower().replace(' & ', '-').replace(' ', '-')}-seller{s}@backtest.local",
                password_hash="not-used-in-backtest",
                full_name=f"{category} Seller {s}",
                role=UserRole.seller,
                is_verified=True,
            )
            seller = Seller(
                id=uuid.uuid4(),
                user_id=user.id,
                business_name=f"{category} Store {s}",
                city=str(rng.choice(CITY_NAMES)),
                delivery_radius_km=int(rng.integers(30, 300)),
                current_trust_score=Decimal(str(round(float(rng.uniform(40, 95)), 2))),
            )
            db.add(user)
            db.add(seller)
            sellers.append(seller)

        for i, name in enumerate(product_names):
            seller = sellers[i % len(sellers)]
            db.add(
                Product(
                    id=uuid.uuid4(),
                    seller_id=seller.id,
                    name=name,
                    description=f"{name} — {category} item for the CTR backtest catalog.",
                    category=category,
                    tags=[category.lower(), *name.lower().split()[:2]],
                    price=Decimal(str(round(float(rng.uniform(99, 4999)), 2))),
                    stock_quantity=int(rng.integers(5, 200)),
                    is_active=True,
                )
            )
    db.commit()


def _synthetic_buyer(category: str, rng: np.random.Generator):
    from app.models.buyer import Buyer

    return Buyer(
        id=uuid.uuid4(),
        preferred_categories=[category],
        city=str(rng.choice(CITY_NAMES)),
        price_sensitivity=Decimal("0.50"),
        account_age_days=0,
    )


def _baseline_ranking(db: Session, top_k: int) -> list[Product]:
    return list(
        db.scalars(
            select(Product).where(Product.is_active.is_(True)).order_by(Product.created_at.desc()).limit(top_k)
        ).all()
    )


def _simulate_clicks(items: list[Product], true_category: str, rng: np.random.Generator) -> int:
    clicks = 0
    for position, product in enumerate(items):
        position_weight = POSITION_DECAY**position
        base_rate = CLICK_PROB_RELEVANT if product.category == true_category else CLICK_PROB_IRRELEVANT
        if rng.random() < base_rate * position_weight:
            clicks += 1
    return clicks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--buyers-per-category", type=int, default=40)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = Session(engine)

    try:
        _seed_catalog(db, rng)
        categories = sorted(CATALOG)
        n_products = db.scalar(select(func.count()).select_from(Product)) or 0

        print(f"Synthetic catalog: {n_products} products across {len(categories)} categories, "
              f"{SELLERS_PER_CATEGORY} sellers/category")
        print(f"Synthetic buyers: {args.buyers_per_category} per category ({args.buyers_per_category * len(categories)} total)")
        print(f"top_k: {args.top_k}, seed: {args.seed}\n")

        baseline_impressions = baseline_clicks = 0
        hybrid_impressions = hybrid_clicks = 0

        for category in categories:
            for _ in range(args.buyers_per_category):
                buyer = _synthetic_buyer(category, rng)

                baseline_items = _baseline_ranking(db, args.top_k)
                baseline_impressions += len(baseline_items)
                baseline_clicks += _simulate_clicks(baseline_items, category, rng)

                hybrid_scored = get_recommendations(db, buyer, top_k=args.top_k)
                hybrid_items = [s.product for s in hybrid_scored]
                hybrid_impressions += len(hybrid_items)
                hybrid_clicks += _simulate_clicks(hybrid_items, category, rng)

        baseline_ctr = baseline_clicks / baseline_impressions if baseline_impressions else 0.0
        hybrid_ctr = hybrid_clicks / hybrid_impressions if hybrid_impressions else 0.0
        lift = (hybrid_ctr - baseline_ctr) / baseline_ctr if baseline_ctr else float("nan")

        print("--- Results (synthetic backtest, not live telemetry) ---")
        print(f"  baseline (unpersonalized, created_at desc): {baseline_clicks}/{baseline_impressions} = {baseline_ctr:.4f} CTR")
        print(f"  hybrid   (real recommendation_service):     {hybrid_clicks}/{hybrid_impressions} = {hybrid_ctr:.4f} CTR")
        print(f"  relative lift: {lift:+.2%}")
        print(f"\nInfosys KPI target (~20% CTR improvement): {'MEETS' if lift >= 0.20 else 'BELOW'} ({lift:+.2%})")
        print(
            "\nCaveat: the baseline is the literal current unpersonalized experience — the exact\n"
            "same newest-first top_k shown to every buyer regardless of stated interest, not a\n"
            "competitive ranking baseline (e.g. popularity-only). A large lift here mostly reflects\n"
            "how weak that static status quo is, not a claim that this recommender beats a strong\n"
            "alternative. Report the lift number honestly with this framing attached, not standalone."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
