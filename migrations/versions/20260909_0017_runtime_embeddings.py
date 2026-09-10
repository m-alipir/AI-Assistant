"""Persist model-bound event and claim vectors for runtime semantic retrieval."""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0017"
down_revision = "20260908_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("embedding_model_id", sa.String(256)))
    op.add_column("claims", sa.Column("embedding_model_id", sa.String(256)))
    op.add_column("claims", sa.Column("embedding_dimensions", sa.Integer()))
    op.execute("ALTER TABLE claims ADD COLUMN embedding vector")
    op.create_index(
        "ix_events_embedding_model_dimensions",
        "events",
        ["embedding_model_id", "embedding_dimensions"],
    )
    op.create_index(
        "ix_claims_embedding_model_dimensions",
        "claims",
        ["embedding_model_id", "embedding_dimensions"],
    )


def downgrade() -> None:
    op.drop_index("ix_claims_embedding_model_dimensions", table_name="claims")
    op.drop_index("ix_events_embedding_model_dimensions", table_name="events")
    op.execute("ALTER TABLE claims DROP COLUMN embedding")
    op.drop_column("claims", "embedding_dimensions")
    op.drop_column("claims", "embedding_model_id")
    op.drop_column("events", "embedding_model_id")
