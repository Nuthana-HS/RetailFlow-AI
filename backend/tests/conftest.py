"""
RetailFlow AI — pytest Configuration

This conftest.py sets up:
  - Test database session (using SQLite in-memory for unit tests)
  - FastAPI test client
  - Test fixtures for users, stores, counters
  - Redis mock for unit tests
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.main import app


# =============================================================================
# Event Loop Configuration
# =============================================================================

@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.DefaultEventLoopPolicy:
    """Use default asyncio event loop policy for all tests."""
    return asyncio.DefaultEventLoopPolicy()


# =============================================================================
# Test Database (In-memory SQLite)
# =============================================================================

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
async def test_engine() -> AsyncGenerator[Any, None]:
    """Create an in-memory SQLite engine for the test session."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Share single connection across threads
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a test database session that rolls back after each test.

    This ensures test isolation — each test starts with a clean slate.
    """
    async_session = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


# =============================================================================
# Redis Mock
# =============================================================================

@pytest.fixture
def mock_redis() -> AsyncMock:
    """
    Mock Redis client for unit tests.

    Prevents tests from requiring a real Redis connection.
    Returns an AsyncMock that can be configured per-test.
    """
    mock = AsyncMock()
    mock.ping.return_value = True
    mock.get.return_value = None
    mock.set.return_value = True
    mock.setex.return_value = True
    mock.hset.return_value = 1
    mock.hgetall.return_value = {}
    mock.publish.return_value = 0
    return mock


# =============================================================================
# FastAPI Test Client
# =============================================================================

@pytest.fixture
async def client(db_session: AsyncSession, mock_redis: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide an async HTTP test client with injected test dependencies.

    Overrides:
        - get_db → test database session
        - get_redis → mock Redis client
    """
    # Override dependencies
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    # Clear dependency overrides after test
    app.dependency_overrides.clear()


# =============================================================================
# Test Data Fixtures
# These will be expanded in Phase 3+ as models are created
# =============================================================================

@pytest.fixture
def test_user_data() -> dict[str, str]:
    """Sample user data for registration tests."""
    return {
        "email": "test.manager@retailflow.test",
        "password": "TestPass123!",
        "full_name": "Test Manager",
        "role": "manager",
    }


@pytest.fixture
def test_admin_data() -> dict[str, str]:
    """Sample admin user data."""
    return {
        "email": "test.admin@retailflow.test",
        "password": "AdminPass123!",
        "full_name": "Test Admin",
        "role": "admin",
    }
