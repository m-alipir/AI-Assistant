"""Add safe provenance and filter metadata for user-facing knowledge search."""

import sqlalchemy as sa
from alembic import op

revision = "20260907_0013"
down_revision = "20260907_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("event_sources", sa.Column("canonical_url", sa.String(2048)))
    op.add_column("event_sources", sa.Column("source_kind", sa.String(32)))
    op.create_table(
        "event_search_metadata",
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), primary_key=True),
        sa.Column("category_paths_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("entities_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("topics_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "email_classifications",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_column("email_classifications", "created_at")
    op.drop_table("event_search_metadata")
    op.drop_column("event_sources", "source_kind")
    op.drop_column("event_sources", "canonical_url")
