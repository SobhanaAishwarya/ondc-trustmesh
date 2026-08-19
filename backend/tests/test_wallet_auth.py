"""Wallet sign-in: nonce -> sign -> link/login. Uses real eth_account
keypairs and real signatures throughout — the whole point of this feature
is a genuine cryptographic proof of address ownership, so faking the
signature would test nothing real.
"""

from eth_account import Account
from eth_account.messages import encode_defunct


def _register_buyer(client, email="walletbuyer@example.com"):
    return client.post(
        "/api/v1/auth/register/buyer",
        json={"email": email, "password": "buyerpass123", "full_name": "Wallet Buyer"},
    )


def _register_seller(client, email="walletseller@example.com"):
    return client.post(
        "/api/v1/auth/register/seller",
        json={"email": email, "password": "sellerpass123", "full_name": "Wallet Seller", "business_name": "Wallet Shop"},
    )


def _sign_challenge(client, account, fake_redis):
    """Requests a nonce for `account.address` and signs the returned
    message with its real private key. Returns (address, signature_hex)."""
    nonce_response = client.post("/api/v1/auth/wallet/nonce", json={"address": account.address})
    assert nonce_response.status_code == 200
    message = nonce_response.json()["message"]

    signed = Account.sign_message(encode_defunct(text=message), private_key=account.key)
    return account.address, signed.signature.hex()


def test_wallet_nonce_returns_a_message_containing_the_address(client, fake_redis):
    account = Account.create()

    response = client.post("/api/v1/auth/wallet/nonce", json={"address": account.address})

    assert response.status_code == 200
    assert account.address in response.json()["message"]


def test_link_wallet_requires_a_real_signature(client, fake_redis):
    token = _register_buyer(client).json()["access_token"]
    account = Account.create()
    address, signature = _sign_challenge(client, account, fake_redis)

    response = client.post(
        "/api/v1/auth/wallet/link",
        json={"address": address, "signature": signature},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["buyer"]["wallet_address"] == address
    assert body["buyer"]["wallet_verified"] is True


def test_link_wallet_rejects_a_signature_from_a_different_key(client, fake_redis):
    token = _register_buyer(client, email="mismatch@example.com").json()["access_token"]
    claimed = Account.create()
    actual_signer = Account.create()

    # Get a nonce for the address we'll *claim*, but sign it with a
    # different private key entirely — the classic forged-ownership attempt.
    nonce_response = client.post("/api/v1/auth/wallet/nonce", json={"address": claimed.address})
    message = nonce_response.json()["message"]
    signed = Account.sign_message(encode_defunct(text=message), private_key=actual_signer.key)

    response = client.post(
        "/api/v1/auth/wallet/link",
        json={"address": claimed.address, "signature": signed.signature.hex()},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_link_wallet_rejects_reusing_a_nonce_twice(client, fake_redis):
    """The nonce is single-use — signing the same message twice and
    replaying the first signature after it's already been consumed must
    not work a second time."""
    token = _register_buyer(client, email="replay@example.com").json()["access_token"]
    account = Account.create()
    address, signature = _sign_challenge(client, account, fake_redis)

    first = client.post(
        "/api/v1/auth/wallet/link",
        json={"address": address, "signature": signature},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 200

    replay = client.post(
        "/api/v1/auth/wallet/link",
        json={"address": address, "signature": signature},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert replay.status_code == 400
    assert "fresh challenge" in replay.json()["detail"]


def test_link_wallet_rejects_a_wallet_already_verified_on_another_account(client, fake_redis):
    token_a = _register_buyer(client, email="ownerA@example.com").json()["access_token"]
    token_b = _register_buyer(client, email="ownerB@example.com").json()["access_token"]
    account = Account.create()

    address, signature = _sign_challenge(client, account, fake_redis)
    first = client.post(
        "/api/v1/auth/wallet/link",
        json={"address": address, "signature": signature},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert first.status_code == 200

    address2, signature2 = _sign_challenge(client, account, fake_redis)
    second = client.post(
        "/api/v1/auth/wallet/link",
        json={"address": address2, "signature": signature2},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert second.status_code == 409


def test_wallet_login_issues_real_tokens_once_linked(client, fake_redis):
    token = _register_seller(client, email="loginseller@example.com").json()["access_token"]
    account = Account.create()

    address, signature = _sign_challenge(client, account, fake_redis)
    link = client.post(
        "/api/v1/auth/wallet/link",
        json={"address": address, "signature": signature},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert link.status_code == 200

    login_address, login_signature = _sign_challenge(client, account, fake_redis)
    login = client.post("/api/v1/auth/wallet/login", json={"address": login_address, "signature": login_signature})

    assert login.status_code == 200
    body = login.json()
    assert body["role"] == "seller"
    assert body["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["seller"]["wallet_address"] == address


def test_wallet_login_rejects_an_unlinked_address(client, fake_redis):
    account = Account.create()
    address, signature = _sign_challenge(client, account, fake_redis)

    response = client.post("/api/v1/auth/wallet/login", json={"address": address, "signature": signature})

    assert response.status_code == 401
    assert "log in with a password" in response.json()["detail"]


def test_wallet_login_without_redis_fails_closed_not_open(client):
    """No fake_redis fixture here — Redis is genuinely unreachable in this
    test's environment. A wallet-auth nonce request must return a clear
    503, never silently accept an unverifiable request."""
    account = Account.create()

    response = client.post("/api/v1/auth/wallet/nonce", json={"address": account.address})

    assert response.status_code == 503
