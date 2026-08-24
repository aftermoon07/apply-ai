"""
Async SQLAlchemy database engine and session management.

Uses aiosqlite for SQLite in development/V1.
The DATABASE_URL in .env can be changed to a PostgreSQL async URL for production.

Migration note: Alembic migrations use a synchronous engine. The async engine
is used exclusively by the application at runtime. Both are driven from the
same DATABASE_URL.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

# Module-level engine/session factory — initialized lazily via init_engine()
_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str, echo: bool = False) -> None:
    """
    Initialize the async engine and session factory.

    Must be called once at application startup before any DB operations.
    Idempotent — subsequent calls are no-ops unless force=True.
    """
    global _engine, _async_session_factory
    if _engine is not None:
        return

    # Ensure SQLite data directory exists
    if database_url.startswith("sqlite"):
        db_path_str = database_url.split("///")[-1]
        if db_path_str and db_path_str != ":memory:":
            Path(db_path_str).parent.mkdir(parents=True, exist_ok=True)

    _engine = create_async_engine(
        database_url,
        echo=echo,
        # SQLite-specific: enable WAL mode for better concurrency
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
    )

    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    logger.info("Database engine initialized: %s", _mask_url(database_url))


def reset_engine() -> None:
    """Tear down the engine. Use in tests to swap databases between test cases."""
    global _engine, _async_session_factory
    _engine = None
    _async_session_factory = None


def get_engine():
    """Return the current engine. Raises RuntimeError if not initialized."""
    if _engine is None:
        raise RuntimeError(
            "Database engine not initialized. Call init_engine() at startup."
        )
    return _engine


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager providing a database session.

    Usage:
        async with get_session() as session:
            result = await session.execute(...)
    """
    if _async_session_factory is None:
        raise RuntimeError(
            "Session factory not initialized. Call init_engine() at startup."
        )
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables() -> None:
    """
    Create all tables defined in ORM models.

    Used for testing with temporary databases.
    In production, use Alembic migrations instead.
    """
    from applyai.models.base import Base  # local import to avoid circular deps

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.debug("All tables created.")


async def drop_all_tables() -> None:
    """Drop all tables. Use in tests only — destructive."""
    from applyai.models.base import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.debug("All tables dropped.")


def _mask_url(url: str) -> str:
    """Mask credentials in a database URL for safe logging."""
    try:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url)
        if parsed.password:
            masked = parsed._replace(netloc=f"{parsed.username}:***@{parsed.hostname}")
            return urlunparse(masked)
    except Exception:
        pass
    return url
