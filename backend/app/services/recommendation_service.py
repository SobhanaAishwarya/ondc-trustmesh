"""Recommendation engine: content-based (TF-IDF + cosine similarity over
category/tags/name against a buyer profile), item-based collaborative
filtering (co-purchase counts — "buyers who bought X also bought Y"), a
seller-trust blend, a proximity/vendor-matchmaking signal (city-level
distance weighed against the seller's delivery radius), and a
popularity-based cold-start fallback when a buyer has neither stated
preferences nor purchase history.

`preferred_categories` (buyer-declared) and past-purchase categories both
feed the content query — engineered/count-based "user embeddings" in the
sense the project brief means: a vector representation of buyer interest,
not a learned neural embedding, which isn't warranted at this data volume.

The proximity term implements the reference paper's "vendor matchmaking"
idea (location + delivery capability alongside reviews/trust) without
needing real GPS coordinates — see app.core.geo for the city-distance
model this is built on.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.geo import distance_between_cities, estimate_delivery_days
from app.models.buyer import Buyer
from app.models.order import Order
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.seller import Seller

HYBRID_WEIGHTS = {"content": 0.35, "collaborative": 0.25, "trust": 0.15, "popularity": 0.10, "proximity": 0.15}
COLD_START_WEIGHTS = {"popularity": 0.5, "trust": 0.25, "proximity": 0.25}
ALGORITHM_HYBRID = "hybrid"
ALGORITHM_COLD_START = "popularity_cold_start"

# Neutral score used when either party's city is unknown — proximity
# should be uninformative, not a penalty, for buyers/sellers who haven't
# set a location.
UNKNOWN_PROXIMITY_SCORE = 0.5


@dataclass
class ScoredProduct:
    product: Product
    score: float
    algorithm: str
    distance_km: float | None = None
    estimated_delivery_days: int | None = None


def get_recommendations(db: Session, buyer: Buyer, top_k: int = 10) -> list[ScoredProduct]:
    products = db.scalars(select(Product).where(Product.is_active.is_(True))).all()
    if not products:
        return []

    purchased_categories = _purchased_categories(db, buyer.id)
    query_categories = list(buyer.preferred_categories) + purchased_categories

    content = _content_scores(products, query_categories)
    collaborative = _collaborative_scores(db, buyer.id, products)
    popularity = _popularity_scores(db, products)
    trust = _trust_scores(db, products)
    sellers = _sellers_by_id(db, products)
    proximity, distances = _proximity_scores(buyer, products, sellers)

    is_cold_start = not query_categories and not collaborative
    scored: list[ScoredProduct] = []
    for product in products:
        p_trust = trust.get(product.seller_id, 0.5)
        p_proximity = proximity.get(product.seller_id, UNKNOWN_PROXIMITY_SCORE)
        if is_cold_start:
            score = (
                COLD_START_WEIGHTS["popularity"] * popularity.get(product.id, 0.0)
                + COLD_START_WEIGHTS["trust"] * p_trust
                + COLD_START_WEIGHTS["proximity"] * p_proximity
            )
            algorithm = ALGORITHM_COLD_START
        else:
            score = (
                HYBRID_WEIGHTS["content"] * content.get(product.id, 0.0)
                + HYBRID_WEIGHTS["collaborative"] * collaborative.get(product.id, 0.0)
                + HYBRID_WEIGHTS["trust"] * p_trust
                + HYBRID_WEIGHTS["popularity"] * popularity.get(product.id, 0.0)
                + HYBRID_WEIGHTS["proximity"] * p_proximity
            )
            algorithm = ALGORITHM_HYBRID
        distance_km = distances.get(product.seller_id)
        scored.append(
            ScoredProduct(
                product=product,
                score=round(score, 5),
                algorithm=algorithm,
                distance_km=distance_km,
                estimated_delivery_days=estimate_delivery_days(distance_km) if distance_km is not None else None,
            )
        )

    scored.sort(key=lambda s: -s.score)
    return scored[:top_k]


def record_impressions(db: Session, buyer: Buyer, scored: list[ScoredProduct]) -> list[Recommendation]:
    records = []
    for rank, item in enumerate(scored, start=1):
        rec = Recommendation(
            buyer_id=buyer.id,
            product_id=item.product.id,
            algorithm=item.algorithm,
            score=Decimal(str(min(max(item.score, 0.0), 1.0))),
            rank=rank,
        )
        db.add(rec)
        records.append(rec)
    return records


def mark_purchased_if_recommended(db: Session, buyer_id: uuid.UUID, product_id: uuid.UUID) -> None:
    """Attribution hook called from POST /orders — if this product was
    recently recommended to this buyer and not yet marked, mark it
    purchased so CTR-to-conversion numbers reflect real outcomes."""
    rec = db.scalar(
        select(Recommendation)
        .where(
            Recommendation.buyer_id == buyer_id,
            Recommendation.product_id == product_id,
            Recommendation.was_purchased.is_(False),
        )
        .order_by(Recommendation.shown_at.desc())
    )
    if rec is not None:
        rec.was_purchased = True


def compute_ctr(db: Session, algorithm: str | None = None) -> dict:
    conditions = [Recommendation.algorithm == algorithm] if algorithm else []

    impressions = db.scalar(select(func.count()).select_from(Recommendation).where(*conditions)) or 0
    clicks = db.scalar(
        select(func.count()).select_from(Recommendation).where(*conditions, Recommendation.was_clicked.is_(True))
    ) or 0
    purchases = db.scalar(
        select(func.count()).select_from(Recommendation).where(*conditions, Recommendation.was_purchased.is_(True))
    ) or 0

    return {
        "algorithm": algorithm,
        "impressions": impressions,
        "clicks": clicks,
        "purchases": purchases,
        "ctr": round(clicks / impressions, 4) if impressions else 0.0,
        "click_to_purchase_rate": round(purchases / clicks, 4) if clicks else 0.0,
    }


def _content_scores(products: list[Product], query_categories: list[str]) -> dict:
    query = " ".join(query_categories).lower().strip()
    if not query:
        return {}

    corpus = [f"{p.category} {' '.join(p.tags)} {p.name}".lower() for p in products]
    vectorizer = TfidfVectorizer()
    vectorizer.fit(corpus + [query])
    item_vectors = vectorizer.transform(corpus)
    query_vector = vectorizer.transform([query])
    similarities = cosine_similarity(query_vector, item_vectors)[0]
    return {p.id: float(s) for p, s in zip(products, similarities)}


def _collaborative_scores(db: Session, buyer_id: uuid.UUID, products: list[Product]) -> dict:
    purchased_ids = set(db.scalars(select(Order.product_id).where(Order.buyer_id == buyer_id)).all())
    if not purchased_ids:
        return {}

    co_buyer_ids = set(
        db.scalars(
            select(Order.buyer_id).where(Order.product_id.in_(purchased_ids), Order.buyer_id != buyer_id).distinct()
        ).all()
    )
    if not co_buyer_ids:
        return {}

    rows = db.execute(
        select(Order.product_id, func.count().label("cnt"))
        .where(Order.buyer_id.in_(co_buyer_ids), Order.product_id.notin_(purchased_ids))
        .group_by(Order.product_id)
    ).all()
    if not rows:
        return {}

    max_count = max(cnt for _, cnt in rows)
    return {product_id: cnt / max_count for product_id, cnt in rows}


def _popularity_scores(db: Session, products: list[Product]) -> dict:
    rows = db.execute(select(Order.product_id, func.count().label("cnt")).group_by(Order.product_id)).all()
    counts = dict(rows)
    if not counts:
        return {p.id: 0.0 for p in products}
    max_count = max(counts.values())
    return {p.id: counts.get(p.id, 0) / max_count for p in products}


def _trust_scores(db: Session, products: list[Product]) -> dict:
    seller_ids = {p.seller_id for p in products}
    sellers = db.scalars(select(Seller).where(Seller.id.in_(seller_ids))).all()
    return {s.id: float(s.current_trust_score) / 100 for s in sellers}


def _sellers_by_id(db: Session, products: list[Product]) -> dict[uuid.UUID, Seller]:
    seller_ids = {p.seller_id for p in products}
    sellers = db.scalars(select(Seller).where(Seller.id.in_(seller_ids))).all()
    return {s.id: s for s in sellers}


def _proximity_scores(
    buyer: Buyer, products: list[Product], sellers: dict[uuid.UUID, Seller]
) -> tuple[dict[uuid.UUID, float], dict[uuid.UUID, float | None]]:
    """Closer, faster-shipping sellers score higher. `1 / (1 + distance /
    delivery_radius)` decays smoothly rather than hard-cutting sellers
    outside their stated radius — a seller can still ship further, just
    less competitively. Unknown city on either side is neutral, not a
    penalty, so buyers/sellers who haven't set a location aren't punished.
    """
    scores: dict[uuid.UUID, float] = {}
    distances: dict[uuid.UUID, float | None] = {}
    for seller_id in {p.seller_id for p in products}:
        seller = sellers.get(seller_id)
        distance_km = distance_between_cities(buyer.city, seller.city if seller else None)
        distances[seller_id] = distance_km
        if distance_km is None:
            scores[seller_id] = UNKNOWN_PROXIMITY_SCORE
        else:
            radius = max(seller.delivery_radius_km, 1) if seller else 50
            scores[seller_id] = 1.0 / (1.0 + distance_km / radius)
    return scores, distances


def _purchased_categories(db: Session, buyer_id: uuid.UUID) -> list[str]:
    rows = db.scalars(
        select(Product.category).join(Order, Order.product_id == Product.id).where(Order.buyer_id == buyer_id)
    ).all()
    return list(rows)
