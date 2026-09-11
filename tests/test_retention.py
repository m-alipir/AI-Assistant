from datetime import UTC, datetime

import pytest

from app.jobs.retention import RetentionJob


class _Result:
    rowcount = 1


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


class _Session(_Transaction):
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, object]]] = []

    def begin(self) -> _Transaction:
        return _Transaction()

    async def execute(self, statement, params: dict[str, object]) -> _Result:
        self.executed.append((str(statement), params))
        return _Result()


@pytest.mark.asyncio
async def test_retention_expires_raw_and_operational_data_without_deleting_knowledge() -> None:
    session = _Session()
    job = RetentionJob(lambda: session, public_raw_days=30, operational_days=90)

    counts = await job.run(datetime(2026, 9, 10, tzinfo=UTC))

    assert counts == {
        "events_raw_expired": 1,
        "agent_audit_deleted": 1,
        "notification_history_deleted": 1,
        "telegram_updates_deleted": 1,
        "telegram_feedback_tokens_deleted": 1,
        "rsshub_metrics_deleted": 1,
        "llm_metadata_deleted": 1,
    }
    sql = "\n".join(statement for statement, _ in session.executed)
    assert "UPDATE events SET raw_content = NULL" in sql
    assert "DELETE FROM events" not in sql
    assert "claims" not in sql and "inferences" not in sql and "event_sources" not in sql
    assert all("cutoff" in params for _, params in session.executed)
