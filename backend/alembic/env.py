"""
Alembic Environment Configuration

This file configures Alembic to:
  1. Read the DATABASE_URL from app settings (not hardcoded)
  2. Import all SQLAlchemy models so autogenerate can detect schema changes
  3. Run migrations in async mode (required for asyncpg)
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Alembic Config object (access to alembic.ini values)
config = context.config

# Configure Python logging from the alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# =============================================================================
# Import ALL models here so Alembic autogenerate can detect them
# =============================================================================
# IMPORTANT: Every new model file must be imported here, otherwise
# Alembic won't know about it and won't generate migrations for it.

from app.core.database import Base  # noqa: F401, E402
from app.core.config import settings  # noqa: E402

# Import models (add new model files here as they're created)
from app.models.user import User, RefreshToken  # noqa: F401, E402
from app.models.store import Store, Counter, StoreManager  # noqa: F401, E402  — Phase 4
from app.models.queue import QueueSnapshot, AlertConfig  # noqa: F401, E402  — Phase 5
from app.models.camera import CameraZone  # noqa: F401, E402  — Phase 8
from app.models.notification import Notification  # noqa: F401, E402  — Phase 10
# from app.models.analytics import ...                  # Phase 11


# Target metadata for autogenerate
target_metadata = Base.metadata

# Override database URL with the one from application settings
# This ensures migrations use the same DB as the app (not a hardcoded URL)
config.set_main_option("sqlalchemy.url", settings.active_database_url)


# =============================================================================
# Migration Functions
# =============================================================================

def run_migrations_offline() -> None:
    """
    Run migrations in offline mode (without a live database connection).

    Used for generating SQL scripts (e.g., `alembic upgrade head --sql`).
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,           # Detect column type changes
        compare_server_default=True,  # Detect server default changes
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure Alembic context and run pending migrations."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations using an async SQLAlchemy engine.

    Required because we use asyncpg as our PostgreSQL driver.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # No connection pooling for migrations
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode (with live database connection)."""
    asyncio.run(run_async_migrations())


# Run the appropriate migration mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
