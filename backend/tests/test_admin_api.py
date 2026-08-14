from tests.helpers import auth_headers, create_product, register_buyer, register_seller


def test_list_users_requires_admin(client):
    buyer = register_buyer(client)
    response = client.get("/api/v1/admin/users", headers=auth_headers(buyer["access_token"]))
    assert response.status_code == 403


def test_admin_can_list_and_filter_users(client, admin_token):
    register_buyer(client, email="u1@example.com")
    register_seller(client, email="u2@example.com")

    response = client.get(
        "/api/v1/admin/users", params={"role": "buyer"}, headers=auth_headers(admin_token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert all(u["role"] == "buyer" for u in body["items"])


def test_admin_can_search_users_by_email(client, admin_token):
    register_buyer(client, email="findme@example.com")
    response = client.get(
        "/api/v1/admin/users", params={"q": "findme"}, headers=auth_headers(admin_token)
    ).json()
    assert response["total"] == 1
    assert response["items"][0]["email"] == "findme@example.com"


def test_deactivating_a_user_locks_out_their_existing_token(client, admin_token):
    buyer = register_buyer(client, email="lockout@example.com")
    user_id = client.get("/api/v1/auth/me", headers=auth_headers(buyer["access_token"])).json()["id"]

    response = client.patch(
        f"/api/v1/admin/users/{user_id}/status", json={"is_active": False}, headers=auth_headers(admin_token)
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    me = client.get("/api/v1/auth/me", headers=auth_headers(buyer["access_token"]))
    assert me.status_code == 401


def test_admin_cannot_deactivate_own_account(client, admin_token):
    admin_user_id = client.get("/api/v1/auth/me", headers=auth_headers(admin_token)).json()["id"]
    response = client.patch(
        f"/api/v1/admin/users/{admin_user_id}/status", json={"is_active": False}, headers=auth_headers(admin_token)
    )
    assert response.status_code == 400


def test_analytics_requires_admin(client):
    seller = register_seller(client)
    response = client.get("/api/v1/admin/analytics", headers=auth_headers(seller["access_token"]))
    assert response.status_code == 403


def test_analytics_reflects_real_data(client, admin_token):
    seller = register_seller(client)
    buyer = register_buyer(client)
    product = create_product(client, seller["access_token"], price="25.00", stock_quantity=5)
    client.post(
        "/api/v1/orders",
        json={"product_id": product["id"], "quantity": 1, "payment_method": "upi"},
        headers=auth_headers(buyer["access_token"]),
    )

    report = client.get("/api/v1/admin/analytics", headers=auth_headers(admin_token)).json()

    assert report["total_users"] >= 2
    assert report["total_products"] >= 1
    assert report["total_orders"] >= 1
    assert report["total_transactions"] >= 1
    assert float(report["total_revenue"]) >= 25.0
    assert 0 <= report["average_seller_trust_score"] <= 100


def test_blockchain_hashes_list_requires_admin(client):
    seller = register_seller(client)
    response = client.get("/api/v1/admin/blockchain-hashes", headers=auth_headers(seller["access_token"]))
    assert response.status_code == 403


def test_blockchain_hashes_list_is_empty_before_bridge_module(client, admin_token):
    response = client.get("/api/v1/admin/blockchain-hashes", headers=auth_headers(admin_token)).json()
    assert response["total"] == 0
