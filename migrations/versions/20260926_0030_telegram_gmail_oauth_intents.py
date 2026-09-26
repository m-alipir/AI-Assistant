"""Add one-time encrypted Telegram-initiated Gmail OAuth intents."""

import sqlalchemy as sa
from alembic import op

revision = "20260926_0030"
down_revision = "20260926_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_gmail_oauth_intents",
        sa.Column("intent_hash", sa.String(64), primary_key=True),
        sa.Column("oauth_state_hash", sa.String(64), unique=True),
        sa.Column("actor_ciphertext", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("callback_claimed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_telegram_gmail_oauth_intents_expires_at",
        "telegram_gmail_oauth_intents",
        ["expires_at"],
    )


def downgrade() -> None:
    pending = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM telegram_gmail_oauth_intents "
            "WHERE expires_at > now() AND completed_at IS NULL"
        )
    )
    if pending:
        raise RuntimeError(
            "Telegram Gmail OAuth links are still active; let them expire or complete them "
            "before downgrade"
        )
    op.drop_index(
        "ix_telegram_gmail_oauth_intents_expires_at",
        table_name="telegram_gmail_oauth_intents",
    )
    op.drop_table("telegram_gmail_oauth_intents")
