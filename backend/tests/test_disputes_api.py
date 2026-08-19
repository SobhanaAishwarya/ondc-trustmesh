from tests.helpers import auth_headers, create_product, register_buyer, register_seller


def _purchase(client, buyer_token, product_id, **overrides):
    payload = {"product_id": product_id, "quantity": 1, "payment_method": "upi"}
    payload.update(overrides)
    return client.post("/api/v1/orders", json=payload, headers=auth_headers(buyer_token))


def _advance(client, seller_token, order_id, *targets):
    for target in targets:
        response = client.patch(
            f"/api/v1/orders/{order_id}/status", json={"status": target}, headers=auth_headers(seller_token)
        )
        assert response.status_code == 200, response.text


def _shipped_order(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])
    order_id = _purchase(client, buyer["access_token"], product["id"]).json()["order"]["id"]
    _advance(client, seller["access_token"], order_id, "confirmed", "shipped")
    return seller, buyer, order_id


def test_raise_dispute_requires_being_a_party(client):
    _seller, _buyer, order_id = _shipped_order(client)
    outsider = register_buyer(client, email="outsider@example.com")

    response = client.post(
        "/api/v1/disputes",
        json={"order_id": order_id, "reason": "item_not_received"},
        headers=auth_headers(outsider["access_token"]),
    )
    assert response.status_code == 403


def test_raise_dispute_on_a_not_yet_confirmed_order_is_rejected(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])
    order_id = _purchase(client, buyer["access_token"], product["id"]).json()["order"]["id"]

    response = client.post(
        "/api/v1/disputes",
        json={"order_id": order_id, "reason": "item_not_received"},
        headers=auth_headers(buyer["access_token"]),
    )
    assert response.status_code == 400


def test_raise_dispute_moves_order_to_disputed(client):
    _seller, buyer, order_id = _shipped_order(client)

    response = client.post(
        "/api/v1/disputes",
        json={"order_id": order_id, "reason": "item_not_received", "evidence_score": "0.8"},
        headers=auth_headers(buyer["access_token"]),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "open"
    assert body["evidence_buyer_score"] == "0.80"

    order = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers(buyer["access_token"])).json()
    assert order["status"] == "disputed"


def test_duplicate_open_dispute_is_rejected(client):
    _seller, buyer, order_id = _shipped_order(client)
    client.post(
        "/api/v1/disputes",
        json={"order_id": order_id, "reason": "item_not_received"},
        headers=auth_headers(buyer["access_token"]),
    )

    response = client.post(
        "/api/v1/disputes",
        json={"order_id": order_id, "reason": "other"},
        headers=auth_headers(buyer["access_token"]),
    )
    assert response.status_code == 400


def test_both_sides_submitting_evidence_triggers_auto_resolution(client):
    seller, buyer, order_id = _shipped_order(client)
    dispute_id = client.post(
        "/api/v1/disputes",
        json={"order_id": order_id, "reason": "item_not_as_described", "evidence_score": "0.3"},
        headers=auth_headers(buyer["access_token"]),
    ).json()["id"]

    response = client.post(
        f"/api/v1/disputes/{dispute_id}/evidence",
        json={"evidence_score": "0.9"},
        headers=auth_headers(seller["access_token"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "auto_resolved"
    assert body["resolved_by"] == "rule_auto"
    assert body["resolution_outcome"] is not None
    assert 0 <= body["seller_share_bps"] <= 10000

    order = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers(buyer["access_token"])).json()
    assert order["status"] == "resolved"


def test_evidence_submission_by_non_party_is_forbidden(client):
    _seller, buyer, order_id = _shipped_order(client)
    dispute_id = client.post(
        "/api/v1/disputes",
        json={"order_id": order_id, "reason": "other"},
        headers=auth_headers(buyer["access_token"]),
    ).json()["id"]
    outsider = register_seller(client, email="outsider@example.com", business_name="Outsider Shop")

    response = client.post(
        f"/api/v1/disputes/{dispute_id}/evidence",
        json={"evidence_score": "0.5"},
        headers=auth_headers(outsider["access_token"]),
    )
    assert response.status_code == 403


def test_admin_can_arbitrate_an_open_dispute(client, admin_token):
    _seller, buyer, order_id = _shipped_order(client)
    dispute_id = client.post(
        "/api/v1/disputes",
        json={"order_id": order_id, "reason": "other"},
        headers=auth_headers(buyer["access_token"]),
    ).json()["id"]

    response = client.patch(
        f"/api/v1/disputes/{dispute_id}/arbitrate",
        json={"seller_share_bps": 3000},
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "arbitrated"
    assert body["resolved_by"] == "arbitrator"
    assert body["seller_share_bps"] == 3000


def test_non_admin_cannot_arbitrate(client):
    _seller, buyer, order_id = _shipped_order(client)
    dispute_id = client.post(
        "/api/v1/disputes",
        json={"order_id": order_id, "reason": "other"},
        headers=auth_headers(buyer["access_token"]),
    ).json()["id"]

    response = client.patch(
        f"/api/v1/disputes/{dispute_id}/arbitrate",
        json={"seller_share_bps": 3000},
        headers=auth_headers(buyer["access_token"]),
    )
    assert response.status_code == 403


def test_list_disputes_is_scoped_to_the_caller(client):
    seller, buyer, order_id = _shipped_order(client)
    client.post(
        "/api/v1/disputes",
        json={"order_id": order_id, "reason": "other"},
        headers=auth_headers(buyer["access_token"]),
    )
    other_buyer = register_buyer(client, email="other@example.com")

    mine = client.get("/api/v1/disputes", headers=auth_headers(buyer["access_token"])).json()
    sellers_view = client.get("/api/v1/disputes", headers=auth_headers(seller["access_token"])).json()
    unrelated = client.get("/api/v1/disputes", headers=auth_headers(other_buyer["access_token"])).json()

    assert mine["total"] == 1
    assert sellers_view["total"] == 1
    assert unrelated["total"] == 0


def test_get_dispute_forbidden_for_unrelated_user(client):
    _seller, buyer, order_id = _shipped_order(client)
    dispute_id = client.post(
        "/api/v1/disputes",
        json={"order_id": order_id, "reason": "other"},
        headers=auth_headers(buyer["access_token"]),
    ).json()["id"]
    outsider = register_buyer(client, email="outsider2@example.com")

    response = client.get(f"/api/v1/disputes/{dispute_id}", headers=auth_headers(outsider["access_token"]))
    assert response.status_code == 403
