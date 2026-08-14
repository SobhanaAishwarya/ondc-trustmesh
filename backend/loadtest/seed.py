"""Seeds a seller with a handful of high-stock products before a load test
run, so locustfile.py's buyers have something real to browse and purchase
without every order attempt failing on insufficient stock (which would
measure stock contention, not request throughput — a different, also
valid, but separate thing to test).

Usage:
    python loadtest/seed.py --host http://localhost:8000
"""

import argparse
import time

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="http://localhost:8000")
    args = parser.parse_args()

    base = f"{args.host}/api/v1"
    email = f"loadtest_seller_{int(time.time())}@example.com"

    response = requests.post(
        f"{base}/auth/register/seller",
        json={"email": email, "password": "loadtestpass123", "full_name": "Load Test Seller", "business_name": "Load Test Shop"},
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    categories = ["Electronics", "Books", "Fashion", "Grocery"]
    for i, category in enumerate(categories):
        response = requests.post(
            f"{base}/products",
            json={
                "name": f"Load Test Product {i}",
                "description": "Seeded for load testing.",
                "category": category,
                "price": "199.99",
                "stock_quantity": 100_000,
            },
            headers=headers,
        )
        response.raise_for_status()
        print(f"Created product: {response.json()['id']} ({category})")

    print(f"\nSeeded as {email}. Run locust against {args.host} now.")


if __name__ == "__main__":
    main()
