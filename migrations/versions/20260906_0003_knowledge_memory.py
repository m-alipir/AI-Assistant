"""Add M3 structured knowledge, provenance, and pgvector event storage."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0003"
down_revision = "20260906_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(128), unique=True, nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("categories.id")),
        sa.Column("materialized_path", sa.String(512), unique=True, nullable=False),
    )
    op.create_table(
        "entities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("canonical_name", sa.String(256), unique=True, nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False, server_default="other"),
    )
    op.create_table(
        "entity_aliases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("entity_id", sa.String(36), sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("alias", sa.String(256), nullable=False),
        sa.Column("normalized_alias", sa.String(256), unique=True, nullable=False),
    )
    op.create_table(
        "topics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(128), unique=True, nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("canonical_title", sa.String(512), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer, nullable=False),
        sa.Column("raw_content", sa.Text),
    )
    op.execute("ALTER TABLE events ADD COLUMN embedding vector")
    op.create_index("ix_events_occurred_at", "events", ["occurred_at"])
    op.create_table(
        "event_sources",
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), primary_key=True),
        sa.Column("source_item_id", sa.String(256), primary_key=True),
        sa.Column("relation", sa.String(32), nullable=False, server_default="primary"),
    )
    op.create_table(
        "claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("source_item_id", sa.String(256), nullable=False),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("source_locator", sa.String(512)),
    )
    op.create_index("ix_claims_event_id", "claims", ["event_id"])
    op.create_table(
        "inferences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("inference_text", sa.Text, nullable=False),
        sa.Column("inference_type", sa.String(64), nullable=False),
    )
    op.create_index("ix_inferences_event_id", "inferences", ["event_id"])


def downgrade() -> None:
    op.drop_table("inferences")
    op.drop_table("claims")
    op.drop_table("event_sources")
    op.drop_table("events")
    op.drop_table("topics")
    op.drop_table("entity_aliases")
    op.drop_table("entities")
    op.drop_table("categories")
