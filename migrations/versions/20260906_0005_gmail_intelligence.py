"""Add minimal protected Gmail state and classifications."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0005"
down_revision = "20260906_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gmail_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("encrypted_refresh_token", sa.Text, nullable=False),
        sa.Column("history_id", sa.String(128)),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "email_classifications",
        sa.Column("source_item_id", sa.String(256), primary_key=True),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("action_summary", sa.Text),
        sa.Column("deadline", sa.DateTime(timezone=True)),
        sa.Column("application_company", sa.String(256)),
    )


def downgrade() -> None:
    op.drop_table("email_classifications")
    op.drop_table("gmail_accounts")
