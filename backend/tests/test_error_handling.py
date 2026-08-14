"""The global exception handlers in app/main.py — validation errors get a
consistent {"detail": ..., "errors": [...]} envelope rather than FastAPI's
default bare array under "detail", so a client branching on the `detail`
field doesn't need a special case for 422s specifically. The unhandled-
exception (500) handler isn't covered here — triggering a genuine bug on
demand would mean contriving one, which isn't a real regression test.
"""


def test_validation_error_uses_the_consistent_error_envelope(client):
    response = client.post("/api/v1/auth/register/buyer", json={"email": "not-an-email", "password": "short"})

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "Validation error"
    assert isinstance(body["errors"], list)
    assert len(body["errors"]) > 0


def test_missing_required_field_uses_the_same_envelope(client):
    response = client.post("/api/v1/auth/register/buyer", json={"password": "buyerpass123"})

    assert response.status_code == 422
    assert response.json()["detail"] == "Validation error"


def test_every_response_carries_a_request_id_header(client):
    response = client.get("/health")
    assert "x-request-id" in {k.lower() for k in response.headers}
