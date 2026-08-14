from tests.helpers import auth_headers, create_product, register_buyer, register_seller


def test_create_product_requires_seller_role(client):
    buyer = register_buyer(client)
    response = client.post(
        "/api/v1/products",
        json={"name": "X", "category": "misc", "price": "10.00", "stock_quantity": 1},
        headers=auth_headers(buyer["access_token"]),
    )
    assert response.status_code == 403


def test_create_product_success(client):
    seller = register_seller(client)
    product = create_product(client, seller["access_token"], name="Bluetooth Speaker", price="49.99")
    assert product["name"] == "Bluetooth Speaker"
    assert product["price"] == "49.99"
    assert product["is_active"] is True


def test_list_products_only_shows_active(client):
    seller = register_seller(client)
    active = create_product(client, seller["access_token"], name="Active Item")
    inactive = create_product(client, seller["access_token"], name="Inactive Item")
    client.delete(f"/api/v1/products/{inactive['id']}", headers=auth_headers(seller["access_token"]))

    response = client.get("/api/v1/products")

    assert response.status_code == 200
    names = [p["name"] for p in response.json()["items"]]
    assert "Active Item" in names
    assert "Inactive Item" not in names


def test_list_products_filters_by_category_and_search(client):
    seller = register_seller(client)
    create_product(client, seller["access_token"], name="Red Shoes", category="footwear")
    create_product(client, seller["access_token"], name="Blue Shirt", category="apparel")

    by_category = client.get("/api/v1/products", params={"category": "footwear"}).json()
    assert [p["name"] for p in by_category["items"]] == ["Red Shoes"]

    by_search = client.get("/api/v1/products", params={"q": "shirt"}).json()
    assert [p["name"] for p in by_search["items"]] == ["Blue Shirt"]


def test_get_product_not_found(client):
    response = client.get("/api/v1/products/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_product_by_owner_succeeds(client):
    seller = register_seller(client)
    product = create_product(client, seller["access_token"])

    response = client.patch(
        f"/api/v1/products/{product['id']}",
        json={"price": "9.99", "stock_quantity": 3},
        headers=auth_headers(seller["access_token"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["price"] == "9.99"
    assert body["stock_quantity"] == 3


def test_update_product_by_non_owner_is_forbidden(client):
    owner = register_seller(client, email="owner@example.com")
    other = register_seller(client, email="other@example.com", business_name="Other Shop")
    product = create_product(client, owner["access_token"])

    response = client.patch(
        f"/api/v1/products/{product['id']}", json={"price": "1.00"}, headers=auth_headers(other["access_token"])
    )

    assert response.status_code == 403


def test_list_my_products_includes_inactive(client):
    seller = register_seller(client)
    product = create_product(client, seller["access_token"])
    client.delete(f"/api/v1/products/{product['id']}", headers=auth_headers(seller["access_token"]))

    response = client.get("/api/v1/products/mine", headers=auth_headers(seller["access_token"]))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["is_active"] is False
