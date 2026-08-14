"""Web3.py bridge to the deployed TrustScore/EscrowDispute contracts.

On-chain sync is best-effort, not a hard dependency: every function here
either succeeds or raises `BlockchainUnavailable`/a Web3 error — callers
(services/blockchain_service.py) catch those so a down or unconfigured
chain never breaks placing an order, delivering one, or resolving a
dispute. Those are the actual product; the chain write is a side effect.
Gated by `BLOCKCHAIN_ENABLED` (off by default — most dev/test runs have no
node up, and the 96-test main suite never needs one).

Contract addresses come from `deployments/<network>.json`, written by
`scripts/deploy.js` — not hardcoded, so pointing at a fresh local deploy or
at Sepolia is just an env var change (`BLOCKCHAIN_NETWORK`), not a code
change.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

from web3 import Web3
from web3.contract import Contract

from app.core.config import REPO_ROOT, get_settings

logger = logging.getLogger(__name__)

TRUST_SCORE_ARTIFACT = REPO_ROOT / "artifacts" / "contracts" / "TrustScore.sol" / "TrustScore.json"
ESCROW_ARTIFACT = REPO_ROOT / "artifacts" / "contracts" / "EscrowDispute.sol" / "EscrowDispute.json"


class BlockchainUnavailable(Exception):
    """The chain isn't enabled, configured, or reachable right now."""


def _load_abi(artifact_path: Path) -> list:
    if not artifact_path.exists():
        raise BlockchainUnavailable(
            f"Contract artifact missing at {artifact_path} — run `npx hardhat compile` in the repo root"
        )
    with open(artifact_path) as f:
        return json.load(f)["abi"]


def _load_deployment(network: str) -> dict:
    path = REPO_ROOT / "deployments" / f"{network}.json"
    if not path.exists():
        raise BlockchainUnavailable(
            f"No deployment file for network '{network}' at {path} — "
            f"run `npx hardhat run scripts/deploy.js --network {network}`"
        )
    with open(path) as f:
        return json.load(f)


@lru_cache
def get_web3() -> Web3:
    settings = get_settings()
    if not settings.blockchain_enabled:
        raise BlockchainUnavailable("BLOCKCHAIN_ENABLED is false")

    w3 = Web3(Web3.HTTPProvider(settings.blockchain_rpc_url, request_kwargs={"timeout": 5}))
    if not w3.is_connected():
        raise BlockchainUnavailable(f"Cannot reach RPC at {settings.blockchain_rpc_url}")
    return w3


@lru_cache
def get_operator_account():
    settings = get_settings()
    if not settings.blockchain_private_key:
        raise BlockchainUnavailable("BLOCKCHAIN_PRIVATE_KEY is not set")
    return get_web3().eth.account.from_key(settings.blockchain_private_key)


@lru_cache
def get_trust_score_contract() -> Contract:
    settings = get_settings()
    w3 = get_web3()
    address = settings.blockchain_trust_score_address or _load_deployment(settings.blockchain_network)[
        "contracts"
    ]["TrustScore"]
    return w3.eth.contract(address=Web3.to_checksum_address(address), abi=_load_abi(TRUST_SCORE_ARTIFACT))


@lru_cache
def get_escrow_contract() -> Contract:
    settings = get_settings()
    w3 = get_web3()
    address = settings.blockchain_escrow_address or _load_deployment(settings.blockchain_network)[
        "contracts"
    ]["EscrowDispute"]
    return w3.eth.contract(address=Web3.to_checksum_address(address), abi=_load_abi(ESCROW_ARTIFACT))


def reset_cached_connections() -> None:
    """Test hook — clears the lru_cache'd Web3/account/contract singletons
    so a new BLOCKCHAIN_* config takes effect."""
    get_web3.cache_clear()
    get_operator_account.cache_clear()
    get_trust_score_contract.cache_clear()
    get_escrow_contract.cache_clear()


def _send(function_call, account) -> dict:
    w3 = get_web3()
    tx = function_call.build_transaction(
        {"from": account.address, "nonce": w3.eth.get_transaction_count(account.address)}
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    return {"tx_hash": receipt.transactionHash.hex(), "block_number": receipt.blockNumber, "status": receipt.status}


def is_registered_onchain(address: str) -> bool:
    contract = get_trust_score_contract()
    return contract.functions.registered(Web3.to_checksum_address(address)).call()


def register_participant(address: str) -> dict:
    contract = get_trust_score_contract()
    account = get_operator_account()
    checksum = Web3.to_checksum_address(address)
    if contract.functions.registered(checksum).call():
        raise ValueError(f"{checksum} is already registered on-chain")
    return _send(contract.functions.register(checksum), account)


def record_event(address: str, event_type: str) -> dict:
    contract = get_trust_score_contract()
    account = get_operator_account()
    return _send(contract.functions.recordEvent(Web3.to_checksum_address(address), event_type), account)


def get_onchain_score(address: str) -> int:
    contract = get_trust_score_contract()
    return contract.functions.scoreOf(Web3.to_checksum_address(address)).call()
