from tests.helpers import auth_headers, create_product, register_buyer, register_seller


def _purchase(client, buyer_token, product_id, **overrides):
    payload = {"product_id": product_id, "quantity": 1, "payment_method": "upi"}
    payload.update(overrides)
    return client.post("/api/v1/orders", json=payload, headers=auth_headers(buyer_token))


def _advance_to_delivered(client, seller_token, order_id):
    for target in ("confirmed", "shipped", "delivered"):
        response = client.patch(
            f"/api/v1/orders/{order_id}/status", json={"status": target}, headers=auth_headers(seller_token)
        )
        assert response.status_code == 200, response.text


def _seller_id(client, seller_token):
    return client.get("/api/v1/auth/me", headers=auth_headers(seller_token)).json()["seller"]["id"]


def test_get_trust_score_lazily_computes_for_a_seller_with_no_history(client):
    seller = register_seller(client)
    seller_id = _seller_id(client, seller["access_token"])

    response = client.get(f"/api/v1/trust/sellers/{seller_id}")
    assert response.status_code == 200
    assert 0 <= float(response.json()["score"]) <= 100


def test_delivering_an_order_recomputes_the_score(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])
    seller_id = _seller_id(client, seller["access_token"])

    baseline = client.get(f"/api/v1/trust/sellers/{seller_id}").json()

    order_id = _purchase(client, buyer["access_token"], product["id"]).json()["order"]["id"]
    _advance_to_delivered(client, seller["access_token"], order_id)

    after_delivery = client.get(f"/api/v1/trust/sellers/{seller_id}").json()
    assert after_delivery["id"] != baseline["id"]
    assert float(after_delivery["order_completion_rate"]) == 1.0


def test_history_grows_with_each_recompute(client):
    seller = register_seller(client)
    seller_id = _seller_id(client, seller["access_token"])
    client.get(f"/api/v1/trust/sellers/{seller_id}")  # first lazy compute

    client.post(f"/api/v1/trust/sellers/{seller_id}/recompute", headers=auth_headers(seller["access_token"]))

    history = client.get(f"/api/v1/trust/sellers/{seller_id}/history").json()
    assert history["total"] >= 2


def test_recompute_forbidden_for_a_different_seller(client):
    owner = register_seller(client, email="owner@example.com")
    other = register_seller(client, email="other@example.com", business_name="Other Shop")
    owner_seller_id = _seller_id(client, owner["access_token"])

    response = client.post(
        f"/api/v1/trust/sellers/{owner_seller_id}/recompute", headers=auth_headers(other["access_token"])
    )
    assert response.status_code == 403


def test_review_requires_delivered_order(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])
    order_id = _purchase(client, buyer["access_token"], product["id"]).json()["order"]["id"]

    response = client.post(
        "/api/v1/reviews", json={"order_id": order_id, "rating": 5}, headers=auth_headers(buyer["access_token"])
    )
    assert response.status_code == 400


def test_review_after_delivery_succeeds_and_updates_seller_rating(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])
    seller_id = _seller_id(client, seller["access_token"])
    order_id = _purchase(client, buyer["access_token"], product["id"]).json()["order"]["id"]
    _advance_to_delivered(client, seller["access_token"], order_id)

    response = client.post(
        "/api/v1/reviews",
        json={"order_id": order_id, "rating": 5, "comment": "Great!"},
        headers=auth_headers(buyer["access_token"]),
    )
    assert response.status_code == 201

    reviews = client.get(f"/api/v1/reviews/sellers/{seller_id}").json()
    assert len(reviews) == 1
    assert reviews[0]["rating"] == 5

    trust = client.get(f"/api/v1/trust/sellers/{seller_id}").json()
    assert float(trust["avg_customer_rating"]) == 5.0


def test_duplicate_review_is_rejected(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])
    order_id = _purchase(client, buyer["access_token"], product["id"]).json()["order"]["id"]
    _advance_to_delivered(client, seller["access_token"], order_id)

    client.post(
        "/api/v1/reviews", json={"order_id": order_id, "rating": 4}, headers=auth_headers(buyer["access_token"])
    )
    response = client.post(
        "/api/v1/reviews", json={"order_id": order_id, "rating": 2}, headers=auth_headers(buyer["access_token"])
    )
    assert response.status_code == 400
