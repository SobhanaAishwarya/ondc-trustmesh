"""Blockchain bridge tests — run against a REAL local chain, not mocked.

Skipped automatically if nothing answers at BLOCKCHAIN_TEST_RPC_URL
(default http://127.0.0.1:8545). To run these:

    npx hardhat node                                    # in one terminal
    npx hardhat run scripts/deploy.js --network localhost
    pytest tests/test_blockchain_bridge.py -v

These are intentionally separate from the main 96-test suite, which never
needs a live chain — this file is the one place that genuinely does.
"""

import os
import uuid
from unittest.mock import MagicMock

import pytest
import requests
from eth_account import Account

from app.blockchain import client
from app.blockchain.client import BlockchainUnavailable
from app.core.config import Settings
from app.models.buyer import Buyer
from app.models.seller import Seller
from app.services import blockchain_service

RPC_URL = os.environ.get("BLOCKCHAIN_TEST_RPC_URL", "http://127.0.0.1:8545")
# Hardhat's account #0 — a well-known, publicly documented dev-only key
# that ships with every `npx hardhat node`. Never use this key for
# anything but a local ephemeral chain.
OPERATOR_KEY = os.environ.get(
    "BLOCKCHAIN_TEST_PRIVATE_KEY",
    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
)


def _node_is_up() -> bool:
    try:
        response = requests.post(
            RPC_URL, json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}, timeout=1
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


pytestmark = pytest.mark.skipif(
    not _node_is_up(), reason=f"No chain reachable at {RPC_URL} — start one with `npx hardhat node`"
)


@pytest.fixture(autouse=True)
def _blockchain_settings(monkeypatch):
    test_settings = Settings(
        blockchain_enabled=True,
        blockchain_rpc_url=RPC_URL,
        blockchain_network="localhost",
        blockchain_private_key=OPERATOR_KEY,
        database_url="sqlite://",
        jwt_secret_key="test-only-secret-do-not-use-in-prod",
    )
    monkeypatch.setattr("app.blockchain.client.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.services.blockchain_service.get_settings", lambda: test_settings)
    client.reset_cached_connections()
    yield
    client.reset_cached_connections()


def _random_address() -> str:
    """A fresh, never-before-seen address per test — the chain persists
    state across test runs (it's a real node, not reset per test), so
    reusing an address would collide with "already registered"."""
    return Account.create().address


def test_register_and_read_score_round_trip():
    address = _random_address()
    assert client.is_registered_onchain(address) is False

    receipt = client.register_participant(address)

    assert receipt["status"] == 1
    assert receipt["tx_hash"]
    assert client.is_registered_onchain(address) is True
    assert client.get_onchain_score(address) == 50


def test_registering_twice_raises_value_error():
    address = _random_address()
    client.register_participant(address)

    with pytest.raises(ValueError):
        client.register_participant(address)


def test_record_event_moves_the_score_as_documented():
    """Mirrors TrustScore.sol's _deltaFor(): +2 for successful_delivery,
    -20 for fraud_flagged — the same event vocabulary blockchain/chain.py
    (the Streamlit prototype) and app/services/blockchain_service.py use."""
    address = _random_address()
    client.register_participant(address)

    client.record_event(address, "successful_delivery")
    assert client.get_onchain_score(address) == 52

    client.record_event(address, "fraud_flagged")
    assert client.get_onchain_score(address) == 32


def test_score_clamps_at_zero():
    address = _random_address()
    client.register_participant(address)

    for _ in range(5):
        client.record_event(address, "fraud_flagged")

    assert client.get_onchain_score(address) == 0


def test_unreachable_node_raises_blockchain_unavailable(monkeypatch):
    bad_settings = Settings(
        blockchain_enabled=True,
        blockchain_rpc_url="http://127.0.0.1:1",  # nothing listens here
        blockchain_network="localhost",
        blockchain_private_key=OPERATOR_KEY,
        database_url="sqlite://",
        jwt_secret_key="test-only-secret-do-not-use-in-prod",
    )
    monkeypatch.setattr("app.blockchain.client.get_settings", lambda: bad_settings)
    client.reset_cached_connections()

    with pytest.raises(BlockchainUnavailable):
        client.get_web3()


# --- Service layer (app/services/blockchain_service.py), still against the
# real chain above — `db` is a MagicMock since these functions only ever
# call `db.add(...)` on it (never query/commit), so a real session isn't
# needed to prove the service correctly drives the real client + mutates
# the model object it's given. ---


def test_register_seller_onchain_against_a_live_chain():
    seller = Seller(id=uuid.uuid4(), user_id=uuid.uuid4(), business_name="Bridge Test Shop", wallet_address=_random_address())
    db = MagicMock()

    result = blockchain_service.register_seller_onchain(db, seller)

    assert result is not None
    assert seller.is_onchain_registered is True
    db.add.assert_called_once()
    assert client.get_onchain_score(seller.wallet_address) == 50


def test_register_buyer_onchain_against_a_live_chain():
    """Buyer registration parity with sellers — TrustScore.sol's
    register() doesn't distinguish participant roles."""
    buyer = Buyer(id=uuid.uuid4(), user_id=uuid.uuid4(), wallet_address=_random_address())
    db = MagicMock()

    result = blockchain_service.register_buyer_onchain(db, buyer)

    assert result is not None
    assert buyer.is_onchain_registered is True
    db.add.assert_called_once()
    assert client.get_onchain_score(buyer.wallet_address) == 50


def test_register_buyer_onchain_is_idempotent():
    buyer = Buyer(id=uuid.uuid4(), user_id=uuid.uuid4(), wallet_address=_random_address(), is_onchain_registered=True)
    db = MagicMock()

    result = blockchain_service.register_buyer_onchain(db, buyer)

    assert result is None
    db.add.assert_not_called()
