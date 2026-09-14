"""add fraud_logs.rule_signals

Adds a dedicated column for rule-based fraud sub-detectors
(app.ml.fraud_rules) — duplicate-account and velocity/bot signals — kept
separate from the existing `risk_factors` column, which is the ML model's
own explainability output. Closes the gap backend/README.md's "What's
next" section flagged: "granular fraud sub-detectors... aren't separate
from the general fraud classifier."

Revision ID: 0006_fraud_rule_signals
Revises: 0005_wallet_verified
Create Date: 2026-09-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_fraud_rule_signals"
down_revision: Union[str, None] = "0005_wallet_verified"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fraud_logs",
        sa.Column("rule_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fraud_logs", "rule_signals")
