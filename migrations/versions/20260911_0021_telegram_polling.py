"""Persist a privacy-minimized Telegram long-poll offset."""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0021"
down_revision = "20260911_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_polling_state",
        sa.Column("consumer_name", sa.String(32), primary_key=True),
        sa.Column("next_offset", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.alter_column("telegram_polling_state", "next_offset", server_default=None)


def downgrade() -> None:
    op.drop_table("telegram_polling_state")
