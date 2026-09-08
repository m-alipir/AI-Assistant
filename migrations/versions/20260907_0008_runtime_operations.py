"""Add cost provenance and durable scheduled-run idempotency."""

import sqlalchemy as sa
from alembic import op

revision = "20260907_0008"
down_revision = "20260907_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_calls", sa.Column("provider_cost_usd", sa.Float()))
    op.add_column(
        "llm_calls",
        sa.Column("cost_status", sa.String(32), nullable=False, server_default="unavailable"),
    )
    op.create_table(
        "scheduled_runs",
        sa.Column("run_date", sa.Date(), primary_key=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="started"),
        sa.Column("message", sa.String(512)),
    )


def downgrade() -> None:
    op.drop_table("scheduled_runs")
    op.drop_column("llm_calls", "cost_status")
    op.drop_column("llm_calls", "provider_cost_usd")
