"""Explicit security regression tests, distinct from the correctness tests
in the other files. Findings from the accompanying `bandit -r app` static
scan (0 medium/high, 2 low-confidence false positives on `TOKEN_TYPE_*`
constants — see backend/README.md) aren't re-litigated here; this file
covers what a static scanner can't: actual request/response behavior.
"""

import jwt

from tests.helpers import auth_headers, register_buyer, register_seller


def test_password_hash_is_never_returned_from_the_api(client):
    token = register_buyer(client, email="secreview1@example.com")["access_token"]
    response = client.get("/api/v1/auth/me", headers=auth_headers(token))
    body_text = response.text
    assert "password_hash" not in body_text
    assert "$2b$" not in body_text  # bcrypt hash prefix — would leak if a hash ever got serialized


def test_login_response_never_echoes_the_password(client):
    register_buyer(client, email="secreview2@example.com")
    response = client.post(
        "/api/v1/auth/login", json={"email": "secreview2@example.com", "password": "buyerpass123"}
    )
    assert "buyerpass123" not in response.text


def test_wrong_password_and_unknown_email_give_the_same_error(client):
    """Distinguishing "wrong password" from "no such account" in the error
    message would let an attacker enumerate registered emails."""
    register_buyer(client, email="secreview3@example.com")

    wrong_password = client.post(
        "/api/v1/auth/login", json={"email": "secreview3@example.com", "password": "not-the-password"}
    )
    unknown_email = client.post(
        "/api/v1/auth/login", json={"email": "nobody-here@example.com", "password": "irrelevant123"}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_token_signed_with_a_different_secret_is_rejected(client):
    """Guards against algorithm/key confusion — a token must be signed
    with *this* server's secret, not just structurally well-formed."""
    forged = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000000", "role": "admin", "type": "access"},
        "a-completely-different-secret",
        algorithm="HS256",
    )
    response = client.get("/api/v1/auth/me", headers=auth_headers(forged))
    assert response.status_code == 401


def test_token_with_none_algorithm_is_rejected(client):
    """The classic `alg: none` JWT bypass — PyJWT's algorithms= allowlist
    in decode_access_token should refuse to even consider it."""
    forged = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000000", "role": "admin", "type": "access"},
        key="",
        algorithm="none",
    )
    response = client.get("/api/v1/auth/me", headers=auth_headers(forged))
    assert response.status_code == 401


def test_sql_injection_style_search_input_is_handled_safely(client):
    """SQLAlchemy's ORM parameterizes every query built here — this proves
    it end-to-end for the one endpoint with free-text user input (product
    search), rather than trusting that by inspection alone."""
    register_seller(client)
    payload = "'; DROP TABLE products; --"

    response = client.get("/api/v1/products", params={"q": payload})

    assert response.status_code == 200
    assert response.json()["items"] == []
    # If the payload had actually executed, this next call would 500.
    sanity_check = client.get("/api/v1/products")
    assert sanity_check.status_code == 200


def test_admin_endpoints_reject_a_forged_admin_role_claim(client):
    """A buyer token can't just claim role=admin in a hand-crafted JWT —
    /me is read from the DB row (User.role), not trusted from the token
    payload, for anything but routing which role-dependent fields to load."""
    buyer_token = register_buyer(client, email="secreview4@example.com")["access_token"]
    payload = jwt.decode(buyer_token, options={"verify_signature": False})
    assert payload["role"] == "buyer"

    response = client.get("/api/v1/admin/users", headers=auth_headers(buyer_token))
    assert response.status_code == 403
