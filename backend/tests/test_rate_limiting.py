"""Rate limiting on the brute-force-prone auth endpoints. The
`_reset_rate_limits` autouse fixture in conftest.py clears the limiter's
counters before/after each test — without it, these limits would carry
over between tests sharing the same TestClient fake remote address and
break unrelated tests, not just these ones.
"""


def test_login_endpoint_rate_limits_after_repeated_attempts(client):
    for _ in range(5):  # matches @limiter.limit("5/minute") on /auth/login
        response = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
        assert response.status_code == 401

    response = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert response.status_code == 429


def test_register_buyer_endpoint_rate_limits_after_repeated_attempts(client):
    for i in range(10):  # matches @limiter.limit("10/hour") on /auth/register/buyer
        response = client.post(
            "/api/v1/auth/register/buyer",
            json={"email": f"ratelimit{i}@example.com", "password": "buyerpass123", "full_name": "Rate Limit Test"},
        )
        assert response.status_code == 201, response.text

    response = client.post(
        "/api/v1/auth/register/buyer",
        json={"email": "one-too-many@example.com", "password": "buyerpass123", "full_name": "One Too Many"},
    )
    assert response.status_code == 429


def test_rate_limiting_is_scoped_per_endpoint_not_global(client):
    """Hitting the tight login limit shouldn't lock out an unrelated
    endpoint — each route has its own limit."""
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"}).status_code == 429

    # /products is a read endpoint under the 120/minute default, nowhere
    # near exhausted by five login attempts.
    response = client.get("/api/v1/products")
    assert response.status_code == 200
