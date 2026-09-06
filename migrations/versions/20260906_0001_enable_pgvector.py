"""Enable the pgvector extension used by later semantic retrieval migrations.

Revision ID: 20260906_0001
Revises:
Create Date: 2026-09-06 00:00:00
"""

from alembic import op

revision = "20260906_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enable pgvector in the development PostgreSQL image."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Remove pgvector only when explicitly downgrading an otherwise empty foundation."""
    op.execute("DROP EXTENSION IF EXISTS vector")
