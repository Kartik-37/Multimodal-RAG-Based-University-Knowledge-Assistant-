"""
Pytest Fixtures and Global Configuration.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings, settings
from backend.app.main import create_application


@pytest.fixture(scope="session")
def app_settings() -> Settings:
    """Fixture providing global application settings."""
    return settings


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """Fixture providing a synchronous HTTP TestClient for FastAPI."""
    app = create_application()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def db_engine(app_settings: Settings):
    """Fixture providing a SQLAlchemy Engine connected to the real test database."""
    from backend.app.db.session import create_db_engine

    test_engine = create_db_engine(app_settings.TEST_DATABASE_URL)
    yield test_engine
    test_engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator:
    """Fixture providing an isolated database session per test function."""
    from sqlalchemy.orm import sessionmaker

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def api_client(db_engine) -> Generator[TestClient, None, None]:
    """
    HTTP test client wired to the isolated PostgreSQL test database.
    Overrides FastAPI's get_db dependency to point to db_engine (TEST_DATABASE_URL).
    """
    from sqlalchemy.orm import sessionmaker

    from backend.app.api.deps import get_db

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    app = create_application()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
