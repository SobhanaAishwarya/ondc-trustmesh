"""Load test. Run `seed.py` first so there's a real catalog to browse/buy
from, then:

    locust -f loadtest/locustfile.py --host http://localhost:8000 \
        --headless -u 50 -r 10 -t 30s --csv=loadtest_results

Two user classes, weighted like a real storefront: mostly anonymous
browsing (reads), a smaller share of registered buyers actually purchasing
(writes that also exercise the fraud-scoring model on every order).
"""

import random
import uuid

from locust import HttpUser, between, task


class BrowsingUser(HttpUser):
    weight = 4
    wait_time = between(0.3, 1.5)

    @task(3)
    def browse_products(self):
        self.client.get("/api/v1/products", name="/products")

    @task(1)
    def search_products(self):
        category = random.choice(["Electronics", "Books", "Fashion", "Grocery"])
        self.client.get("/api/v1/products", params={"category": category}, name="/products?category=")

    @task(1)
    def health_check(self):
        self.client.get("/health")


class BuyerJourneyUser(HttpUser):
    weight = 1
    wait_time = between(1, 3)

    def on_start(self):
        email = f"loadtest_buyer_{uuid.uuid4().hex[:12]}@example.com"
        response = self.client.post(
            "/api/v1/auth/register/buyer",
            json={"email": email, "password": "loadtestpass123", "full_name": "Load Test Buyer"},
            name="/auth/register/buyer",
        )
        self.token = response.json().get("access_token") if response.status_code == 201 else None

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(3)
    def browse_then_view_me(self):
        self.client.get("/api/v1/products", name="/products")
        self.client.get("/api/v1/auth/me", headers=self.headers, name="/auth/me")

    @task(1)
    def place_an_order(self):
        if not self.token:
            return
        listing = self.client.get("/api/v1/products", name="/products").json()
        if not listing["items"]:
            return
        product = random.choice(listing["items"])
        self.client.post(
            "/api/v1/orders",
            json={"product_id": product["id"], "quantity": 1, "payment_method": "upi"},
            headers=self.headers,
            name="/orders [POST]",
        )
