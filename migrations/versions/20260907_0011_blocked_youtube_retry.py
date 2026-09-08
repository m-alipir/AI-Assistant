"""Add safe metadata and atomic retry control for blocked YouTube items."""

import sqlalchemy as sa
from alembic import op

revision = "20260907_0011"
down_revision = "20260907_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("post_llm_failures", sa.Column("source_name", sa.String(256)))
    op.add_column("post_llm_failures", sa.Column("title", sa.String(512)))
    op.add_column("post_llm_failures", sa.Column("canonical_url", sa.String(2048)))
    op.add_column("post_llm_failures", sa.Column("published_at", sa.DateTime(timezone=True)))
    op.add_column("post_llm_failures", sa.Column("language", sa.String(8)))
    op.add_column(
        "post_llm_failures",
        sa.Column("retry_state", sa.String(16), nullable=False, server_default="blocked"),
    )
    op.add_column(
        "post_llm_failures",
        sa.Column("retry_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "post_llm_failures",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_column("post_llm_failures", "updated_at")
    op.drop_column("post_llm_failures", "retry_attempts")
    op.drop_column("post_llm_failures", "retry_state")
    op.drop_column("post_llm_failures", "language")
    op.drop_column("post_llm_failures", "published_at")
    op.drop_column("post_llm_failures", "canonical_url")
    op.drop_column("post_llm_failures", "title")
    op.drop_column("post_llm_failures", "source_name")
