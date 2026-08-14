from tests.helpers import auth_headers, create_product, register_buyer, register_seller


def _purchase(client, buyer_token, product_id, quantity=1, payment_method="upi"):
    return client.post(
        "/api/v1/orders",
        json={"product_id": product_id, "quantity": quantity, "payment_method": payment_method},
        headers=auth_headers(buyer_token),
    )


def test_create_order_requires_buyer_role(client):
    seller = register_seller(client)
    product = create_product(client, seller["access_token"])
    response = _purchase(client, seller["access_token"], product["id"])
    assert response.status_code == 403


def test_create_order_success_decrements_stock_and_marks_transaction_success(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"], stock_quantity=5, price="10.00")

    response = _purchase(client, buyer["access_token"], product["id"], quantity=2, payment_method="upi")

    assert response.status_code == 201
    body = response.json()
    assert body["order"]["amount"] == "20.00"
    assert body["order"]["status"] == "created"
    assert body["transaction"]["status"] == "success"

    updated_product = client.get(f"/api/v1/products/{product['id']}").json()
    assert updated_product["stock_quantity"] == 3


def test_create_order_cod_transaction_is_pending(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])

    response = _purchase(client, buyer["access_token"], product["id"], payment_method="cod")

    assert response.json()["transaction"]["status"] == "pending"


def test_create_order_insufficient_stock_is_rejected(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"], stock_quantity=1)

    response = _purchase(client, buyer["access_token"], product["id"], quantity=5)

    assert response.status_code == 400


def test_create_order_product_not_found(client):
    buyer = register_buyer(client)
    response = _purchase(client, buyer["access_token"], "00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_buyer_sees_only_own_orders(client):
    seller = register_seller(client)
    buyer_a = register_buyer(client, email="a@example.com")
    buyer_b = register_buyer(client, email="b@example.com")
    product = create_product(client, seller["access_token"], stock_quantity=10)

    _purchase(client, buyer_a["access_token"], product["id"])
    _purchase(client, buyer_b["access_token"], product["id"])

    response = client.get("/api/v1/orders", headers=auth_headers(buyer_a["access_token"]))

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_seller_sees_orders_across_their_buyers(client):
    seller = register_seller(client)
    buyer_a = register_buyer(client, email="a@example.com")
    buyer_b = register_buyer(client, email="b@example.com")
    product = create_product(client, seller["access_token"], stock_quantity=10)

    _purchase(client, buyer_a["access_token"], product["id"])
    _purchase(client, buyer_b["access_token"], product["id"])

    response = client.get("/api/v1/orders", headers=auth_headers(seller["access_token"]))

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_unrelated_buyer_cannot_view_someone_elses_order(client):
    seller = register_seller(client)
    buyer_a = register_buyer(client, email="a@example.com")
    buyer_b = register_buyer(client, email="b@example.com")
    product = create_product(client, seller["access_token"])
    order_id = _purchase(client, buyer_a["access_token"], product["id"]).json()["order"]["id"]

    response = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers(buyer_b["access_token"]))

    assert response.status_code == 403


def test_order_status_happy_path_to_delivered(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])
    order_id = _purchase(client, buyer["access_token"], product["id"]).json()["order"]["id"]

    for target in ("confirmed", "shipped", "delivered"):
        response = client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": target},
            headers=auth_headers(seller["access_token"]),
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == target

    final = client.get(f"/api/v1/orders/{order_id}", headers=auth_headers(seller["access_token"])).json()
    assert final["delivered_at"] is not None


def test_order_status_rejects_invalid_transition(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"])
    order_id = _purchase(client, buyer["access_token"], product["id"]).json()["order"]["id"]

    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "delivered"},
        headers=auth_headers(seller["access_token"]),
    )

    assert response.status_code == 400


def test_order_status_update_by_non_owning_seller_is_forbidden(client):
    owner = register_seller(client, email="owner@example.com")
    other = register_seller(client, email="other@example.com", business_name="Other Shop")
    buyer = register_buyer(client)
    product = create_product(client, owner["access_token"])
    order_id = _purchase(client, buyer["access_token"], product["id"]).json()["order"]["id"]

    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "confirmed"},
        headers=auth_headers(other["access_token"]),
    )

    assert response.status_code == 403


def test_cancelling_an_order_restocks_the_product(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"], stock_quantity=5)

    order_id = _purchase(client, buyer["access_token"], product["id"], quantity=2).json()["order"]["id"]
    assert client.get(f"/api/v1/products/{product['id']}").json()["stock_quantity"] == 3

    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "cancelled"},
        headers=auth_headers(seller["access_token"]),
    )

    assert response.status_code == 200
    assert client.get(f"/api/v1/products/{product['id']}").json()["stock_quantity"] == 5
