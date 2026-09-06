"""FastAPI application factory and production ASGI entrypoint."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.health import router as health_router
from app.config.settings import Settings, get_settings
from app.db.session import check_database_ready, create_engine
from app.observability.logging import configure_logging

ReadinessCheck = Callable[[], Awaitable[bool]]


def create_app(
    settings: Settings | None = None,
    readiness_check: ReadinessCheck | None = None,
) -> FastAPI:
    """Build the API with injectable readiness behavior for isolated unit tests."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)
    engine: AsyncEngine | None = None

    if readiness_check is None:
        engine = create_engine(active_settings)

        async def database_readiness() -> bool:
            assert engine is not None
            return await check_database_ready(engine)

        readiness_check = database_readiness

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI) -> AsyncIterator[None]:
        yield
        if lifespan_app.state.engine is not None:
            await lifespan_app.state.engine.dispose()

    app = FastAPI(
        title="Personal Intelligence System",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.readiness_check = readiness_check
    app.state.engine = engine
    app.include_router(health_router)

    logging.getLogger(__name__).info(
        "application_configured",
        extra={"environment": active_settings.app_env},
    )
    return app


app = create_app()
