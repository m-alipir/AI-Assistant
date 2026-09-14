"""Persist non-secret Control Center preferences."""

import sqlalchemy as sa
from alembic import op

revision = "20260914_0026"
down_revision = "20260914_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = op.create_table(
        "control_center_settings",
        sa.Column("id", sa.Boolean(), primary_key=True, server_default=sa.true()),
        sa.Column("scheduler_enabled", sa.Boolean()),
        sa.Column("scheduler_daily_time", sa.String(5)),
    )
    op.bulk_insert(table, [{"id": True}])


def downgrade() -> None:
    op.drop_table("control_center_settings")
