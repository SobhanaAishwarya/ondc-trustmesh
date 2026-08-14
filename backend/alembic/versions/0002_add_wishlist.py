"""add wishlists table

Not one of the original 12 tables in database/schema.sql — added for the
buyer wishlist feature. One small additive table, nothing else touched;
schema.sql has been updated to match.

Revision ID: 0002_add_wishlist
Revises: 0001_initial_schema
Create Date: 2026-08-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_add_wishlist"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wishlists",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "buyer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("buyers.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("buyer_id", "product_id", name="uq_wishlists_buyer_product"),
    )
    op.create_index("idx_wishlists_buyer", "wishlists", ["buyer_id"])


def downgrade() -> None:
    op.drop_table("wishlists")
