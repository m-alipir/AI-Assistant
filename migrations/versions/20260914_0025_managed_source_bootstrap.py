"""Record completion of the one-time managed-source YAML bootstrap."""

import sqlalchemy as sa
from alembic import op

revision = "20260914_0025"
down_revision = "20260913_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = op.create_table(
        "managed_source_bootstrap",
        sa.Column("id", sa.Boolean(), primary_key=True, server_default=sa.true()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("defaults", sa.JSON()),
    )
    op.bulk_insert(table, [{"id": True}])


def downgrade() -> None:
    op.drop_table("managed_source_bootstrap")
