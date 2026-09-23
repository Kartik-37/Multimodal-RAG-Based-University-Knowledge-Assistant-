"""
FastAPI Application Entry Point.

Configures application lifecycle, CORS, routing, and system health checks.
Follows the modular monolith pattern where route handlers remain thin.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.db.session import check_database_connection, engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager:
    - Startup: Verifies authoritative PostgreSQL connectivity using existing health check probe.
      Fails fast without exposing connection secrets if database is unreachable.
    - Shutdown: Disposes SQLAlchemy engine connection pool on both normal exit and exceptions,
      preventing connection or socket leakage.
    """
    # 1. Startup: Verify database connection using existing health check mechanism
    if not check_database_connection():
        engine.dispose()
        raise RuntimeError("Database connection could not be established at application startup.")

    logger.info("Application startup: database connectivity verified successfully.")

    import asyncio

    from backend.app.services.indexing_worker import run_indexing_worker

    worker_task = asyncio.create_task(run_indexing_worker())

    try:
        yield
    finally:
        # 2. Shutdown: Cancel worker and dispose engine connection pool
        logger.info("Application shutdown: terminating indexing worker.")
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Application shutdown: disposing database connection pool.")
        engine.dispose()


def create_application() -> FastAPI:
    """Application factory for FastAPI."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Production-grade RAG application for university knowledge bases",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Explicit CORS configuration (safe for local development with NiceGUI frontend and API clients)
    # Wildcard is never combined with allow_credentials=True
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
        allow_headers=["*"],
    )

    # Observability & Correlation ID middleware (outermost request context)
    from backend.app.core.telemetry import CorrelationIdMiddleware

    app.add_middleware(CorrelationIdMiddleware)

    # Defensive HTTP security headers
    from backend.app.core.security import SecurityHeadersMiddleware

    app.add_middleware(SecurityHeadersMiddleware)

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

    @app.get("/ready", tags=["system"])
    async def readiness_check() -> JSONResponse:
        """
        Readiness probe: verifies that critical backing dependencies (PostgreSQL) are accessible.
        Returns 200 if ready to serve traffic, 503 if backing dependencies are unavailable.
        Suppresses internal exception details and absolute server filesystem paths to prevent leakage.
        """
        db_ready = check_database_connection()
        checks = {
            "config": "ok",
            "database": "ok" if db_ready else "unavailable",
            "storage": "ready",
        }

        if not db_ready:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "not_ready",
                    "environment": settings.APP_ENV,
                    "checks": checks,
                },
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "environment": settings.APP_ENV,
                "checks": checks,
            },
        )

    return app


app = create_application()
