"""Add metadata-only audit records for the read-only Agent API."""

import sqlalchemy as sa
from alembic import op

revision = "20260908_0016"
down_revision = "20260908_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_api_audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("response_bytes", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_api_audit_log_occurred_at", "agent_api_audit_log", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_api_audit_log_occurred_at", table_name="agent_api_audit_log")
    op.drop_table("agent_api_audit_log")
