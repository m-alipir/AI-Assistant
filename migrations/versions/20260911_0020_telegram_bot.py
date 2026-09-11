"""Add Telegram webhook replay protection and channel-scoped delivery state."""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0020"
down_revision = "20260910_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_deliveries",
        sa.Column("channel", sa.String(32), nullable=False, server_default="ntfy"),
    )
    op.drop_constraint("notification_deliveries_pkey", "notification_deliveries", type_="primary")
    op.create_primary_key(
        "notification_deliveries_pkey",
        "notification_deliveries",
        ["channel", "idempotency_key"],
    )
    op.alter_column("notification_deliveries", "channel", server_default=None)
    op.create_table(
        "telegram_updates",
        sa.Column("update_id", sa.BigInteger(), primary_key=True),
        sa.Column("actor_hash", sa.String(64), nullable=False),
        sa.Column("chat_hash", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("failure_category", sa.String(64)),
        sa.Column(
            "received_at",
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
    )
    op.create_index(
        "ix_telegram_updates_status_updated", "telegram_updates", ["status", "updated_at"]
    )
    op.create_table(
        "telegram_feedback_tokens",
        sa.Column("token", sa.String(20), primary_key=True),
        sa.Column("actor_pair_hash", sa.String(64), nullable=False),
        sa.Column("briefing_id", sa.String(36), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["briefing_id"], ["briefings.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_telegram_feedback_tokens_expires_at", "telegram_feedback_tokens", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_feedback_tokens_expires_at", table_name="telegram_feedback_tokens")
    op.drop_table("telegram_feedback_tokens")
    op.drop_index("ix_telegram_updates_status_updated", table_name="telegram_updates")
    op.drop_table("telegram_updates")
    op.drop_constraint("notification_deliveries_pkey", "notification_deliveries", type_="primary")
    op.drop_column("notification_deliveries", "channel")
    op.create_primary_key(
        "notification_deliveries_pkey", "notification_deliveries", ["idempotency_key"]
    )
