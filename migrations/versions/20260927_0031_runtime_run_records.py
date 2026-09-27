"""Persist a bounded metadata-only runtime execution trail."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260927_0031"
down_revision = "20260926_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_run_records",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("entry_point", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "details", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )
    op.create_index(
        "ix_runtime_run_records_started_at", "runtime_run_records", ["started_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_runtime_run_records_started_at", table_name="runtime_run_records")
    op.drop_table("runtime_run_records")
