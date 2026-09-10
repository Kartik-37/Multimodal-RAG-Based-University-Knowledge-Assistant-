"""enable_vector_extension

Revision ID: f06d9a1c047f
Revises:
Create Date: 2026-09-10 14:11:29.352118

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f06d9a1c047f"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: enable pgvector extension."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def downgrade() -> None:
    """Downgrade schema: remove pgvector extension."""
    op.execute("DROP EXTENSION IF EXISTS vector CASCADE;")
