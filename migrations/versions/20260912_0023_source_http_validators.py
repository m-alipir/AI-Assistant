"""Persist non-sensitive RSS conditional-request validators."""

import sqlalchemy as sa
from alembic import op

revision = "20260912_0023"
down_revision = "20260912_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_health", sa.Column("http_etag", sa.String(length=512)))
    op.add_column("source_health", sa.Column("http_last_modified", sa.String(length=256)))


def downgrade() -> None:
    op.drop_column("source_health", "http_last_modified")
    op.drop_column("source_health", "http_etag")
