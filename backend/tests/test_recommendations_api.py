from tests.helpers import auth_headers, create_product, register_buyer, register_seller


def test_no_products_means_no_recommendations(client):
    buyer = register_buyer(client)
    response = client.get("/api/v1/recommendations", headers=auth_headers(buyer["access_token"]))
    assert response.status_code == 200
    assert response.json() == []


def test_cold_start_buyer_gets_popularity_fallback(client):
    seller = register_seller(client)
    create_product(client, seller["access_token"], name="Something", category="Misc")
    buyer = register_buyer(client, preferred_categories=[])

    response = client.get("/api/v1/recommendations", headers=auth_headers(buyer["access_token"]))

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["algorithm"] == "popularity_cold_start"


def test_content_based_recommendation_favors_matching_category(client):
    seller = register_seller(client)
    create_product(client, seller["access_token"], name="Laptop", category="Electronics", tags=["electronics"])
    create_product(client, seller["access_token"], name="Novel", category="Books", tags=["books"])
    buyer = register_buyer(client, preferred_categories=["Electronics"])

    response = client.get("/api/v1/recommendations", headers=auth_headers(buyer["access_token"]))

    items = response.json()
    assert items[0]["product"]["name"] == "Laptop"
    assert items[0]["algorithm"] == "hybrid"
    assert items[0]["distance_km"] is None  # neither buyer nor seller set a city


def test_proximity_favors_the_nearer_seller_when_everything_else_ties(client):
    near_seller = register_seller(client, email="near@example.com", business_name="Near Shop", city="Mumbai")
    far_seller = register_seller(client, email="far@example.com", business_name="Far Shop", city="Chennai")
    near_product = create_product(
        client, near_seller["access_token"], name="Phone", category="Electronics", tags=["electronics"]
    )
    create_product(client, far_seller["access_token"], name="Phone", category="Electronics", tags=["electronics"])
    buyer = register_buyer(client, preferred_categories=["Electronics"], city="Mumbai")

    response = client.get("/api/v1/recommendations", headers=auth_headers(buyer["access_token"]))

    items = response.json()
    assert items[0]["product"]["id"] == near_product["id"]
    assert items[0]["distance_km"] == 0.0
    assert items[0]["estimated_delivery_days"] == 1
    assert items[1]["distance_km"] > 500


def test_register_rejects_unknown_city(client):
    response = client.post(
        "/api/v1/auth/register/buyer",
        json={
            "email": "badcity@example.com",
            "password": "buyerpass123",
            "full_name": "Bee Yer",
            "city": "Atlantis",
        },
    )
    assert response.status_code == 422


def test_click_marks_recommendation_as_clicked(client, admin_token):
    seller = register_seller(client)
    create_product(client, seller["access_token"])
    buyer = register_buyer(client)

    rec_id = client.get("/api/v1/recommendations", headers=auth_headers(buyer["access_token"])).json()[0]["id"]
    click_response = client.post(f"/api/v1/recommendations/{rec_id}/click", headers=auth_headers(buyer["access_token"]))
    assert click_response.status_code == 204

    report = client.get("/api/v1/recommendations/ctr", headers=auth_headers(admin_token)).json()
    assert report["clicks"] >= 1
    assert report["ctr"] > 0


def test_click_on_someone_elses_recommendation_is_not_found(client):
    seller = register_seller(client)
    create_product(client, seller["access_token"])
    buyer_a = register_buyer(client, email="a@example.com")
    buyer_b = register_buyer(client, email="b@example.com")

    rec_id = client.get("/api/v1/recommendations", headers=auth_headers(buyer_a["access_token"])).json()[0]["id"]

    response = client.post(f"/api/v1/recommendations/{rec_id}/click", headers=auth_headers(buyer_b["access_token"]))
    assert response.status_code == 404


def test_purchasing_a_recommended_product_marks_it_purchased(client, admin_token):
    seller = register_seller(client)
    product = create_product(client, seller["access_token"], stock_quantity=5)
    buyer = register_buyer(client)

    recs = client.get("/api/v1/recommendations", headers=auth_headers(buyer["access_token"])).json()
    algorithm = recs[0]["algorithm"]

    client.post(
        "/api/v1/orders",
        json={"product_id": product["id"], "quantity": 1, "payment_method": "upi"},
        headers=auth_headers(buyer["access_token"]),
    )

    report = client.get(
        "/api/v1/recommendations/ctr", params={"algorithm": algorithm}, headers=auth_headers(admin_token)
    ).json()
    assert report["purchases"] >= 1


def test_ctr_endpoint_requires_admin(client):
    seller = register_seller(client)
    response = client.get("/api/v1/recommendations/ctr", headers=auth_headers(seller["access_token"]))
    assert response.status_code == 403
