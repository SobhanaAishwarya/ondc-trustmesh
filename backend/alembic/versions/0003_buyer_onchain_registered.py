"""add buyers.is_onchain_registered

sellers.is_onchain_registered has existed since the blockchain-bridge
module; buyers were never given the equivalent column even though
TrustScore.sol's register() works for any participant address, not just
sellers. One additive column, nothing else touched.

Revision ID: 0003_buyer_onchain_registered
Revises: 0002_add_wishlist
Create Date: 2026-08-05

Revision id shortened from 0003_add_buyer_onchain_registered (33 chars)
to fit Alembic's default `alembic_version.version_num VARCHAR(32)`
column — Postgres enforces that length strictly (SQLite, what the test
suite runs against, doesn't, which is why this went unnoticed until an
actual Postgres deploy: `psycopg.errors.StringDataRightTruncation`).
Keep future revision ids at or under 32 characters.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_buyer_onchain_registered"
down_revision: Union[str, None] = "0002_add_wishlist"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "buyers",
        sa.Column("is_onchain_registered", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("buyers", "is_onchain_registered")
