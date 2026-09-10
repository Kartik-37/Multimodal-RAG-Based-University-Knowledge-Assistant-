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
