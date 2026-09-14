from tests.helpers import auth_headers, create_product, register_buyer, register_seller


def test_compare_ranks_the_cheaper_equally_placed_seller_as_best_match(client):
    buyer = register_buyer(client, city="Mumbai")
    cheap_seller = register_seller(client, email="cheap@example.com", business_name="Cheap Co", city="Mumbai")
    pricey_seller = register_seller(client, email="pricey@example.com", business_name="Pricey Co", city="Mumbai")

    create_product(client, cheap_seller["access_token"], name="Smartwatch", price="1999.00", stock_quantity=50)
    create_product(client, pricey_seller["access_token"], name="Smartwatch", price="4999.00", stock_quantity=50)

    response = client.get(
        "/api/v1/products/compare", params={"name": "Smartwatch"}, headers=auth_headers(buyer["access_token"])
    )

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2
    assert results[0]["seller_name"] == "Cheap Co"
    assert results[0]["is_best_match"] is True
    assert results[1]["is_best_match"] is False
    assert results[0]["match_score"] > results[1]["match_score"]


def test_compare_is_case_insensitive_and_trims_whitespace(client):
    buyer = register_buyer(client)
    seller = register_seller(client)
    create_product(client, seller["access_token"], name="Yoga Mat")

    response = client.get(
        "/api/v1/products/compare", params={"name": "  yoga mat  "}, headers=auth_headers(buyer["access_token"])
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_compare_returns_an_empty_list_for_an_unknown_product(client):
    buyer = register_buyer(client)

    response = client.get(
        "/api/v1/products/compare", params={"name": "Nonexistent Gadget"}, headers=auth_headers(buyer["access_token"])
    )

    assert response.status_code == 200
    assert response.json() == []


def test_compare_excludes_deactivated_listings(client):
    buyer = register_buyer(client)
    seller = register_seller(client)
    product = create_product(client, seller["access_token"], name="Desk Lamp")
    client.delete(f"/api/v1/products/{product['id']}", headers=auth_headers(seller["access_token"]))

    response = client.get(
        "/api/v1/products/compare", params={"name": "Desk Lamp"}, headers=auth_headers(buyer["access_token"])
    )

    assert response.json() == []


def test_exactly_one_listing_is_flagged_best_match_among_several(client):
    buyer = register_buyer(client, city="Delhi")
    for i in range(4):
        seller = register_seller(client, email=f"seller{i}@example.com", business_name=f"Seller {i}", city="Delhi")
        create_product(client, seller["access_token"], name="Backpack", price=str(999 + i * 200))

    response = client.get(
        "/api/v1/products/compare", params={"name": "Backpack"}, headers=auth_headers(buyer["access_token"])
    )

    results = response.json()
    assert len(results) == 4
    assert sum(1 for r in results if r["is_best_match"]) == 1
    # Descending match score, since results are returned ranked best-first.
    scores = [r["match_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_compare_requires_buyer_authentication(client):
    seller = register_seller(client)
    create_product(client, seller["access_token"], name="Backpack")

    response = client.get("/api/v1/products/compare", params={"name": "Backpack"})

    assert response.status_code == 401
