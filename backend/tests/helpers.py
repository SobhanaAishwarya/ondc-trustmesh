"""Shared test setup: registering buyers/sellers and creating products so
each test file isn't re-deriving the same boilerplate."""


def register_buyer(client, email="buyer@example.com", **overrides):
    payload = {
        "email": email,
        "password": "buyerpass123",
        "full_name": "Bee Yer",
        "preferred_categories": [],
    }
    payload.update(overrides)
    response = client.post("/api/v1/auth/register/buyer", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def register_seller(client, email="seller@example.com", business_name="Sel's Shop", **overrides):
    payload = {
        "email": email,
        "password": "sellerpass123",
        "full_name": "Sel Ler",
        "business_name": business_name,
    }
    payload.update(overrides)
    response = client.post("/api/v1/auth/register/seller", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_product(client, seller_token, **overrides):
    payload = {
        "name": "Widget",
        "description": "A widget",
        "category": "electronics",
        "tags": ["gadget"],
        "price": "199.99",
        "stock_quantity": 10,
    }
    payload.update(overrides)
    response = client.post("/api/v1/products", json=payload, headers=auth_headers(seller_token))
    assert response.status_code == 201, response.text
    return response.json()
