"""Self-service returns: POST /orders/{id}/return (app/api/v1/endpoints/
orders.py's request_return). Distinct from the contested-dispute flow in
test_disputes_api.py — these are the "buyer self-serves, no seller
counter-evidence needed" path for a within-window, good-condition return.
"""

from datetime import datetime, timedelta, timezone

from tests.conftest import TestingSessionLocal
from tests.helpers import auth_headers, create_product, register_buyer, register_seller

from app.models.order import Order


def _purchase_and_deliver(client, buyer_token, seller_token, product_id):
    order = client.post(
        "/api/v1/orders",
        json={"product_id": product_id, "quantity": 1, "payment_method": "upi"},
        headers=auth_headers(buyer_token),
    ).json()["order"]
    for target in ("confirmed", "shipped", "delivered"):
        client.patch(
            f"/api/v1/orders/{order['id']}/status",
            json={"status": target},
            headers=auth_headers(seller_token),
        )
    return order


def _backdate_delivery(order_id: str, days_ago: int) -> None:
    db = TestingSessionLocal()
    try:
        order = db.get(Order, order_id)
        order.delivered_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        db.commit()
    finally:
        db.close()


def test_return_in_good_condition_within_window_is_auto_refunded(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"], stock_quantity=5)
    order = _purchase_and_deliver(client, buyer["access_token"], seller["access_token"], product["id"])

    response = client.post(
        f"/api/v1/orders/{order['id']}/return",
        json={"reason": "item_not_as_described", "item_condition": "good"},
        headers=auth_headers(buyer["access_token"]),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "auto_resolved"
    assert body["resolved_by"] == "auto_return"
    assert body["seller_share_bps"] == 0

    updated_order = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(buyer["access_token"])).json()
    assert updated_order["status"] == "resolved"


def test_return_with_damaged_item_opens_a_contested_dispute_instead(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"], stock_quantity=5)
    order = _purchase_and_deliver(client, buyer["access_token"], seller["access_token"], product["id"])

    response = client.post(
        f"/api/v1/orders/{order['id']}/return",
        json={"reason": "damaged_in_transit", "item_condition": "damaged"},
        headers=auth_headers(buyer["access_token"]),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "open"
    assert body["resolved_by"] is None

    updated_order = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(buyer["access_token"])).json()
    assert updated_order["status"] == "disputed"


def test_return_outside_the_window_is_rejected(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"], stock_quantity=5)
    order = _purchase_and_deliver(client, buyer["access_token"], seller["access_token"], product["id"])
    _backdate_delivery(order["id"], days_ago=10)

    response = client.post(
        f"/api/v1/orders/{order['id']}/return",
        json={"reason": "item_not_as_described"},
        headers=auth_headers(buyer["access_token"]),
    )

    assert response.status_code == 400
    assert "window" in response.json()["detail"].lower()


def test_return_on_an_undelivered_order_is_rejected(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"], stock_quantity=5)
    order = client.post(
        "/api/v1/orders",
        json={"product_id": product["id"], "quantity": 1, "payment_method": "upi"},
        headers=auth_headers(buyer["access_token"]),
    ).json()["order"]

    response = client.post(
        f"/api/v1/orders/{order['id']}/return",
        json={"reason": "item_not_as_described"},
        headers=auth_headers(buyer["access_token"]),
    )

    assert response.status_code == 400


def test_return_by_a_different_buyer_is_forbidden(client):
    seller = register_seller(client)
    buyer = register_buyer(client, email="owner@example.com")
    other_buyer = register_buyer(client, email="other@example.com")
    product = create_product(client, seller["access_token"], stock_quantity=5)
    order = _purchase_and_deliver(client, buyer["access_token"], seller["access_token"], product["id"])

    response = client.post(
        f"/api/v1/orders/{order['id']}/return",
        json={"reason": "item_not_as_described"},
        headers=auth_headers(other_buyer["access_token"]),
    )

    assert response.status_code == 403


def test_cannot_request_a_second_return_while_one_is_open(client):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"], stock_quantity=5)
    order = _purchase_and_deliver(client, buyer["access_token"], seller["access_token"], product["id"])

    client.post(
        f"/api/v1/orders/{order['id']}/return",
        json={"reason": "damaged_in_transit", "item_condition": "damaged"},
        headers=auth_headers(buyer["access_token"]),
    )
    second = client.post(
        f"/api/v1/orders/{order['id']}/return",
        json={"reason": "item_not_as_described"},
        headers=auth_headers(buyer["access_token"]),
    )

    assert second.status_code == 400
