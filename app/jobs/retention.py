"""Bounded, opt-in PostgreSQL retention maintenance."""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


class RetentionJob:
    """Expire raw public content and old operational metadata without deleting knowledge."""

    def __init__(
        self,
        sessions: Callable[[], Any],
        *,
        public_raw_days: int,
        operational_days: int,
    ) -> None:
        self._sessions = sessions
        self._public_raw_days = public_raw_days
        self._operational_days = operational_days

    async def run(self, now: datetime | None = None) -> dict[str, int]:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        raw_cutoff = current - timedelta(days=self._public_raw_days)
        operational_cutoff = current - timedelta(days=self._operational_days)
        statements = {
            "events_raw_expired": (
                "UPDATE events SET raw_content = NULL "
                "WHERE raw_content IS NOT NULL AND occurred_at < :cutoff",
                raw_cutoff,
            ),
            "agent_audit_deleted": (
                "DELETE FROM agent_api_audit_log WHERE occurred_at < :cutoff",
                operational_cutoff,
            ),
            "notification_history_deleted": (
                "DELETE FROM notification_deliveries WHERE updated_at < :cutoff",
                operational_cutoff,
            ),
            "telegram_updates_deleted": (
                "DELETE FROM telegram_updates WHERE updated_at < :cutoff",
                operational_cutoff,
            ),
            "telegram_feedback_tokens_deleted": (
                "DELETE FROM telegram_feedback_tokens WHERE expires_at < :now",
                current,
            ),
            "rsshub_metrics_deleted": (
                "DELETE FROM rsshub_pilot_route_observations WHERE observed_at < :cutoff",
                operational_cutoff,
            ),
            "llm_metadata_deleted": (
                "DELETE FROM llm_calls WHERE created_at < :cutoff",
                operational_cutoff,
            ),
        }
        counts: dict[str, int] = {}
        async with self._sessions() as session, session.begin():
            for name, (statement, cutoff) in statements.items():
                result = await session.execute(text(statement), {"cutoff": cutoff})
                counts[name] = max(int(result.rowcount or 0), 0)
        return counts


class RetentionScheduler:
    """Run maintenance immediately and periodically without provider work."""

    def __init__(self, job: RetentionJob, interval_hours: int) -> None:
        self._job = job
        self._interval_seconds = interval_hours * 60 * 60
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                counts = await self._job.run()
                logger.info("retention_completed", extra={"counts": counts})
            except Exception:
                logger.warning("retention_failed", extra={"category": "database_error"})
            await asyncio.sleep(self._interval_seconds)
