"""Add a safe briefing outbox and indexes for bounded production paths."""

import sqlalchemy as sa
from alembic import op

revision = "20260908_0014"
down_revision = "20260907_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows originated from the YouTube-only post-LLM guard.
    op.add_column(
        "post_llm_failures",
        sa.Column("source_kind", sa.String(32), nullable=False, server_default="youtube"),
    )
    op.create_table(
        "briefing_outbox",
        sa.Column("event_id", sa.String(256), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("source_urls_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("interest", sa.Integer(), nullable=False),
        sa.Column("global_importance", sa.Integer(), nullable=False),
        sa.Column("actionable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("video", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("why_watch", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # These match the actual bounded ORDER BY / lookup paths used by Admin, dedup, and Search.
    op.create_index("ix_briefings_created_at", "briefings", ["created_at"])
    op.create_index("ix_email_classifications_created_at", "email_classifications", ["created_at"])
    op.create_index("ix_event_sources_source_item_id", "event_sources", ["source_item_id"])
    op.create_index(
        "ix_event_sources_source_kind_event_id",
        "event_sources",
        ["source_kind", "event_id"],
    )
    op.create_index("ix_llm_calls_created_at", "llm_calls", ["created_at"])
    op.create_index(
        "ix_post_llm_failures_source_kind_updated_at",
        "post_llm_failures",
        ["source_kind", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_post_llm_failures_source_kind_updated_at", table_name="post_llm_failures")
    op.drop_index("ix_llm_calls_created_at", table_name="llm_calls")
    op.drop_index("ix_event_sources_source_kind_event_id", table_name="event_sources")
    op.drop_index("ix_event_sources_source_item_id", table_name="event_sources")
    op.drop_index("ix_email_classifications_created_at", table_name="email_classifications")
    op.drop_index("ix_briefings_created_at", table_name="briefings")
    op.drop_table("briefing_outbox")
    op.drop_column("post_llm_failures", "source_kind")
