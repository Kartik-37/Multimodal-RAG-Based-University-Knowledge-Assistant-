"""
Database Session and Connection Management.

Provides SQLAlchemy 2.x synchronous engine and session factories with connection pooling.
FastAPI dependency injection executes synchronous sessions in worker threads via anyio,
preventing event-loop blocking while ensuring thread safety for NiceGUI and background tasks.
"""

import logging
from collections.abc import Generator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def create_db_engine(database_url: str | None = None) -> Engine:
    """
    Create a SQLAlchemy Engine with connection health checking.

    pool_pre_ping=True tests connections before handing them out to detect dropped
    connections gracefully.
    """
    url = database_url or settings.DATABASE_URL
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=False,
    )


# Authoritative application database engine and session maker
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding an isolated database session.

    Enforces transaction boundaries:
    - Commits automatically if the request handler succeeds.
    - Rolls back changes if any exception is raised.
    - Closes the session reliably in all cases.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database_connection(db_engine: Engine | None = None) -> bool:
    """
    Health check probe: performs a lightweight 'SELECT 1' query.

    Returns True if the database is reachable and accepting queries, False otherwise.
    Suppresses internal exception details to prevent credential or schema leakage.
    """
    target_engine = db_engine or engine
    try:
        with target_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except (SQLAlchemyError, Exception) as exc:
        logger.warning("Database readiness probe failed: %s", type(exc).__name__)
        return False
