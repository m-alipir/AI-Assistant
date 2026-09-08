"""Record safe post-LLM failures to prevent costly automatic reprocessing."""

import sqlalchemy as sa
from alembic import op

revision = "20260907_0010"
down_revision = "20260907_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "post_llm_failures",
        sa.Column("content_hash", sa.String(64), primary_key=True),
        sa.Column("failure_category", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("post_llm_failures")
