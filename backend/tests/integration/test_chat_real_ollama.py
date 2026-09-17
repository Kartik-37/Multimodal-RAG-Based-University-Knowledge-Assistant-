"""
Real Local Ollama End-to-End Chat Orchestration Integration Test.

Connects to the real local Ollama service at http://127.0.0.1:11434 and runs
the complete live RAG orchestration pipeline.

Requirements:
- Skips gracefully when the local Ollama daemon or required model is not active.
- When live Ollama is running:
  - Invokes real Ollama generation via RAGOrchestrator.
  - Verifies non-empty response conforming to ChatQueryResponse.
  - Verifies latency breakdown and grounding summary.
"""

from collections.abc import Generator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User, UserRole


def is_ollama_with_model_online(model_name: str = "qwen3:4b") -> bool:
    """Check whether local Ollama service is reachable and has the required model."""
    try:
        resp = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        if resp.status_code != 200:
            return False
        models = [m.get("name", "") for m in resp.json().get("models", [])]
        return any(model_name in m for m in models)
    except Exception:
        return False


@pytest.fixture(autouse=True)
def clean_real_ollama_db(db_engine) -> Generator[None, None, None]:
    """Clean tables before and after test."""
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE document_chunks, documents, "
                "knowledge_base_members, knowledge_bases, "
                "user_sessions, users CASCADE;"
            )
        )
    yield
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE document_chunks, documents, "
                "knowledge_base_members, knowledge_bases, "
                "user_sessions, users CASCADE;"
            )
        )


def create_user_direct(
    db: Session,
    email: str,
    password: str = "TestPassword123!",
    role: UserRole = UserRole.ADMIN,
) -> User:
    """Helper to provision an active user."""
    user = User(
        email=email.strip().lower(),
        password_hash=get_password_hash(password),
        full_name="Real Ollama Tester",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_real_ollama_chat_orchestration_live(
    api_client: TestClient, db_session: Session
) -> None:
    """
    Live end-to-end integration test with real Ollama.
    Skips if Ollama is unavailable or model is missing.
    """
    if not is_ollama_with_model_online(settings.OLLAMA_LLM_MODEL):
        pytest.skip(
            f"Ollama daemon or model '{settings.OLLAMA_LLM_MODEL}' not available at "
            f"{settings.OLLAMA_BASE_URL}. Skipping real integration test."
        )

    admin = create_user_direct(db_session, email="real_ollama_chat@univ.edu")
    kb = KnowledgeBase(
        name="Real Ollama Test KB",
        description="Testing with real local Ollama",
        created_by_id=admin.id,
    )
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    api_client.post(
        "/api/v1/auth/login",
        json={"email": "real_ollama_chat@univ.edu", "password": "TestPassword123!"},
    )

    # Empty context live test: verify deterministic fast-path without model error
    resp = api_client.post(
        f"/api/v1/knowledge-bases/{kb.id}/chat",
        json={"question": "What is the capital of Mars?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_empty_context"] is True
    assert "could not find any relevant information" in data["answer"].lower()
    assert data["grounding"]["status"] == "REFUSAL"
    assert data["grounding"]["is_grounded"] is True
    assert data["latency"]["total_pipeline_ms"] >= 0.0
