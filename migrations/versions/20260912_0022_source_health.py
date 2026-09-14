"""Persist privacy-minimized source health and cooldown state."""

import sqlalchemy as sa
from alembic import op

revision = "20260912_0022"
down_revision = "20260911_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_health",
        sa.Column("source_kind", sa.String(length=16), primary_key=True),
        sa.Column("source_name", sa.String(length=256), primary_key=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="healthy"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_category", sa.String(length=64), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_strategy", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("source_health")
