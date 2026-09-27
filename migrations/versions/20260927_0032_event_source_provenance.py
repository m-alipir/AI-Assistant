"""Persist verified source labels and freshness policy snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "20260927_0032"
down_revision = "20260927_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("event_sources", sa.Column("source_name", sa.String(200), nullable=True))
    op.add_column("event_sources", sa.Column("freshness_hours", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_event_sources_freshness_hours_positive",
        "event_sources",
        "freshness_hours IS NULL OR freshness_hours > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_event_sources_freshness_hours_positive", "event_sources", type_="check"
    )
    op.drop_column("event_sources", "freshness_hours")
    op.drop_column("event_sources", "source_name")
