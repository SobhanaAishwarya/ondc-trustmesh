"""Vendor Match Score — Module 2 (Intelligent Vendor Matching) from the
project brief.

`GET /products` (products.py) lists results newest-first with no ranking
at all — fine for browsing a catalog, useless for the actual question a
buyer has when 5 sellers list the identical product: "which one is
better?" This module answers that question with the brief's own worked
example formula (Seller A/B/C -> 91%/89%/76%, "Best Match: Seller C"):

    30% rating + 25% proximity/distance + 20% price + 15% delivery speed
    + 10% availability

Price and delivery are scored *relative to the other listings in this
comparison*, not against some fixed universal scale — "cheap" only means
something next to alternatives, which mirrors how a buyer actually reads
a search-results page (cheapest of these five, not cheapest possible
price in the abstract).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.geo import distance_between_cities, estimate_delivery_days
from app.models.buyer import Buyer
from app.models.product import Product
from app.models.review import Review
from app.models.seller import Seller

WEIGHTS = {"rating": 0.30, "proximity": 0.25, "price": 0.20, "delivery": 0.15, "availability": 0.10}

# Matches fraud_service._avg_seller_rating's cold-start assumption — a
# seller with zero reviews yet is scored as average, not penalized.
DEFAULT_RATING = 3.0
RATING_SCALE = 5.0

# Stock at/above this scores full marks on availability — a saturating
# score, not a hard cutoff, since "50 in stock" and "500 in stock" are
# both just "plenty" from a buyer's perspective.
AVAILABILITY_SATURATION_UNITS = 50

UNKNOWN_PROXIMITY_SCORE = 0.5
UNKNOWN_DELIVERY_SCORE = 0.5


@dataclass
class VendorMatch:
    product: Product
    seller: Seller | None
    rating: float
    distance_km: float | None
    estimated_delivery_days: int | None
    match_score: float
    is_best_match: bool


def compare_vendors(db: Session, buyer: Buyer, product_name: str) -> list[VendorMatch]:
    """Every active listing whose name matches `product_name` (case-
    insensitive, exact — same product, different seller), ranked by match
    score, highest first. Empty list if nothing matches, same "no
    exception for a normal empty result" convention as get_recommendations.
    """
    listings = db.scalars(
        select(Product).where(
            Product.is_active.is_(True), func.lower(Product.name) == product_name.strip().lower()
        )
    ).all()
    if not listings:
        return []

    seller_ids = {p.seller_id for p in listings}
    sellers = {s.id: s for s in db.scalars(select(Seller).where(Seller.id.in_(seller_ids))).all()}
    ratings = {seller_id: _avg_rating(db, seller_id) for seller_id in seller_ids}

    prices = [float(p.price) for p in listings]
    price_lo, price_hi = min(prices), max(prices)

    distances: dict[uuid.UUID, float | None] = {}
    delivery_days: dict[uuid.UUID, int | None] = {}
    for seller_id in seller_ids:
        seller = sellers.get(seller_id)
        distance_km = distance_between_cities(buyer.city, seller.city if seller else None)
        distances[seller_id] = distance_km
        delivery_days[seller_id] = estimate_delivery_days(distance_km) if distance_km is not None else None

    known_days = [d for d in delivery_days.values() if d is not None]
    days_lo, days_hi = (min(known_days), max(known_days)) if known_days else (None, None)

    matches = []
    for product in listings:
        seller = sellers.get(product.seller_id)
        rating = ratings.get(product.seller_id, DEFAULT_RATING)
        distance_km = distances.get(product.seller_id)
        days = delivery_days.get(product.seller_id)

        rating_score = rating / RATING_SCALE
        proximity_score = _proximity_score(distance_km, seller)
        price_score = _cheaper_or_faster_is_better(float(product.price), price_lo, price_hi)
        delivery_score = (
            _cheaper_or_faster_is_better(days, days_lo, days_hi)
            if days is not None and days_lo is not None
            else UNKNOWN_DELIVERY_SCORE
        )
        availability_score = min(product.stock_quantity / AVAILABILITY_SATURATION_UNITS, 1.0)

        score = (
            WEIGHTS["rating"] * rating_score
            + WEIGHTS["proximity"] * proximity_score
            + WEIGHTS["price"] * price_score
            + WEIGHTS["delivery"] * delivery_score
            + WEIGHTS["availability"] * availability_score
        )
        matches.append(
            VendorMatch(
                product=product,
                seller=seller,
                rating=rating,
                distance_km=distance_km,
                estimated_delivery_days=days,
                match_score=round(score, 4),
                is_best_match=False,
            )
        )

    matches.sort(key=lambda m: -m.match_score)
    matches[0].is_best_match = True
    return matches


def _cheaper_or_faster_is_better(value: float, lo: float, hi: float) -> float:
    """1.0 for the lowest value in the comparison set, 0.0 for the
    highest, linear in between. Used for both price and delivery days —
    lower is better for both. All-equal collapses to 1.0 for everyone
    (no listing is actually worse on this axis than another)."""
    if hi == lo:
        return 1.0
    return 1.0 - (value - lo) / (hi - lo)


def _proximity_score(distance_km: float | None, seller: Seller | None) -> float:
    if distance_km is None:
        return UNKNOWN_PROXIMITY_SCORE
    radius = max(seller.delivery_radius_km, 1) if seller else 50
    return 1.0 / (1.0 + distance_km / radius)


def _avg_rating(db: Session, seller_id: uuid.UUID) -> float:
    avg = db.scalar(select(func.avg(Review.rating)).where(Review.seller_id == seller_id))
    return float(avg) if avg is not None else DEFAULT_RATING
