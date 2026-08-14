from app.core.config import Settings


def test_plain_postgres_url_gets_psycopg_driver():
    settings = Settings(database_url="postgres://user:pass@host:5432/db", jwt_secret_key="x")
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/db"


def test_postgresql_url_without_driver_gets_psycopg_driver():
    settings = Settings(database_url="postgresql://user:pass@host:5432/db", jwt_secret_key="x")
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/db"


def test_url_with_explicit_driver_is_left_alone():
    settings = Settings(database_url="postgresql+psycopg://user:pass@host/db", jwt_secret_key="x")
    assert settings.database_url == "postgresql+psycopg://user:pass@host/db"


def test_sqlite_url_is_left_alone():
    settings = Settings(database_url="sqlite://", jwt_secret_key="x")
    assert settings.database_url == "sqlite://"
