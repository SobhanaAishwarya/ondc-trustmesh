def _register_buyer(client, email="buyer@example.com"):
    return client.post(
        "/api/v1/auth/register/buyer",
        json={
            "email": email,
            "password": "buyerpass123",
            "full_name": "Bee Yer",
            "preferred_categories": ["electronics", "books"],
        },
    )


def _register_seller(client, email="seller@example.com"):
    return client.post(
        "/api/v1/auth/register/seller",
        json={
            "email": email,
            "password": "sellerpass123",
            "full_name": "Sel Ler",
            "business_name": "Sel's Shop",
        },
    )


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_buyer_returns_token(client):
    response = _register_buyer(client)
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "buyer"
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_register_seller_returns_token(client):
    response = _register_seller(client)
    assert response.status_code == 201
    assert response.json()["role"] == "seller"


def test_duplicate_email_registration_is_rejected(client):
    _register_buyer(client, email="dupe@example.com")
    response = _register_buyer(client, email="dupe@example.com")
    assert response.status_code == 400


def test_login_with_correct_credentials_succeeds(client):
    _register_buyer(client, email="login@example.com")

    response = client.post(
        "/api/v1/auth/login", json={"email": "login@example.com", "password": "buyerpass123"}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_with_wrong_password_is_rejected(client):
    _register_buyer(client, email="login2@example.com")

    response = client.post(
        "/api/v1/auth/login", json={"email": "login2@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401


def test_me_without_token_is_unauthorized(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_valid_token_returns_profile(client):
    token = _register_buyer(client, email="me@example.com").json()["access_token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "me@example.com"
    assert body["buyer"]["preferred_categories"] == ["electronics", "books"]
    assert body["seller"] is None


def test_me_with_seller_token_returns_seller_profile(client):
    token = _register_seller(client, email="sellerme@example.com").json()["access_token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["seller"]["business_name"] == "Sel's Shop"
    assert body["buyer"] is None


def test_me_with_garbage_token_is_unauthorized(client):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_register_returns_a_refresh_token_too(client):
    body = _register_buyer(client, email="refresh1@example.com").json()
    assert body["refresh_token"]
    assert body["refresh_token"] != body["access_token"]


def test_refresh_token_issues_a_new_working_access_token(client):
    refresh_token = _register_buyer(client, email="refresh2@example.com").json()["refresh_token"]

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    new_access_token = response.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access_token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "refresh2@example.com"


def test_refresh_rejects_an_access_token(client):
    access_token = _register_buyer(client, email="refresh3@example.com").json()["access_token"]
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert response.status_code == 401


def test_refresh_rejects_garbage_token(client):
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 401


def test_buyer_can_update_own_profile(client):
    token = _register_buyer(client, email="profile1@example.com").json()["access_token"]

    response = client.patch(
        "/api/v1/auth/me",
        json={"full_name": "New Name", "preferred_categories": ["Books", "Beauty"]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "New Name"
    assert body["buyer"]["preferred_categories"] == ["Books", "Beauty"]


def test_buyer_setting_a_wallet_address_does_not_crash_with_blockchain_disabled(client):
    """register_buyer_onchain no-ops when BLOCKCHAIN_ENABLED is false (the
    test-suite default) — mirrors the seller wallet-address behavior;
    is_onchain_registered stays False rather than the request failing."""
    token = _register_buyer(client, email="chainbuyer@example.com").json()["access_token"]

    response = client.patch(
        "/api/v1/auth/me",
        json={"wallet_address": "0x90F79bf6EB2c4f870365E785982E1f101E93b906"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["buyer"]["wallet_address"] == "0x90F79bf6EB2c4f870365E785982E1f101E93b906"
    assert body["buyer"]["is_onchain_registered"] is False


def test_updating_profile_rejects_a_malformed_wallet_address(client):
    token = _register_buyer(client, email="badwallet@example.com").json()["access_token"]

    response = client.patch(
        "/api/v1/auth/me",
        json={"wallet_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C"},  # one hex char short
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_seller_can_update_own_profile(client):
    token = _register_seller(client, email="profile2@example.com").json()["access_token"]

    response = client.patch(
        "/api/v1/auth/me",
        json={"business_name": "Renamed Shop", "gstin": "22AAAAA0000A1Z5"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["seller"]["business_name"] == "Renamed Shop"
    assert body["seller"]["gstin"] == "22AAAAA0000A1Z5"


def test_seller_only_fields_are_ignored_for_a_buyer(client):
    token = _register_buyer(client, email="profile3@example.com").json()["access_token"]

    response = client.patch(
        "/api/v1/auth/me", json={"business_name": "Should Be Ignored"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["buyer"] is not None
