"""
Pytest Fixtures for Unit Tests.

Provides resilient test database configuration:
- When PostgreSQL is available, binds SessionLocal and engine to TEST_DATABASE_URL
  so database-dependent unit services (e.g. indexing pipeline) interact with the test database.
- When PostgreSQL is unavailable, gracefully no-ops so pure, non-database unit tests
  remain independent of external database services.
"""

from collections.abc import Generator

import pytest


@pytest.fixture(scope="session", autouse=True)
def configure_test_db() -> Generator[None, None, None]:
    """Ensure SessionLocal binds to test database if available without breaking offline runs."""
    import backend.app.db.session as db_session_module
    from backend.app.core.config import settings
    from backend.app.db.session import create_db_engine

    engine = None
    old_engine = db_session_module.engine
    try:
        engine = create_db_engine(settings.TEST_DATABASE_URL)
        with engine.connect():
            pass
        db_session_module.engine = engine
        db_session_module.SessionLocal.configure(bind=engine)
    except Exception:
        engine = None

    yield

    if engine is not None:
        db_session_module.engine = old_engine
        db_session_module.SessionLocal.configure(bind=old_engine)
        engine.dispose()


@pytest.fixture(scope="function", autouse=True)
def clean_rate_limit_entries() -> Generator[None, None, None]:
    """Ensure rate limit entries are cleaned if test database is available."""
    from sqlalchemy import text

    import backend.app.db.session as db_session_module

    try:
        with db_session_module.engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE rate_limit_entries;"))
    except Exception:
        pass

    yield

    try:
        with db_session_module.engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE rate_limit_entries;"))
    except Exception:
        pass
