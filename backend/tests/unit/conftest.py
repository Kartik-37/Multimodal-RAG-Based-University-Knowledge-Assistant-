"""
Pytest Fixtures for Pure Unit Tests.

Overrides root database autouse fixtures to ensure unit tests remain
strictly deterministic, isolated from PostgreSQL, and execute without
external service dependencies.
"""

from collections.abc import Generator

import pytest


@pytest.fixture(scope="session", autouse=True)
def configure_test_db() -> Generator[None, None, None]:
    """No-op test db configuration for pure unit tests."""
    yield


@pytest.fixture(scope="function", autouse=True)
def clean_rate_limit_entries() -> Generator[None, None, None]:
    """No-op rate limit cleanup for pure unit tests."""
    yield
