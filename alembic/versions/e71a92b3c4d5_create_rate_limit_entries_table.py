"""create_rate_limit_entries_table

Revision ID: e71a92b3c4d5
Revises: 35fc9a73097a
Create Date: 2026-09-21 11:07:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e71a92b3c4d5"
down_revision: str | Sequence[str] | None = "35fc9a73097a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create rate_limit_entries table with composite primary key and expiration index."""
    op.create_table(
        "rate_limit_entries",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("window_bucket", sa.BigInteger(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key", "window_bucket", name="pk_rate_limit_entries"),
    )
    op.create_index(
        "ix_rate_limit_entries_expires_at",
        "rate_limit_entries",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop rate_limit_entries table and its index."""
    op.drop_index("ix_rate_limit_entries_expires_at", table_name="rate_limit_entries")
    op.drop_table("rate_limit_entries")
