"""Persist idempotent notification delivery state without message content."""

import sqlalchemy as sa
from alembic import op

revision = "20260910_0019"
down_revision = "20260910_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_deliveries",
        sa.Column("idempotency_key", sa.String(128), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_category", sa.String(64)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_notification_deliveries_status_updated",
        "notification_deliveries",
        ["status", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_deliveries_status_updated", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
