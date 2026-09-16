"""
API v1 Root Router.

Assembles all sub-routers for v1 endpoints:
- auth
- knowledge bases
- documents
- RAG search/query
"""

from fastapi import APIRouter

from backend.app.api.v1.endpoints.auth import router as auth_router
from backend.app.api.v1.endpoints.chat import router as chat_router
from backend.app.api.v1.endpoints.hybrid_retrieval import router as hybrid_retrieval_router
from backend.app.api.v1.endpoints.knowledge_bases import router as kb_router
from backend.app.api.v1.endpoints.lexical_retrieval import router as lexical_retrieval_router
from backend.app.api.v1.endpoints.query import router as query_router
from backend.app.api.v1.endpoints.reranking import router as reranking_router
from backend.app.api.v1.endpoints.retrieval import router as retrieval_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(kb_router)
api_router.include_router(query_router)
api_router.include_router(retrieval_router)
api_router.include_router(lexical_retrieval_router)
api_router.include_router(hybrid_retrieval_router)
api_router.include_router(reranking_router)
api_router.include_router(chat_router)


@api_router.get("/ping", tags=["system"])
async def ping() -> dict[str, str]:
    """Basic connectivity check for API v1."""
    return {"status": "ok", "message": "v1 active"}
