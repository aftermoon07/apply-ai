"""
Alembic environment configuration.

Uses a synchronous SQLAlchemy connection for migrations (Alembic requirement),
while the application itself uses the async engine at runtime.

The DATABASE_URL environment variable overrides alembic.ini at runtime.
SQLite is the default; PostgreSQL is supported via async connection.
"""

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import all models so Alembic can detect them for autogenerate
import applyai.models  # noqa: F401
from applyai.models.base import Base

# Alembic Config object — access to .ini values
config = context.config

# Set up Python logging from the .ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate support
target_metadata = Base.metadata


def get_url() -> str:
    """
    Resolve the database URL.

    Priority:
      1. DATABASE_URL environment variable (set in .env)
      2. alembic.ini sqlalchemy.url value

    Note: Alembic uses a SYNC driver (sqlite:///).
    The application runtime uses an ASYNC driver (sqlite+aiosqlite:///).
    Strip the async driver prefix for migrations.
    """
    url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url", "")
    # Convert async URL to sync for Alembic
    return url.replace("sqlite+aiosqlite://", "sqlite:///").replace(
        "postgresql+asyncpg://", "postgresql://"
    )


def run_migrations_offline() -> None:
    """Run migrations without a DB connection — generates SQL scripts."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live DB connection."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
