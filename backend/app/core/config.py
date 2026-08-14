"""Application settings, loaded from environment variables / .env.

Every other module reads configuration through `get_settings()` rather than
`os.environ` directly, so the whole app has one validated source of truth
and tests can override it by constructing a `Settings(...)` instance.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ondc_blockchain_ai/ — trained_models/ and datasets/ are siblings of backend/,
# matching the project's top-level folder layout.
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str = "postgresql+psycopg://ondc:ondc@localhost:5432/ondc_ai"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "change-me-to-a-random-64-byte-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    fraud_model_path: str = str(REPO_ROOT / "trained_models" / "fraud_model.joblib")
    fraud_flag_threshold: float = 0.5

    # Off by default — most dev/test runs have no chain up, and the main
    # test suite never needs one. Flip on + point at a running node
    # (`npx hardhat node`, deployed via scripts/deploy.js) to exercise it.
    blockchain_enabled: bool = False
    blockchain_rpc_url: str = "http://127.0.0.1:8545"
    blockchain_network: str = "localhost"
    blockchain_private_key: str | None = None
    blockchain_trust_score_address: str | None = None
    blockchain_escrow_address: str | None = None

    @field_validator("database_url")
    @classmethod
    def _normalize_postgres_driver(cls, value: str) -> str:
        """Managed Postgres providers (Render, Railway, Heroku-style) hand
        out a plain `postgresql://` or `postgres://` URL with no driver —
        SQLAlchemy 1.4+ needs an explicit one. Rewriting it here means a
        deployment's DATABASE_URL env var can be pasted in verbatim rather
        than requiring every environment to remember to add `+psycopg`."""
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
