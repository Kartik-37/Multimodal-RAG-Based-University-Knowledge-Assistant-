"""
Database Session and Connection Management.

Provides SQLAlchemy 2.x synchronous engine and session factories with connection pooling.
FastAPI dependency injection executes synchronous sessions in worker threads via anyio,
preventing event-loop blocking while ensuring thread safety for NiceGUI and background tasks.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

APPROVED_TEST_DB_NAMES = {"rag_assistant_test_db", ":memory:"}
APPROVED_TEST_DB_PREFIXES = ("test_", "rag_assistant_test")


def validate_test_database_url(raw_url: str | None) -> str:
    """
    Validate that a given SQLAlchemy database URL points strictly to an approved isolated test database.

    Security & Isolation Directives:
    - Rejects production database names ('rag_assistant_db', 'postgres') explicitly.
    - Rejects unapproved database names without permitted test prefixes.
    - Never prints passwords, tokens, or raw connection strings in logs or exceptions.
    - Returns the verified database name on success.
    - Raises RuntimeError or ValueError if validation fails.
    """
    if not raw_url or not isinstance(raw_url, str) or not raw_url.strip():
        raise ValueError("Database URL is empty or missing.")

    try:
        parsed = make_url(raw_url.strip())
    except Exception as exc:
        raise ValueError(f"Failed to parse database connection URL: {type(exc).__name__}") from exc

    db_name = parsed.database
    if not db_name:
        raise ValueError("Database URL does not specify a target database name.")

    # Explicit protection for production databases
    if db_name.lower() in ("rag_assistant_db", "postgres"):
        raise RuntimeError(
            f"REFUSING DESTRUCTIVE SETUP: Target database '{db_name}' is a protected production/system database. "
            "Verification and test operations must strictly target an approved test database."
        )

    # Must match approved exact names or prefixes
    is_approved = (
        db_name in APPROVED_TEST_DB_NAMES
        or any(db_name.startswith(pfx) for pfx in APPROVED_TEST_DB_PREFIXES)
    )

    if not is_approved:
        raise RuntimeError(
            f"REFUSING DESTRUCTIVE SETUP: Database '{db_name}' is not an approved isolated test database "
            f"(must be one of {APPROVED_TEST_DB_NAMES} or have prefix {APPROVED_TEST_DB_PREFIXES})."
        )

    return db_name



def create_db_engine(database_url: str | None = None) -> Engine:
    """
    Create a SQLAlchemy Engine with connection health checking.

    pool_pre_ping=True tests connections before handing them out to detect dropped
    connections gracefully.
    """
    url = database_url or settings.DATABASE_URL
    connect_args: dict[str, Any] = {}
    if "postgresql" in str(url):
        connect_args["connect_timeout"] = 3
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=False,
        connect_args=connect_args,
    )


# Authoritative application database engine and session maker
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager providing a transactional database session for standalone scripts
    and background jobs.
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
