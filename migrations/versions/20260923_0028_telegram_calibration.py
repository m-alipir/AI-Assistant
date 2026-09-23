"""Store the bounded Telegram onboarding calibration progress and subjects."""

import sqlalchemy as sa
from alembic import op

revision = "20260923_0028"
down_revision = "20260914_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "control_center_settings",
        sa.Column("telegram_calibration_days", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "control_center_settings",
        sa.Column("telegram_calibration_last_day", sa.Date(), nullable=True),
    )
    op.add_column(
        "telegram_feedback_tokens",
        sa.Column("subject", sa.String(256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("telegram_feedback_tokens", "subject")
    op.drop_column("control_center_settings", "telegram_calibration_last_day")
    op.drop_column("control_center_settings", "telegram_calibration_days")
