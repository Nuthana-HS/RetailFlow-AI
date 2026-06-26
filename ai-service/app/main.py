"""
RetailFlow AI — AI Service Entry Point

FastAPI application for computer vision (YOLOv8) and ML (XGBoost) services.
This service is called internally by the Core API only.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI

from app.core.config import settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    AI Service startup and shutdown.

    Startup:
        - Initialize YOLOv8 model (loads from disk/downloads weights)
        - Initialize XGBoost predictor (loads serialized model)

    Shutdown:
        - Release model resources
    """
    logger.info(
        "RetailFlow AI Service starting up",
        environment=settings.ENVIRONMENT,
        yolo_model=settings.YOLO_MODEL_SIZE,
    )

    # TODO (Phase 8): Initialize CV module — YOLO model loading
    # from app.cv.detector import detector
    # await detector.initialize()
    # logger.info("YOLOv8 model loaded", model_size=settings.YOLO_MODEL_SIZE)

    # TODO (Phase 9): Initialize ML module — XGBoost model loading
    # from app.ml.predictor import predictor
    # await predictor.initialize()
    # logger.info("XGBoost predictor loaded", model_version=predictor.version)

    logger.info("RetailFlow AI Service startup complete")

    yield

    logger.info("RetailFlow AI Service shutting down")


def create_app() -> FastAPI:
    """AI Service FastAPI application factory."""
    app = FastAPI(
        title="RetailFlow AI — AI Service",
        description=(
            "Internal AI service for computer vision (YOLOv8) and "
            "ML wait time prediction (XGBoost). "
            "Not exposed publicly — called by Core API only."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # TODO (Phase 8): Register CV routes
    # from app.api.v1.cv.router import router as cv_router
    # app.include_router(cv_router, prefix="/api/v1/cv", tags=["Computer Vision"])

    # TODO (Phase 9): Register ML routes
    # from app.api.v1.ml.router import router as ml_router
    # app.include_router(ml_router, prefix="/api/v1/ml", tags=["ML Predictions"])

    @app.get("/health", tags=["System"])
    async def health_check() -> dict[str, str]:
        """AI service health check."""
        return {
            "status": "healthy",
            "service": "retailflow-ai-service",
            "version": settings.APP_VERSION,
        }

    return app


app = create_app()
