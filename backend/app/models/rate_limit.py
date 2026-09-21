"""
Rate Limiting Database Models.

Stores persistent, atomic rate-limiting counters in PostgreSQL.
Composite primary key (key, window_bucket) ensures atomic increments
via PostgreSQL row-level locks on conflict (INSERT ... ON CONFLICT DO UPDATE).
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class RateLimitEntry(Base):
    """
    Persistent rate-limit state bucket in PostgreSQL.

    Invariants:
    - key: Identifier for the quota subject (e.g., 'user:<uuid>:<policy>' or 'ip:<ip>:<policy>').
    - window_bucket: Discretized epoch window (epoch_seconds // window_seconds).
    - count: Monotonically incremented request counter within this window bucket.
    - expires_at: Timestamp when this window bucket becomes eligible for cleanup.
    """

    __tablename__ = "rate_limit_entries"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    window_bucket: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
