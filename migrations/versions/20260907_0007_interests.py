"""Persist stable interest layers and feedback history."""

import sqlalchemy as sa
from alembic import op

revision = "20260907_0007"
down_revision = "20260906_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "interest_profile",
        sa.Column("subject", sa.String(256), primary_key=True),
        sa.Column("base", sa.Float, nullable=False),
        sa.Column("explicit", sa.Float, nullable=False),
        sa.Column("adaptive", sa.Float, nullable=False),
    )
    op.create_table(
        "feedback_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("subject", sa.String(256), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "interest_candidates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("subject", sa.String(256), nullable=False),
        sa.Column("delta", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("interest_candidates")
    op.drop_table("feedback_events")
    op.drop_table("interest_profile")
