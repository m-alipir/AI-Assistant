"""Add non-sensitive LLM operational cache and accounting tables."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0002"
down_revision = "20260906_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("model_id", sa.String(256), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False),
        sa.Column("estimated_cost_usd", sa.Float, nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("cache_hit", sa.Boolean, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_llm_calls_role", "llm_calls", ["role"])
    op.create_table(
        "llm_result_cache",
        sa.Column("cache_key", sa.String(64), primary_key=True),
        sa.Column("model_id", sa.String(256), nullable=False),
        sa.Column("validated_result_json", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("llm_result_cache")
    op.drop_index("ix_llm_calls_role", table_name="llm_calls")
    op.drop_table("llm_calls")
