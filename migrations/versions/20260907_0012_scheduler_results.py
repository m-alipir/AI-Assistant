"""Persist safe completion metadata for each claimed daily scheduler run."""

import sqlalchemy as sa
from alembic import op

revision = "20260907_0012"
down_revision = "20260907_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scheduled_runs", sa.Column("completed_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("scheduled_runs", "completed_at")
