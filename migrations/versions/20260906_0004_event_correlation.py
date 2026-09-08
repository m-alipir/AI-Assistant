"""Add event status and evidence-bound historical relations."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0004"
down_revision = "20260906_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events", sa.Column("status", sa.String(32), nullable=False, server_default="active")
    )
    op.create_table(
        "event_relations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("target_event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column("inference_id", sa.String(36), sa.ForeignKey("inferences.id"), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    )


def downgrade() -> None:
    op.drop_table("event_relations")
    op.drop_column("events", "status")
