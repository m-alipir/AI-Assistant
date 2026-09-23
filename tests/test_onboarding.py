"""Opt-in PostgreSQL coverage for persisted onboarding preferences."""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config.onboarding import OnboardingRepository, SchedulerPreference

DATABASE_URL = os.environ.get("MANAGED_SOURCE_INTEGRATION_DATABASE_URL")


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="set MANAGED_SOURCE_INTEGRATION_DATABASE_URL to a disposable migrated PostgreSQL DB",
)
@pytest.mark.asyncio
async def test_scheduler_preference_persists_in_postgres() -> None:
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    repository = OnboardingRepository(async_sessionmaker(engine, expire_on_commit=False))
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert revision == "20260923_0028"

        assert await repository.scheduler_preference() is None
        await repository.save_scheduler_preference(
            SchedulerPreference(enabled=True, daily_time="07:30")
        )
        assert await repository.scheduler_preference() == SchedulerPreference(
            enabled=True, daily_time="07:30"
        )
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE control_center_settings SET scheduler_enabled = NULL, "
                    "scheduler_daily_time = NULL WHERE id"
                )
            )
        await engine.dispose()
