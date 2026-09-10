"""
SQLAlchemy Declarative Base.

Serves as the root base class for all application ORM models.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class for all database models."""

    pass
