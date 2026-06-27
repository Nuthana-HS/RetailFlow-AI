"""
RetailFlow AI — FastAPI Application Entry Point

This module creates and configures the FastAPI application instance.
It follows the Application Factory pattern for testability.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.database import engine
from app.core.redis import redis_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Application Lifespan (startup + shutdown events)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manages application startup and shutdown lifecycle.

    Startup:
        - Initialize database connection pool
        - Connect to Redis
        - Log startup info

    Shutdown:
        - Close database connections
        - Close Redis connections
    """
    # -------------------------------------------------------------------------
    # Startup
    # -------------------------------------------------------------------------
    logger.info(
        "RetailFlow AI Backend starting up",
        environment=settings.ENVIRONMENT,
        version=settings.APP_VERSION,
    )

    # Test database connectivity
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")  # type: ignore[arg-type]
        logger.info("Database connection established")
    except Exception as e:
        logger.error("Failed to connect to database", error=str(e))
        raise

    # Test Redis connectivity
    try:
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e))
        raise

    logger.info("RetailFlow AI Backend startup complete")

    yield  # Application is running

    # -------------------------------------------------------------------------
    # Shutdown
    # -------------------------------------------------------------------------
    logger.info("RetailFlow AI Backend shutting down...")

    await engine.dispose()
    await redis_client.close()

    logger.info("RetailFlow AI Backend shutdown complete")


# =============================================================================
# Rate Limiter
# =============================================================================

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


# =============================================================================
# Application Factory
# =============================================================================

def create_app() -> FastAPI:
    """
    FastAPI application factory.

    Returns a fully configured FastAPI instance with:
    - CORS middleware
    - Rate limiting
    - API routers (v1)
    - Health check endpoint
    - OpenAPI documentation
    """
    app = FastAPI(
        title="RetailFlow AI — Core API",
        description=(
            "AI-powered Retail Queue Intelligence Platform API. "
            "Real-time queue monitoring, wait time prediction, and staffing optimization."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
        contact={
            "name": "RetailFlow AI Engineering Team",
            "url": "https://github.com/Nuthana-HS/RetailFlow-AI",
        },
        license_info={"name": "MIT"},
    )

    # -------------------------------------------------------------------------
    # Middleware (order matters — applied in reverse order)
    # -------------------------------------------------------------------------

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    # Trusted host (prevents host header injection in production)
    if settings.ENVIRONMENT == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS,
        )

    # CORS — must be after rate limiting
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=86400,  # Cache preflight for 24 hours
    )

    # -------------------------------------------------------------------------
    # Routers
    # -------------------------------------------------------------------------
    # Routers are registered here as each phase completes.
    # Phase 3: Auth ✅
    from app.api.v1.auth.router import router as auth_router
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])

    # Phase 4: Store Management ✅
    from app.api.v1.stores.router import router as stores_router
    app.include_router(stores_router, prefix="/api/v1/stores", tags=["Store Management"])

    # Phase 5: Queue Engine ✅
    from app.api.v1.queues.router import router as queues_router
    app.include_router(queues_router, prefix="/api/v1/queues", tags=["Queue Engine"])

    # Phase 6: Analytics ✅
    from app.api.v1.analytics.router import router as analytics_router
    app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])

    # Phase 7: WebSocket Real-Time ✅
    from app.websocket.router import router as ws_router
    app.include_router(ws_router, prefix="/ws", tags=["WebSocket"])

    # -------------------------------------------------------------------------
    # Health Check Endpoint
    # -------------------------------------------------------------------------

    @app.get("/health", tags=["System"], summary="Health check")
    async def health_check() -> dict:
        """
        Health check endpoint for load balancers and monitoring.

        Returns:
            JSON with status, version, environment, and WebSocket connection stats.
        """
        from app.websocket.connection_manager import connection_manager

        return {
            "status": "healthy",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "service": "retailflow-ai-backend",
            "websocket": connection_manager.stats,
        }

    return app


# =============================================================================
# Application Instance
# =============================================================================

app = create_app()
