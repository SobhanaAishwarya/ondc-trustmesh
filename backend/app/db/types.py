"""Cross-dialect column types.

Production runs on PostgreSQL (native UUID/ARRAY, as `database/schema.sql`
specifies), but the test suite runs against SQLite so it starts in
milliseconds with no external service. These TypeDecorators pick the native
Postgres type when available and fall back to a portable encoding otherwise,
so the same model definitions produce a correct schema on both — this is
the standard SQLAlchemy recipe for backend-agnostic UUID columns, not a
simplification of the production schema.
"""

import json
import uuid

from sqlalchemy import CHAR, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID


class GUID(TypeDecorator):
    """Platform-independent UUID: native UUID on Postgres, CHAR(36) elsewhere."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


class StringArray(TypeDecorator):
    """TEXT[] on Postgres; JSON-encoded TEXT list elsewhere."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(Text))
        return dialect.type_descriptor(Text)

    def process_bind_param(self, value, dialect):
        if value is None:
            return [] if dialect.name == "postgresql" else "[]"
        if dialect.name == "postgresql":
            return value
        return json.dumps(list(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        if dialect.name == "postgresql":
            return list(value)
        return json.loads(value)
