"""Create canonical database-managed source configuration."""

import sqlalchemy as sa
from alembic import op

revision = "20260913_0024"
down_revision = "20260911_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "managed_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("canonical_endpoint", sa.String(2048), nullable=False),
        sa.Column("stream", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("category", sa.String(128)),
        sa.Column("language", sa.String(8)),
        sa.Column("freshness_hours", sa.Integer()),
        sa.Column("health_status", sa.String(24), nullable=False, server_default="healthy"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_category", sa.String(64)),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("last_successful_strategy", sa.String(64)),
        sa.Column("detected_language", sa.String(16)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("kind", "canonical_endpoint", name="uq_managed_sources_endpoint"),
    )
    op.create_index("ix_managed_sources_enabled", "managed_sources", ["enabled", "kind"])


def downgrade() -> None:
    op.drop_index("ix_managed_sources_enabled", table_name="managed_sources")
    op.drop_table("managed_sources")
