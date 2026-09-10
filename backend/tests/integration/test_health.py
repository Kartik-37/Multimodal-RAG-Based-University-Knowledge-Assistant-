"""
Integration tests for system health probes and API v1 router connectivity.
"""

from fastapi import status
from fastapi.testclient import TestClient


def test_health_check_endpoint(client: TestClient) -> None:
    """Verify /health returns HTTP 200 with healthy status."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data
    assert data["version"] == "0.1.0"


def test_ready_check_endpoint(client: TestClient) -> None:
    """Verify /ready returns HTTP 200 with readiness check results."""
    response = client.get("/ready")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["config"] == "ok"


def test_api_v1_ping_endpoint(client: TestClient) -> None:
    """Verify /api/v1/ping returns HTTP 200 and router is mounted properly."""
    response = client.get("/api/v1/ping")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ok"
    assert data["message"] == "v1 active"
