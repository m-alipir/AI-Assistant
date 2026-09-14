"""Small persisted preferences owned by the Control Center onboarding flow."""

from __future__ import annotations

from datetime import time

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SchedulerPreference(BaseModel):
    enabled: bool = False
    daily_time: str = Field(default="08:00", min_length=5, max_length=5)

    @field_validator("daily_time")
    @classmethod
    def valid_daily_time(cls, value: str) -> str:
        try:
            parsed = time.fromisoformat(value)
        except ValueError as error:
            raise ValueError("daily_time must use HH:MM") from error
        if parsed.second or parsed.microsecond:
            raise ValueError("daily_time must use HH:MM")
        return f"{parsed.hour:02d}:{parsed.minute:02d}"


class OnboardingRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def scheduler_preference(self) -> SchedulerPreference | None:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT scheduler_enabled, scheduler_daily_time "
                        "FROM control_center_settings WHERE id"
                    )
                )
            ).mappings().one_or_none()
        if row is None or row["scheduler_enabled"] is None:
            return None
        return SchedulerPreference(
            enabled=bool(row["scheduler_enabled"]), daily_time=str(row["scheduler_daily_time"])
        )

    async def save_scheduler_preference(self, preference: SchedulerPreference) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                text(
                    "UPDATE control_center_settings SET scheduler_enabled = :enabled, "
                    "scheduler_daily_time = :daily_time WHERE id"
                ),
                preference.model_dump(),
            )
