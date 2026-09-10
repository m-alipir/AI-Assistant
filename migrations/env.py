"""Alembic environment for asynchronous PostgreSQL migrations."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from app.config.settings import get_settings
from app.db import (
    agent_api_models,  # noqa: F401
    email_models,  # noqa: F401
    llm_models,  # noqa: F401
)
from app.db.base import Base
from app.db.session import create_engine
from app.knowledge import models  # noqa: F401

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url_string)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without opening a database connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations against an existing synchronous connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Create a temporary async engine, migrate, then release all resources."""
    connectable = create_engine(settings)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
