"""add city/delivery_radius_km location fields

Adds a buyer/seller city column (one of app.core.geo.CITY_NAMES) and a
seller delivery_radius_km column, so the recommendation service can rank
sellers partly by proximity — the "vendor matchmaking" signal the project
brief's reference paper calls for (location + delivery capability) that
wasn't in the schema until now. Both additive, nullable-or-defaulted
columns; nothing existing changes shape.

Revision ID: 0004_add_location_fields
Revises: 0003_buyer_onchain_registered
Create Date: 2026-08-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_location_fields"
down_revision: Union[str, None] = "0003_buyer_onchain_registered"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("buyers", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("sellers", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column(
        "sellers",
        sa.Column("delivery_radius_km", sa.Integer(), nullable=False, server_default="50"),
    )


def downgrade() -> None:
    op.drop_column("sellers", "delivery_radius_km")
    op.drop_column("sellers", "city")
    op.drop_column("buyers", "city")
