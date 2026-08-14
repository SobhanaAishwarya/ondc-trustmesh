from tests.helpers import auth_headers, create_product, register_buyer, register_seller


def _purchase(client, buyer_token, product_id, **overrides):
    payload = {"product_id": product_id, "quantity": 1, "payment_method": "upi"}
    payload.update(overrides)
    return client.post("/api/v1/orders", json=payload, headers=auth_headers(buyer_token))


def test_order_creation_produces_a_fraud_log_consistent_with_the_transaction(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])

    order_response = _purchase(client, buyer["access_token"], product["id"])
    assert order_response.status_code == 201
    txn = order_response.json()["transaction"]

    assert txn["fraud_probability"] is not None
    assert 0.0 <= float(txn["fraud_probability"]) <= 1.0
    assert isinstance(txn["is_fraud_flagged"], bool)

    alerts = client.get(
        "/api/v1/fraud/alerts", params={"only_flagged": False}, headers=auth_headers(seller["access_token"])
    ).json()
    assert alerts["total"] == 1
    log = alerts["items"][0]
    assert log["transaction_id"] == txn["id"]
    assert log["is_flagged"] == txn["is_fraud_flagged"]
    assert log["model_name"] == "random_forest"
    assert len(log["risk_factors"]) == 3


def test_buyer_only_sees_their_own_fraud_alerts(client):
    seller = register_seller(client)
    buyer_a = register_buyer(client, email="a@example.com")
    buyer_b = register_buyer(client, email="b@example.com")
    product = create_product(client, seller["access_token"], stock_quantity=10)

    _purchase(client, buyer_a["access_token"], product["id"])
    _purchase(client, buyer_b["access_token"], product["id"])

    response = client.get(
        "/api/v1/fraud/alerts", params={"only_flagged": False}, headers=auth_headers(buyer_a["access_token"])
    )
    assert response.json()["total"] == 1


def test_only_flagged_query_param_filters_consistently(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])
    txn = _purchase(client, buyer["access_token"], product["id"]).json()["transaction"]

    flagged_only = client.get("/api/v1/fraud/alerts", headers=auth_headers(seller["access_token"])).json()
    all_logs = client.get(
        "/api/v1/fraud/alerts", params={"only_flagged": False}, headers=auth_headers(seller["access_token"])
    ).json()

    assert all_logs["total"] == 1
    expected_flagged_total = 1 if txn["is_fraud_flagged"] else 0
    assert flagged_only["total"] == expected_flagged_total


def test_admin_can_review_a_fraud_log(client, admin_token):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])
    _purchase(client, buyer["access_token"], product["id"])

    log_id = _first_log_id(client, seller["access_token"])

    response = client.patch(
        f"/api/v1/fraud/logs/{log_id}/review",
        json={"admin_decision": "false_positive"},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["admin_decision"] == "false_positive"
    assert body["reviewed_by_admin_id"] is not None


def test_non_admin_cannot_review_a_fraud_log(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])
    _purchase(client, buyer["access_token"], product["id"])

    log_id = _first_log_id(client, seller["access_token"])

    response = client.patch(
        f"/api/v1/fraud/logs/{log_id}/review",
        json={"admin_decision": "false_positive"},
        headers=auth_headers(seller["access_token"]),
    )

    assert response.status_code == 403


def test_review_rejects_invalid_decision_value(client, admin_token):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])
    _purchase(client, buyer["access_token"], product["id"])

    log_id = _first_log_id(client, seller["access_token"])

    response = client.patch(
        f"/api/v1/fraud/logs/{log_id}/review",
        json={"admin_decision": "not_a_real_value"},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 422


def _first_log_id(client, seller_token):
    logs = client.get(
        "/api/v1/fraud/alerts", params={"only_flagged": False}, headers=auth_headers(seller_token)
    ).json()
    return logs["items"][0]["id"]
