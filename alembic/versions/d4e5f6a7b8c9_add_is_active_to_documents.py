"""add_is_active_to_documents

Revision ID: d4e5f6a7b8c9
Revises: e71a92b3c4d5
Create Date: 2026-09-22 14:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "e71a92b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add is_active column and index to documents table."""
    op.add_column(
        "documents",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_index(
        "ix_documents_is_active",
        "documents",
        ["is_active"],
        unique=False,
    )


def downgrade() -> None:
    """Drop is_active index and column from documents table."""
    op.drop_index("ix_documents_is_active", table_name="documents")
    op.drop_column("documents", "is_active")
