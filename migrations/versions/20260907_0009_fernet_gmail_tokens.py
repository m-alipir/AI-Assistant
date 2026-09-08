"""Mark Gmail token encryption scheme for authenticated-encryption migration."""

import sqlalchemy as sa
from alembic import op

revision = "20260907_0009"
down_revision = "20260907_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gmail_accounts",
        sa.Column("token_scheme", sa.String(32), nullable=False, server_default="legacy_xor"),
    )


def downgrade() -> None:
    op.drop_column("gmail_accounts", "token_scheme")
