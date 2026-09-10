"""
API v1 Root Router.

Assembles all sub-routers for v1 endpoints:
- auth
- knowledge bases
- documents
- RAG search/query
"""

from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/ping", tags=["system"])
async def ping() -> dict[str, str]:
    """Basic connectivity check for API v1."""
    return {"status": "ok", "message": "v1 active"}
