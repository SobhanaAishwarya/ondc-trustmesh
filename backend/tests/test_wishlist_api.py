from tests.helpers import auth_headers, create_product, register_buyer, register_seller


def test_add_and_list_wishlist(client):
    seller = register_seller(client)
    product = create_product(client, seller["access_token"])
    buyer = register_buyer(client)

    add_response = client.post(
        "/api/v1/wishlist", json={"product_id": product["id"]}, headers=auth_headers(buyer["access_token"])
    )
    assert add_response.status_code == 201

    listing = client.get("/api/v1/wishlist", headers=auth_headers(buyer["access_token"])).json()
    assert len(listing) == 1
    assert listing[0]["product"]["id"] == product["id"]


def test_duplicate_wishlist_add_is_rejected(client):
    seller = register_seller(client)
    product = create_product(client, seller["access_token"])
    buyer = register_buyer(client)

    client.post("/api/v1/wishlist", json={"product_id": product["id"]}, headers=auth_headers(buyer["access_token"]))
    response = client.post(
        "/api/v1/wishlist", json={"product_id": product["id"]}, headers=auth_headers(buyer["access_token"])
    )
    assert response.status_code == 400


def test_remove_from_wishlist(client):
    seller = register_seller(client)
    product = create_product(client, seller["access_token"])
    buyer = register_buyer(client)
    client.post("/api/v1/wishlist", json={"product_id": product["id"]}, headers=auth_headers(buyer["access_token"]))

    response = client.delete(f"/api/v1/wishlist/{product['id']}", headers=auth_headers(buyer["access_token"]))
    assert response.status_code == 204

    listing = client.get("/api/v1/wishlist", headers=auth_headers(buyer["access_token"])).json()
    assert listing == []


def test_removing_something_not_in_wishlist_is_not_found(client):
    seller = register_seller(client)
    product = create_product(client, seller["access_token"])
    buyer = register_buyer(client)

    response = client.delete(f"/api/v1/wishlist/{product['id']}", headers=auth_headers(buyer["access_token"]))
    assert response.status_code == 404


def test_wishlist_requires_buyer_role(client):
    seller = register_seller(client)
    product = create_product(client, seller["access_token"])

    response = client.post(
        "/api/v1/wishlist", json={"product_id": product["id"]}, headers=auth_headers(seller["access_token"])
    )
    assert response.status_code == 403
