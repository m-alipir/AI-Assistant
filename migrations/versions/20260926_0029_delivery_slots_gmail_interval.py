"""Persist exact scheduled delivery slots and Gmail polling interval."""

import sqlalchemy as sa
from alembic import op

revision = "20260926_0029"
down_revision = "20260923_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "control_center_settings",
        sa.Column(
            "gmail_poll_interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )
    op.create_check_constraint(
        "ck_control_center_settings_gmail_poll_interval_minutes",
        "control_center_settings",
        "gmail_poll_interval_minutes BETWEEN 15 AND 1440",
    )
    op.create_table(
        "scheduled_run_slots",
        sa.Column("delivery_at", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="started"),
        sa.Column("message", sa.String(512)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_scheduled_run_slots_run_date", "scheduled_run_slots", ["run_date"])
    # Legacy rows only stored the claim start. Reconstruct the prior 15-minute prep slot,
    # truncating sub-minute scheduler jitter; retain the original date-keyed history unchanged.
    op.execute(
        sa.text(
            "INSERT INTO scheduled_run_slots "
            "(delivery_at, run_date, started_at, status, message, completed_at) "
            "SELECT date_trunc('minute', started_at) + interval '15 minutes', "
            "run_date, started_at, status, message, completed_at FROM scheduled_runs "
            "ON CONFLICT (delivery_at) DO NOTHING"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    changed_intervals = bind.scalar(
        sa.text(
            "SELECT count(*) FROM control_center_settings "
            "WHERE gmail_poll_interval_minutes <> 60"
        )
    )
    if changed_intervals:
        raise RuntimeError(
            "Gmail polling preferences differ from the default; preserve them before downgrade"
        )
    new_slots = bind.scalar(
        sa.text(
            "SELECT count(*) FROM scheduled_run_slots slot "
            "WHERE NOT EXISTS (SELECT 1 FROM scheduled_runs old "
            "WHERE old.run_date = slot.run_date AND old.started_at = slot.started_at)"
        )
    )
    if new_slots:
        raise RuntimeError(
            "scheduled slot history has new entries that the legacy date-keyed table "
            "cannot represent; export/reconcile it before downgrade"
        )
    op.drop_index("ix_scheduled_run_slots_run_date", table_name="scheduled_run_slots")
    op.drop_table("scheduled_run_slots")
    op.drop_constraint(
        "ck_control_center_settings_gmail_poll_interval_minutes",
        "control_center_settings",
        type_="check",
    )
    op.drop_column("control_center_settings", "gmail_poll_interval_minutes")
