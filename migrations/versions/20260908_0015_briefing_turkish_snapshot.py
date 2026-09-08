"""Persist Turkish-first briefing presentation fields without rewriting old briefings."""

import sqlalchemy as sa
from alembic import op

revision = "20260908_0015"
down_revision = "20260908_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("briefing_outbox", sa.Column("summary_tr", sa.Text()))
    op.add_column("briefing_outbox", sa.Column("what_changed_tr", sa.Text()))
    op.add_column("briefing_outbox", sa.Column("why_important_tr", sa.Text()))
    op.create_table(
        "briefing_item_content",
        sa.Column("briefing_id", sa.String(36), nullable=False),
        sa.Column("event_id", sa.String(256), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary_tr", sa.Text()),
        sa.Column("what_changed_tr", sa.Text()),
        sa.Column("why_important_tr", sa.Text()),
        sa.ForeignKeyConstraint(["briefing_id"], ["briefings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("briefing_id", "event_id"),
    )


def downgrade() -> None:
    op.drop_table("briefing_item_content")
    op.drop_column("briefing_outbox", "why_important_tr")
    op.drop_column("briefing_outbox", "what_changed_tr")
    op.drop_column("briefing_outbox", "summary_tr")
