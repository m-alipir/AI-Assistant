"""Async SQLAlchemy engine lifecycle and readiness checks."""

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create the application's asynchronous PostgreSQL engine."""
    return create_async_engine(settings.database_url_string, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create sessions that do not implicitly commit transactions."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def check_database_ready(engine: AsyncEngine) -> bool:
    """Return whether the database accepts a trivial query without leaking connection details."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - readiness translates all driver failures to false
        return False
    return True


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield one request/job database session."""
    async with session_factory() as session:
        yield session
