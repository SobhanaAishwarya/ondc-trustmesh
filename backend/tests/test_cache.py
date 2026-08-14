"""Redis-backed caching and refresh-token revocation (app/core/cache.py).

Uses the `fake_redis` fixture (conftest.py) rather than a live Redis
instance — these tests prove the actual read-through/invalidation/
revocation *logic*, not just that the code doesn't crash without Redis
(that's already implicitly proven by every other test in this suite,
which all run with caching disabled).
"""

import json

from tests.helpers import auth_headers, create_product, register_buyer, register_seller


def test_product_detail_is_served_from_cache_until_invalidated(client, fake_redis):
    seller = register_seller(client)
    product = create_product(client, seller["access_token"], name="Original Name")

    first = client.get(f"/api/v1/products/{product['id']}")
    assert first.json()["name"] == "Original Name"
    cache_key = f"product:{product['id']}"
    assert cache_key in fake_redis.store

    # Tamper with the cached entry directly — proves the second read comes
    # from cache, not a fresh DB query.
    cached = json.loads(fake_redis.store[cache_key])
    cached["name"] = "Cached Stale Name"
    fake_redis.store[cache_key] = json.dumps(cached)

    second = client.get(f"/api/v1/products/{product['id']}")
    assert second.json()["name"] == "Cached Stale Name"

    # Updating the product invalidates its cache entry; the next read
    # reflects the real, current row again.
    client.patch(
        f"/api/v1/products/{product['id']}",
        json={"name": "Updated Name"},
        headers=auth_headers(seller["access_token"]),
    )
    third = client.get(f"/api/v1/products/{product['id']}")
    assert third.json()["name"] == "Updated Name"


def test_product_list_cache_is_invalidated_when_a_new_product_is_created(client, fake_redis):
    seller = register_seller(client)
    create_product(client, seller["access_token"], name="First")

    first = client.get("/api/v1/products")
    assert first.json()["total"] == 1

    create_product(client, seller["access_token"], name="Second")

    second = client.get("/api/v1/products")
    assert second.json()["total"] == 2


def test_trust_score_is_cached_and_invalidated_on_recompute(client, fake_redis):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"], stock_quantity=5)
    seller_id = product["seller_id"]

    order = client.post(
        "/api/v1/orders",
        json={"product_id": product["id"], "quantity": 1, "payment_method": "upi"},
        headers=auth_headers(buyer["access_token"]),
    ).json()["order"]

    first = client.get(f"/api/v1/trust/sellers/{seller_id}")
    assert first.status_code == 200
    cache_key = f"trust_score:current:{seller_id}"
    assert cache_key in fake_redis.store

    cached = json.loads(fake_redis.store[cache_key])
    cached["score"] = "1.23"
    fake_redis.store[cache_key] = json.dumps(cached)

    second = client.get(f"/api/v1/trust/sellers/{seller_id}")
    assert second.json()["score"] == "1.23"

    for next_status in ("confirmed", "shipped", "delivered"):
        client.patch(
            f"/api/v1/orders/{order['id']}/status",
            json={"status": next_status},
            headers=auth_headers(seller["access_token"]),
        )

    third = client.get(f"/api/v1/trust/sellers/{seller_id}")
    assert third.json()["score"] != "1.23"


def test_refresh_token_is_revoked_after_use(client, fake_redis):
    tokens = register_buyer(client)
    refresh_token = tokens["refresh_token"]

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert first.status_code == 200

    second = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert second.status_code == 401
    assert "revoked" in second.json()["detail"].lower()


def test_logout_revokes_the_refresh_token(client, fake_redis):
    tokens = register_buyer(client)
    refresh_token = tokens["refresh_token"]

    logout_response = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_response.status_code == 204

    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_response.status_code == 401


def test_logout_with_an_already_invalid_token_still_succeeds(client, fake_redis):
    response = client.post("/api/v1/auth/logout", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 204
