"""
FastAPI Application Entry Point.

Configures application lifecycle, CORS, routing, and system health checks.
Follows the modular monolith pattern where route handlers remain thin.
"""

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings


def create_application() -> FastAPI:
    """Application factory for FastAPI."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Production-grade RAG application for university knowledge bases",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # CORS configuration (safe for local development with NiceGUI frontend)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.DEBUG else ["http://localhost:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/health", tags=["system"], status_code=status.HTTP_200_OK)
    async def health_check() -> dict[str, str]:
        """
        Liveness probe: verifies that the web service is running and able to handle HTTP requests.
        """
        return {
            "status": "healthy",
            "environment": settings.APP_ENV,
            "version": "0.1.0",
        }

    @app.get("/ready", tags=["system"], status_code=status.HTTP_200_OK)
    async def readiness_check() -> JSONResponse:
        """
        Readiness probe: verifies that critical backing dependencies are accessible.
        In Step 1 foundation, checks basic app configuration readiness.
        """
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "environment": settings.APP_ENV,
                "checks": {
                    "config": "ok",
                    "storage_dir": str(settings.STORAGE_DIR),
                },
            },
        )

    return app


app = create_application()
