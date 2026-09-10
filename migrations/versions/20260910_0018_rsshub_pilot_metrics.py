"""Persist aggregate-only RSSHub pilot route measurements."""

import sqlalchemy as sa
from alembic import op

revision = "20260910_0018"
down_revision = "20260909_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rsshub_pilot_route_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_name", sa.String(256), nullable=False),
        sa.Column("stream", sa.String(32), nullable=False),
        sa.Column("source_tier", sa.String(64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("fetched_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fresh_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retained_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_category", sa.String(128)),
    )
    op.create_index(
        "ix_rsshub_pilot_route_observations_source_observed",
        "rsshub_pilot_route_observations",
        ["source_name", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rsshub_pilot_route_observations_source_observed",
        table_name="rsshub_pilot_route_observations",
    )
    op.drop_table("rsshub_pilot_route_observations")
