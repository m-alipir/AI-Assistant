"""Small, bounded persistence helpers for cross-process runtime diagnostics."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import text


class RuntimeRunRecords:
    def __init__(self, sessions: Callable[[], Any]) -> None:
        self._sessions = sessions

    async def start(self, run_id: str, entry_point: str, started_at: datetime) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO runtime_run_records "
                    "(run_id, entry_point, status, started_at, details) "
                    "VALUES (:run_id, :entry_point, 'running', :started_at, '{}'::jsonb)"
                ),
                {"run_id": run_id, "entry_point": entry_point, "started_at": started_at},
            )

    async def finish(
        self,
        run_id: str,
        status: str,
        completed_at: datetime,
        details_json: str,
    ) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                text(
                    "UPDATE runtime_run_records SET status = :status, "
                    "completed_at = :completed_at, details = details || CAST(:details AS jsonb) "
                    "WHERE run_id = :run_id"
                ),
                {
                    "run_id": run_id,
                    "status": status,
                    "completed_at": completed_at,
                    "details": details_json,
                },
            )
            await session.execute(
                text(
                    "DELETE FROM runtime_run_records WHERE status <> 'running' AND run_id IN ("
                    "SELECT run_id FROM runtime_run_records WHERE status <> 'running' "
                    "ORDER BY started_at DESC OFFSET greatest(50 - (SELECT count(*) "
                    "FROM runtime_run_records WHERE status = 'running'), 0))"
                )
            )

    async def progress(self, run_id: str, details_json: str) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                text(
                    "UPDATE runtime_run_records SET details = details || CAST(:details AS jsonb) "
                    "WHERE run_id = :run_id"
                ),
                {"run_id": run_id, "details": details_json},
            )

    async def latest(self, limit: int = 10) -> list[dict[str, object]]:
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT run_id, entry_point, status, started_at, completed_at, details "
                        "FROM runtime_run_records ORDER BY started_at DESC LIMIT :limit"
                    ),
                    {"limit": min(max(limit, 1), 50)},
                )
            ).mappings().all()
        return [dict(row) for row in rows]

    async def delivery(self, run_id: str, outcome: str) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                text(
                    "UPDATE runtime_run_records SET details = details || "
                    "jsonb_build_object('telegram_delivery', CAST(:outcome AS text)) "
                    "WHERE run_id = :run_id"
                ),
                {"run_id": run_id, "outcome": outcome},
            )
