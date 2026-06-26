"""
RetailFlow AI — Database Engine and Session Management

Configures SQLAlchemy async engine and provides a session factory
via FastAPI dependency injection.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# =============================================================================
# SQLAlchemy Async Engine
# =============================================================================

engine = create_async_engine(
    settings.active_database_url,
    # Connection pool settings
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,          # Verify connection alive before using from pool
    pool_recycle=3600,           # Recycle connections after 1 hour
    echo=settings.DEBUG,         # Log SQL queries in debug mode
    future=True,                 # Use SQLAlchemy 2.0 style
)


# =============================================================================
# Session Factory
# =============================================================================

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,      # Don't expire objects after commit (important for async)
    autocommit=False,
    autoflush=False,
)


# =============================================================================
# Base Model Class
# =============================================================================

class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    All models in app/models/ inherit from this class.
    Provides common functionality via DeclarativeBase.
    """
    pass


# =============================================================================
# Dependency: Database Session
# =============================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session per request.

    Usage in route handlers:
        @router.get("/")
        async def handler(db: AsyncSession = Depends(get_db)):
            ...

    The session is automatically committed on success and rolled back on error.
    The session is always closed after the request completes.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
