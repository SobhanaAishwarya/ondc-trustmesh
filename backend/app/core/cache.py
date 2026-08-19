"""Thin Redis wrapper for hot-read caching, refresh-token revocation, and
wallet sign-in nonces.

Fails open, the same way `app/services/blockchain_service.py` no-ops when
the chain isn't reachable: if Redis is down or `REDIS_URL` points nowhere,
most functions here become a silent no-op (cache misses always, tokens
are never "found revoked") rather than raising. That's a deliberate
tradeoff, not an oversight — see the docstring on `blocklist_contains`
for the one place it actually matters. The `wallet_nonce_*` functions
below are the one deliberate exception: they fail *closed*
(`NonceStoreUnavailable`), since a nonce is the actual security check for
wallet sign-in, not an optional side effect.

The client is connected lazily on first use and cached at module scope —
tests never touch a real Redis instance (`get_settings().redis_url`
resolves to a host nothing is listening on in CI/local pytest runs), so
the one connection attempt fails fast (short timeouts below) and every
subsequent call short-circuits on `_client is None`.
"""

import logging

import redis

from app.core.config import get_settings

logger = logging.getLogger("app.cache")

_client: "redis.Redis | None" = None
_client_initialized = False


def get_redis() -> "redis.Redis | None":
    global _client, _client_initialized
    if not _client_initialized:
        _client_initialized = True
        try:
            candidate = redis.Redis.from_url(
                get_settings().redis_url,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
                decode_responses=True,
            )
            candidate.ping()
            _client = candidate
        except redis.RedisError:
            logger.warning("Redis not reachable — caching and refresh-token revocation are disabled this run")
            _client = None
    return _client


def reset_for_tests() -> None:
    """Lets tests force a fresh connection attempt (e.g. against a fake
    client) instead of reusing whatever the first call in the process
    resolved to."""
    global _client, _client_initialized
    _client = None
    _client_initialized = False


def cache_get(key: str) -> str | None:
    client = get_redis()
    if client is None:
        return None
    try:
        return client.get(key)
    except redis.RedisError:
        return None


def cache_set(key: str, value: str, ttl_seconds: int) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        client.setex(key, max(1, ttl_seconds), value)
    except redis.RedisError:
        pass


def cache_delete(*keys: str) -> None:
    client = get_redis()
    if client is None or not keys:
        return
    try:
        client.delete(*keys)
    except redis.RedisError:
        pass


def cache_incr(key: str) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        client.incr(key)
    except redis.RedisError:
        pass


def blocklist_add(jti: str, ttl_seconds: float) -> None:
    """Marks a refresh token's id as spent/revoked until its own natural
    expiry — no need to remember it any longer than the JWT itself would
    still pass its `exp` check."""
    client = get_redis()
    if client is None or ttl_seconds <= 0:
        return
    try:
        client.setex(f"revoked_jti:{jti}", int(ttl_seconds) + 1, "1")
    except redis.RedisError:
        pass


def blocklist_contains(jti: str) -> bool:
    """Fails open (returns False, i.e. "not revoked") when Redis is
    unreachable. This means revocation isn't enforced if the cache is
    down — an explicit, documented tradeoff (matches this project's
    blockchain-bridge no-op pattern) rather than making refresh/login
    itself depend on Redis being up."""
    client = get_redis()
    if client is None:
        return False
    try:
        return client.exists(f"revoked_jti:{jti}") == 1
    except redis.RedisError:
        return False


class NonceStoreUnavailable(Exception):
    """Raised instead of failing open. A wallet-auth nonce is the actual
    security check for that flow, not an optional side effect like caching
    or revocation above — an unreachable Redis must stop wallet sign-in
    with a clear error, not silently accept an unverifiable signature."""


def wallet_nonce_set(address: str, nonce: str, ttl_seconds: int) -> None:
    client = get_redis()
    if client is None:
        raise NonceStoreUnavailable("Redis is required for wallet sign-in and is not reachable")
    try:
        client.setex(f"wallet_nonce:{address.lower()}", max(1, ttl_seconds), nonce)
    except redis.RedisError as exc:
        raise NonceStoreUnavailable("Redis is required for wallet sign-in and is not reachable") from exc


def wallet_nonce_pop(address: str) -> str | None:
    """Single-use: read-then-delete. A get+delete race could in principle
    let a second signature over the same nonce through in a narrow window,
    but that window only matters against a nonce that's about to expire
    anyway (TTL is minutes, not hours) — an accepted tradeoff rather than
    reaching for a Lua script/transaction for a demo-scale threat model."""
    client = get_redis()
    if client is None:
        raise NonceStoreUnavailable("Redis is required for wallet sign-in and is not reachable")
    key = f"wallet_nonce:{address.lower()}"
    try:
        value = client.get(key)
        if value is not None:
            client.delete(key)
        return value
    except redis.RedisError as exc:
        raise NonceStoreUnavailable("Redis is required for wallet sign-in and is not reachable") from exc
