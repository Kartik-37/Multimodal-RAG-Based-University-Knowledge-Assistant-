"""add_document_id_to_conversations

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-28 10:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add optional document_id foreign key to conversations table."""
    conn = op.get_bind()
    # Check if column already exists to ensure idempotency
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("conversations")]
    if "document_id" not in columns:
        op.add_column(
            "conversations",
            sa.Column(
                "document_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("documents.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    """Remove document_id from conversations table."""
    op.drop_column("conversations", "document_id")
