"""Generates real, non-synthetic recommendation traffic against the live
deployed backend so `GET /recommendations/ctr` reports an actual number
instead of the 0 it shows with zero real usage.

This is deliberately NOT `scripts/evaluate_recommendation_ctr.py` (which
runs a synthetic, in-process backtest for an offline read on the ~20% CTR
KPI ahead of real traffic existing — see that script's docstring). This
one makes real HTTP requests against a real running deployment, creating
real rows in its database: a demo seller, a handful of demo buyers, real
products, real recommendation impressions, and real clicks (plus two real
orders, so `click_to_purchase_rate` isn't zero either). Every account it
creates is clearly named `ctr-demo-*` so it's obviously demo data if
anyone looks at the admin user list later, not something disguised as a
real customer.

Usage:
    python scripts/seed_live_ctr_demo.py [--base-url https://ondc-backend-5kxh.onrender.com]

Afterwards, view the real result yourself (this script has no admin
credentials and cannot read it back):
    GET {base_url}/api/v1/recommendations/ctr   (admin bearer token required)
via the Swagger UI at {base_url}/docs, logged in as your own admin account.
"""

import argparse
import random
import sys
import time
import uuid

import requests

try:
    # On some machines (seen on Windows here) requests/certifi's bundled CA
    # list doesn't include whatever issued Render's certificate chain, even
    # though the OS's own trust store (what `curl` uses) verifies it fine.
    # `truststore` makes `ssl` — and therefore `requests`, via urllib3 —
    # verify against the OS store instead. `pip install truststore` if this
    # script hits SSLCertVerificationError without it.
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

DEFAULT_BASE_URL = "https://ondc-backend-5kxh.onrender.com"
RUN_ID = uuid.uuid4().hex[:8]
CITIES = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai"]
CATEGORIES = ["electronics", "fashion", "home", "sports", "books"]

# Free-tier Render services sleep after inactivity and take 30-60s to wake
# on the first request — generous timeout so that cold start doesn't look
# like a failure.
REQUEST_TIMEOUT_S = 60


def register_seller(session: requests.Session, base_url: str) -> dict:
    payload = {
        "email": f"ctr-demo-seller-{RUN_ID}@example.com",
        "password": "CtrDemoPass123!",
        "full_name": "CTR Demo Seller",
        "business_name": f"CTR Demo Shop {RUN_ID}",
        "city": random.choice(CITIES),
    }
    resp = session.post(f"{base_url}/api/v1/auth/register/seller", json=payload, timeout=REQUEST_TIMEOUT_S)
    resp.raise_for_status()
    return resp.json()


def register_buyer(session: requests.Session, base_url: str, index: int) -> dict:
    payload = {
        "email": f"ctr-demo-buyer-{RUN_ID}-{index}@example.com",
        "password": "CtrDemoPass123!",
        "full_name": f"CTR Demo Buyer {index}",
        "preferred_categories": random.sample(CATEGORIES, k=2),
        "city": random.choice(CITIES),
    }
    resp = session.post(f"{base_url}/api/v1/auth/register/buyer", json=payload, timeout=REQUEST_TIMEOUT_S)
    resp.raise_for_status()
    return resp.json()


def create_product(session: requests.Session, base_url: str, seller_token: str, index: int) -> dict:
    category = CATEGORIES[index % len(CATEGORIES)]
    payload = {
        "name": f"CTR Demo Product {index} ({category})",
        "description": "Demo listing created by seed_live_ctr_demo.py for a real CTR measurement.",
        "category": category,
        "tags": ["demo"],
        "price": str(random.choice([499, 999, 1499, 2499, 3999])),
        "stock_quantity": 25,
    }
    resp = session.post(
        f"{base_url}/api/v1/products",
        json=payload,
        headers={"Authorization": f"Bearer {seller_token}"},
        timeout=REQUEST_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()


def get_recommendations(session: requests.Session, base_url: str, buyer_token: str, top_k: int = 6) -> list[dict]:
    resp = session.get(
        f"{base_url}/api/v1/recommendations",
        params={"top_k": top_k},
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=REQUEST_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()


def click_recommendation(session: requests.Session, base_url: str, buyer_token: str, rec_id: str) -> None:
    resp = session.post(
        f"{base_url}/api/v1/recommendations/{rec_id}/click",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=REQUEST_TIMEOUT_S,
    )
    resp.raise_for_status()


def place_order(session: requests.Session, base_url: str, buyer_token: str, product_id: str) -> dict:
    payload = {"product_id": product_id, "quantity": 1, "payment_method": "upi"}
    resp = session.post(
        f"{base_url}/api/v1/orders",
        json=payload,
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=REQUEST_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--num-buyers", type=int, default=5)
    parser.add_argument("--num-products", type=int, default=6)
    parser.add_argument("--sessions-per-buyer", type=int, default=2)
    parser.add_argument("--click-rate", type=float, default=0.5, help="fraction of shown items a buyer clicks")
    parser.add_argument("--purchasing-buyers", type=int, default=2, help="how many buyers also place a real order")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    session = requests.Session()

    print(f"Run ID: {RUN_ID}  |  Target: {base_url}")
    print("Waking the service (Render free tier can take 30-60s on the first request)...")

    seller_email = f"ctr-demo-seller-{RUN_ID}@example.com"
    seller = register_seller(session, base_url)
    print(f"Registered seller: {seller_email} (user_id={seller['user_id']})")

    products = [create_product(session, base_url, seller["access_token"], i) for i in range(args.num_products)]
    print(f"Created {len(products)} products across {len({p['category'] for p in products})} categories")

    total_impressions = 0
    total_clicks = 0
    total_orders = 0

    for i in range(args.num_buyers):
        buyer_email = f"ctr-demo-buyer-{RUN_ID}-{i}@example.com"
        buyer = register_buyer(session, base_url, i)
        buyer_token = buyer["access_token"]
        print(f"Registered buyer {i}: {buyer_email} (user_id={buyer['user_id']})")

        buyer_impressions: list[dict] = []
        for session_num in range(args.sessions_per_buyer):
            time.sleep(0.5)  # spread requests out slightly rather than hammering the API back-to-back
            recs = get_recommendations(session, base_url, buyer_token)
            buyer_impressions.extend(recs)
            total_impressions += len(recs)
            print(f"  session {session_num}: {len(recs)} recommendations shown")

        to_click = random.sample(buyer_impressions, k=max(1, int(len(buyer_impressions) * args.click_rate)))
        for rec in to_click:
            click_recommendation(session, base_url, buyer_token, rec["id"])
            total_clicks += 1
        print(f"  clicked {len(to_click)}/{len(buyer_impressions)} shown recommendations")

        if i < args.purchasing_buyers and to_click:
            purchased_product_id = to_click[0]["product"]["id"]
            order = place_order(session, base_url, buyer_token, purchased_product_id)
            total_orders += 1
            print(f"  placed a real order for {to_click[0]['product']['name']} "
                  f"(fraud_probability={order['transaction']['fraud_probability']})")

    print()
    print("=" * 70)
    print(f"Done. Real traffic generated against {base_url}:")
    print(f"  impressions logged : {total_impressions}")
    print(f"  clicks logged      : {total_clicks}")
    print(f"  orders placed      : {total_orders}")
    print(f"  raw click rate     : {total_clicks / total_impressions:.1%}" if total_impressions else "  (no impressions)")
    print()
    print("This script has no admin credentials, so it can't read back the")
    print(f"official report. View the real, live number yourself at:")
    print(f"  {base_url}/docs  ->  GET /api/v1/recommendations/ctr  (log in as your admin account)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
