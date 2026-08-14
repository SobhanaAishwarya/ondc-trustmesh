"""Content-based product/service matching for ONDC buyers, blended with
on-chain seller trust score. Includes a simulated CTR backtest comparing
the recommender against a random-baseline placement strategy."""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def recommend_for_buyer(catalog, buyer, top_k=5):
    query = " ".join(buyer["preferred_categories"]).lower()
    corpus = (catalog["category"] + " " + catalog["tags"]).tolist()

    vectorizer = TfidfVectorizer()
    vectorizer.fit(corpus + [query])
    item_vecs = vectorizer.transform(corpus)
    query_vec = vectorizer.transform([query])
    similarity = cosine_similarity(query_vec, item_vecs)[0]

    trust_boost = catalog["seller_trust_score"].to_numpy() / 100
    price_penalty = 1 - buyer["price_sensitivity"] * (
        catalog["price"].to_numpy() / catalog["price"].max()
    )
    match_score = 0.6 * similarity + 0.25 * trust_boost + 0.15 * price_penalty

    ranked = catalog.assign(match_score=match_score).sort_values(
        "match_score", ascending=False
    )
    return ranked.head(top_k)


def _click_probability(buyer, product):
    base = 0.04
    category_match = product["category"] in buyer["preferred_categories"]
    trust = product["seller_trust_score"] / 100
    p = base + (0.28 if category_match else 0) + 0.15 * trust
    return float(np.clip(p, 0, 0.9))


def simulate_ctr(catalog, buyers, top_k=5, seed=99):
    """Backtest: for each buyer, compare click-through on a random impression
    set vs. the recommender's ranked impression set, using a synthetic
    click-probability model driven by category match + seller trust."""
    rng = np.random.default_rng(seed)

    random_clicks = random_impressions = 0
    reco_clicks = reco_impressions = 0

    for buyer in buyers:
        random_items = catalog.sample(top_k, random_state=int(rng.integers(0, 1_000_000)))
        for _, item in random_items.iterrows():
            random_impressions += 1
            if rng.random() < _click_probability(buyer, item):
                random_clicks += 1

        reco_items = recommend_for_buyer(catalog, buyer, top_k=top_k)
        for _, item in reco_items.iterrows():
            reco_impressions += 1
            if rng.random() < _click_probability(buyer, item):
                reco_clicks += 1

    random_ctr = random_clicks / random_impressions
    reco_ctr = reco_clicks / reco_impressions
    lift_pct = (reco_ctr - random_ctr) / random_ctr * 100 if random_ctr > 0 else 0.0

    return {
        "random_ctr": random_ctr,
        "reco_ctr": reco_ctr,
        "lift_pct": lift_pct,
        "random_clicks": random_clicks,
        "random_impressions": random_impressions,
        "reco_clicks": reco_clicks,
        "reco_impressions": reco_impressions,
    }
