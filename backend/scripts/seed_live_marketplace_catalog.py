"""Seeds a realistic multi-seller catalog against the live deployed backend:
the same ~15 well-known product types, each listed by every one of ~5
distinct demo sellers at a different price, in a different city, with a
different delivery radius — so Module 2 (vendor matching) has something
real to compare instead of one seller's single listing per product.

Why this exists instead of scraping Amazon/Flipkart/Meesho/Nykaa: doing
that would violate their Terms of Service, break unpredictably (anti-bot
protection), and run against ONDC's own premise of an open network sellers
join voluntarily rather than one app unilaterally pulling data from closed
competitor platforms. Product names/specs here are public facts (not
copyrightable); images are freely-licensed Wikipedia/Wikimedia Commons
photos (stable URLs, explicitly reusable, unlike hotlinking a competitor's
product photography) — see PRODUCT_TEMPLATES below for exactly which
article each image comes from.

Every seller this script creates is named `... (Demo)` and every product
tagged `demo-catalog` so it's obviously seeded data to anyone who looks,
not disguised as an organic listing.

Usage:
    python scripts/seed_live_marketplace_catalog.py [--base-url URL]

Rate-limit note: seller registration is capped at 10/hour per IP
(independent of the buyer-registration cap) — this script registers 5,
safe on its own, but don't run it more than once per hour from the same
machine without checking how much of that budget other scripts (e.g.
seed_live_ctr_demo.py) already used.
"""

import argparse
import random
import sys
import uuid

import requests

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

DEFAULT_BASE_URL = "https://ondc-backend-5kxh.onrender.com"
RUN_ID = uuid.uuid4().hex[:8]
REQUEST_TIMEOUT_S = 60

# (business_name, city, delivery_radius_km, price_multiplier)
# Multiplier gives each seller a consistent "market position" across every
# product, the way real marketplaces do (one is reliably cheaper, one is
# reliably wider-reaching/slower, etc.) rather than random noise per item.
SELLERS = [
    ("UrbanCart", "Mumbai", 100, 1.00),
    ("TrendNest", "Bengaluru", 300, 1.12),
    ("ValueBazaar", "Delhi", 500, 0.85),
    ("QuickMart Express", "Chennai", 150, 1.05),
    ("PrimeStyle Retail", "Hyderabad", 1000, 0.95),
]

# (name, category, base_price_inr, tags, image_url)
# Image URLs are Wikipedia/Wikimedia Commons thumbnails (CC-licensed,
# stable, explicitly reusable) fetched via the public REST summary API for
# the named article — swap the article name if a better photo is found
# later, but keep the source freely-licensed.
PRODUCT_TEMPLATES = [
    ("Running Shoes", "fashion", 3299, ["shoes", "sports"],
     "https://upload.wikimedia.org/wikipedia/commons/5/59/Air_Jordan_1_Banned.jpg"),
    ("Wireless Earbuds", "electronics", 1999, ["audio", "wireless"],
     "https://upload.wikimedia.org/wikipedia/commons/0/00/S%C5%82uchawki_referencyjne_K-701_firmy_AKG.jpg"),
    ("Smartwatch", "electronics", 4499, ["wearable", "fitness"],
     "https://upload.wikimedia.org/wikipedia/commons/b/b8/Samsung_Galaxy_Watch.jpg"),
    ("Men's Cotton Kurta", "fashion", 1299, ["ethnic", "cotton"],
     "https://upload.wikimedia.org/wikipedia/commons/3/31/Kurta_traditional_front_sandalwood_buttons.jpg"),
    ("Matte Lipstick", "beauty", 599, ["makeup", "cosmetics"],
     "https://upload.wikimedia.org/wikipedia/commons/3/3e/Applying_red_lipstick_-_model_Eve_Casini.jpg"),
    ("Sunscreen SPF 50", "beauty", 449, ["skincare", "spf"],
     "https://upload.wikimedia.org/wikipedia/commons/6/60/Sunscreen_on_back_under_normal_and_UV_light.jpg"),
    ("Yoga Mat", "sports", 799, ["fitness", "yoga"],
     "https://upload.wikimedia.org/wikipedia/commons/0/06/Ardha-Nav%C4%81sana.JPG"),
    ("Non-Stick Frying Pan", "home", 899, ["kitchen", "cookware"],
     "https://upload.wikimedia.org/wikipedia/commons/5/5c/Pfanne_%28Edelstahl%29.jpg"),
    ("LED Desk Lamp", "home", 699, ["lighting", "office"],
     "https://upload.wikimedia.org/wikipedia/commons/d/d3/Wide_array_of_lamps.jpg"),
    ("Bluetooth Speaker", "electronics", 1799, ["audio", "portable"],
     "https://upload.wikimedia.org/wikipedia/commons/0/0e/Electrodynamic-loudspeaker.png"),
    ("Adjustable Dumbbell Set", "sports", 2499, ["fitness", "gym"],
     "https://upload.wikimedia.org/wikipedia/commons/e/e3/TwoDumbbells.JPG"),
    ("Drip Coffee Maker", "home", 1599, ["kitchen", "appliance"],
     "https://upload.wikimedia.org/wikipedia/commons/c/cd/Moka_Express_sideview.png"),
    ("Denim Jacket", "fashion", 1899, ["denim", "outerwear"],
     "https://upload.wikimedia.org/wikipedia/commons/3/3e/Jacket2-1.jpg"),
    ("Travel Backpack", "fashion", 1399, ["bag", "travel"],
     "https://upload.wikimedia.org/wikipedia/commons/d/d7/Rucksack1.jpg"),
    ("Cotton Bedsheet Set", "home", 999, ["bedding", "cotton"],
     "https://upload.wikimedia.org/wikipedia/commons/e/ed/Prze%C5%9Bcierad%C5%82o.jpg"),
]

# Fixed per-(seller, product) jitter so re-reading this file always explains
# the exact price shown — not re-randomized on every run.
random.seed("ondc-demo-catalog-v1")
PRICE_JITTER = {
    (seller_idx, product_idx): random.uniform(0.9, 1.1)
    for seller_idx in range(len(SELLERS))
    for product_idx in range(len(PRODUCT_TEMPLATES))
}


def register_seller(session: requests.Session, base_url: str, business_name: str, city: str, radius: int) -> dict:
    payload = {
        "email": f"demo-seller-{business_name.lower().replace(' ', '-')}-{RUN_ID}@example.com",
        "password": "CatalogDemoPass123!",
        "full_name": f"{business_name} (Demo)",
        "business_name": f"{business_name} (Demo)",
        "city": city,
        "delivery_radius_km": radius,
    }
    resp = session.post(f"{base_url}/api/v1/auth/register/seller", json=payload, timeout=REQUEST_TIMEOUT_S)
    resp.raise_for_status()
    body = resp.json()
    body["_email"] = payload["email"]
    return body


def create_product(
    session: requests.Session, base_url: str, seller_token: str, name: str, category: str,
    price: float, tags: list[str], image_url: str, stock: int,
) -> dict:
    payload = {
        "name": name,
        "description": f"{name} — demo catalog listing for the ONDC AI+Blockchain prototype.",
        "category": category,
        "tags": [*tags, "demo-catalog"],
        "price": f"{price:.2f}",
        "stock_quantity": stock,
        "image_url": image_url,
    }
    resp = session.post(
        f"{base_url}/api/v1/products",
        json=payload,
        headers={"Authorization": f"Bearer {seller_token}"},
        timeout=REQUEST_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    session = requests.Session()
    print(f"Run ID: {RUN_ID}  |  Target: {base_url}")
    print("Waking the service (Render free tier can take 30-60s on the first request)...")

    seller_records = []
    for seller_idx, (business_name, city, radius, price_mult) in enumerate(SELLERS):
        seller = register_seller(session, base_url, business_name, city, radius)
        print(f"Registered seller: {business_name} (Demo) — {city}, {radius}km radius — {seller['_email']}")
        seller_records.append((seller_idx, business_name, price_mult, seller["access_token"]))

    total_products = 0
    for seller_idx, business_name, price_mult, token in seller_records:
        for product_idx, (name, category, base_price, tags, image_url) in enumerate(PRODUCT_TEMPLATES):
            jitter = PRICE_JITTER[(seller_idx, product_idx)]
            price = round(base_price * price_mult * jitter, -1) - 1  # e.g. 3299 -> x,x99-style price
            stock = random.randint(8, 40)
            create_product(session, base_url, token, name, category, max(price, 49), tags, image_url, stock)
            total_products += 1
        print(f"  {business_name}: listed {len(PRODUCT_TEMPLATES)} products")

    print()
    print("=" * 70)
    print(f"Done. {len(SELLERS)} sellers x {len(PRODUCT_TEMPLATES)} product types "
          f"= {total_products} real listings created against {base_url}.")
    print("Every one of the 15 product types now has 5 competing sellers at")
    print("different prices/cities/delivery radii — browse the app or call")
    print("GET /api/v1/products?category=electronics (etc.) to see them, or")
    print("log in as any buyer and check GET /api/v1/recommendations to see")
    print("the vendor-matching algorithm actually choosing between them.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
