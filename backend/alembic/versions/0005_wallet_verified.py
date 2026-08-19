"""add buyers/sellers.wallet_verified

Closes a real gap: wallet_address was settable via PATCH /auth/me as plain
text with only a format check (0x + 40 hex chars) — no proof the caller
actually controls that address. wallet_verified is only ever set True by
POST /auth/wallet/link, which requires a signature over a one-time server
nonce (see app/api/v1/endpoints/auth.py). PATCH /auth/me can no longer set
wallet_address at all as of this change.

Revision ID: 0005_wallet_verified
Revises: 0004_add_location_fields
Create Date: 2026-08-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_wallet_verified"
down_revision: Union[str, None] = "0004_add_location_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("buyers", sa.Column("wallet_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("sellers", sa.Column("wallet_verified", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("sellers", "wallet_verified")
    op.drop_column("buyers", "wallet_verified")
