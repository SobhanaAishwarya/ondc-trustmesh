"""Test fixtures.

The backend targets Postgres in production (see database/schema.sql), but
tests run against an in-memory SQLite DB via the portable GUID/StringArray
types in app/db/types.py, so the whole test suite runs in-process with no
external services — no docker-compose, no network. Set env vars before
importing anything under `app` since `get_settings()` is cached on first call.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-do-not-use-in-prod")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401 — populates Base.metadata
from app.core.limiter import limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _fresh_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """The rate limiter's counters live in a process-wide in-memory store
    (app/core/limiter.py's `limiter` singleton), not per-request state —
    without resetting it, tests that repeatedly hit /auth/register or
    /auth/login (most of this suite) would start tripping 429s partway
    through the run, since TestClient's requests all share one fake
    remote-address key. Reset before *and* after so a failed test doesn't
    leave the counters dirty for the next one either."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fake_redis(monkeypatch):
    """Installs an in-memory stand-in for app.core.cache's Redis client so
    caching/refresh-token-revocation logic can be exercised without a live
    Redis instance. Only used by tests that explicitly ask for it — the
    rest of the suite deliberately runs with caching/revocation disabled
    (see app/core/cache.py's fail-open design) to prove the app works
    with zero external services, same as the Postgres-free SQLite setup
    above."""
    import app.core.cache as cache_module

    class _FakeRedis:
        def __init__(self):
            self.store: dict[str, str] = {}

        def get(self, key):
            return self.store.get(key)

        def setex(self, key, ttl, value):
            self.store[key] = value

        def delete(self, *keys):
            for key in keys:
                self.store.pop(key, None)

        def incr(self, key):
            self.store[key] = str(int(self.store.get(key, "0")) + 1)

        def exists(self, key):
            return 1 if key in self.store else 0

    fake = _FakeRedis()
    monkeypatch.setattr(cache_module, "_client", fake)
    monkeypatch.setattr(cache_module, "_client_initialized", True)
    yield fake


@pytest.fixture
def admin_token():
    """There's no public admin-registration endpoint by design (see
    app/api/v1/endpoints/auth.py), so tests create one directly in the DB —
    the same out-of-band path scripts/create_admin.py uses in production."""
    from app.core.security import create_access_token
    from app.models.user import User, UserRole

    db = TestingSessionLocal()
    try:
        admin = User(
            email="admin@example.com",
            password_hash="not-used-in-tests",
            full_name="Test Admin",
            role=UserRole.admin,
            is_verified=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return create_access_token(admin.id, admin.role.value)
    finally:
        db.close()
