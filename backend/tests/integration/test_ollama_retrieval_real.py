"""
Real Local Ollama Vector Retrieval Integration Test.

Connects to the real local Ollama service at http://127.0.0.1:11434, generates
1024-dimensional query embeddings with qwen3-embedding:0.6b, executes pgvector
cosine distance retrieval in PostgreSQL, and verifies semantic relevance.

Skips gracefully if the local Ollama daemon is not active.
"""

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.models.document import Document, DocumentChunk, DocumentStatus, IndexingStatus
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.user import User, UserRole
from backend.app.services.embedding.ollama_provider import OllamaEmbeddingProvider
from backend.app.services.retrieval import VectorRetrievalService


def is_ollama_online() -> bool:
    """Check whether local Ollama service is reachable."""
    try:
        resp = httpx.get(f"{settings.OLLAMA_BASE_URL}/", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.mark.asyncio
async def test_real_ollama_vector_retrieval_end_to_end(
    db_session: Session,
    db_engine,
) -> None:
    """
    End-to-end vector retrieval test with real Ollama and PostgreSQL + pgvector:
    1. Embeds chunks via local qwen3-embedding:0.6b.
    2. Persists 1024-dimensional vectors in document_chunks.
    3. Issues natural-language query and embeds via Ollama.
    4. Executes pgvector cosine-distance search.
    5. Verifies semantically closest chunk is retrieved first.
    """
    if not is_ollama_online():
        pytest.skip(
            f"Ollama daemon not reachable at {settings.OLLAMA_BASE_URL}. Skipping real integration test."
        )

    # Clean test tables
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE document_chunks, documents, knowledge_base_members, "
                "knowledge_bases, user_sessions, users CASCADE;"
            )
        )

    provider = OllamaEmbeddingProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model_name=settings.OLLAMA_EMBED_MODEL,
        dimension=settings.EMBEDDING_DIM,
    )

    # 1. Provision user and KB
    user = User(
        email="real_ollama_user@univ.edu",
        password_hash=get_password_hash("SecurePassword123!"),
        full_name="Real Ollama User",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    kb = KnowledgeBase(name="Real AI & OS Knowledge", created_by_id=user.id)
    db_session.add(kb)
    db_session.commit()

    doc = Document(
        knowledge_base_id=kb.id,
        original_filename="bca_operating_systems.pdf",
        storage_key=f"storage/{kb.id}/bca_os.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=2048,
        content_hash="a" * 64,
        status=DocumentStatus.COMPLETED,
        indexing_status=IndexingStatus.COMPLETED,
    )
    db_session.add(doc)
    db_session.commit()

    # 2. Embed real chunks with qwen3-embedding:0.6b
    chunk_texts = [
        (
            "CPU Scheduling in Operating Systems determines which process runs when the CPU "
            "becomes idle. Common algorithms include First-Come First-Served (FCFS), "
            "Shortest Job First (SJF), Priority Scheduling, and Round Robin (RR)."
        ),
        (
            "Relational Database Normalization organizes columns and tables to minimize "
            "data redundancy. First Normal Form (1NF) eliminates repeating groups, "
            "Second Normal Form (2NF) removes partial dependencies, and Third Normal Form (3NF) "
            "removes transitive dependencies."
        ),
    ]

    embeddings = await provider.embed_texts(chunk_texts)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 1024
    assert len(embeddings[1]) == 1024

    chunk_os = DocumentChunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        chunk_index=0,
        text=chunk_texts[0],
        token_count=len(chunk_texts[0].split()),
        page_number=1,
        section_title="CPU Scheduling Algorithms",
        embedding=embeddings[0],
    )
    chunk_db = DocumentChunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        chunk_index=1,
        text=chunk_texts[1],
        token_count=len(chunk_texts[1].split()),
        page_number=5,
        section_title="Database Normalization",
        embedding=embeddings[1],
    )
    db_session.add_all([chunk_os, chunk_db])
    db_session.commit()

    # 3. Issue query about CPU Scheduling
    service = VectorRetrievalService(provider=provider)
    response = await service.retrieve(
        db=db_session,
        kb_id=kb.id,
        query="Which algorithm is used for CPU scheduling in operating systems?",
        top_k=2,
    )

    assert response.total_results == 2
    top_match = response.results[0]

    # 4. Verify semantic ranking: OS chunk must be #1 with highest similarity
    assert top_match.chunk_id == chunk_os.id
    assert top_match.section_title == "CPU Scheduling Algorithms"
    assert "First-Come First-Served" in top_match.text
    assert top_match.cosine_distance < response.results[1].cosine_distance
    assert top_match.similarity > response.results[1].similarity
