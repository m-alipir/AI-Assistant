"""Persist rendered daily briefing history."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0006"
down_revision = "20260906_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "briefings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rendered", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "briefing_items",
        sa.Column("briefing_id", sa.String(36), sa.ForeignKey("briefings.id"), primary_key=True),
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("section", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("briefing_items")
    op.drop_table("briefings")
