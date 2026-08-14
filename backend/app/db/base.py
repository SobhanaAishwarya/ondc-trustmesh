from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base — every model in app.models inherits this so
    a single `Base.metadata` describes the whole schema for Alembic
    autogenerate and for `create_all()` in tests."""
