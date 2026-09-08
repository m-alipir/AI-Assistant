import asyncio
from datetime import UTC, date, datetime

import pytest

from app.jobs.scheduler import DailyScheduler, RuntimeRunCoordinator


@pytest.mark.asyncio
async def test_opt_in_scheduler_claims_day_once_without_external_calls() -> None:
    claims: set[date] = set()
    calls: list[str] = []

    async def claim(day: date) -> bool:
        if day in claims:
            return False
        claims.add(day)
        return True

    async def run() -> dict[str, object]:
        calls.append("run")
        return {"status": "completed"}

    scheduler = DailyScheduler(True, "08:00", "Europe/Istanbul", run, claim)
    due = datetime(2026, 9, 7, 6, 0, tzinfo=UTC)  # 09:00 Istanbul.
    assert await scheduler.run_due(due)
    assert not await scheduler.run_due(due)
    assert calls == ["run"]


@pytest.mark.asyncio
async def test_disabled_scheduler_never_claims_or_runs() -> None:
    async def unexpected_claim(day: date) -> bool:
        raise AssertionError("disabled scheduler must not claim a day")

    async def unexpected_run() -> dict[str, object]:
        raise AssertionError("disabled scheduler must not run")

    scheduler = DailyScheduler(False, "08:00", "Europe/Istanbul", unexpected_run, unexpected_claim)
    assert not await scheduler.run_due(datetime(2026, 9, 7, 6, 0, tzinfo=UTC))


@pytest.mark.asyncio
async def test_restart_cannot_claim_a_second_istanbul_local_day_and_records_safe_summary() -> None:
    claims: set[date] = set()
    records: list[tuple[date, str, str | None]] = []

    async def claim(day: date) -> bool:
        if day in claims:
            return False
        claims.add(day)
        return True

    async def run() -> dict[str, object]:
        return {"status": "completed", "counts": {"processed": 0, "llm_calls": 0}}

    async def record(day: date, status: str, summary: str | None) -> None:
        records.append((day, status, summary))

    due = datetime(2026, 9, 7, 6, 0, tzinfo=UTC)
    first = DailyScheduler(True, "08:00", "Europe/Istanbul", run, claim, record)
    restarted = DailyScheduler(True, "08:00", "Europe/Istanbul", run, claim, record)

    assert await first.run_due(due)
    assert not await restarted.run_due(due)
    assert restarted.state.last_skip_reason == "already_claimed_for_local_day"
    assert records == [(date(2026, 9, 7), "completed", "processed=0; llm_calls=0")]


def test_next_run_uses_istanbul_local_clock() -> None:
    scheduler = DailyScheduler(True, "08:00", "Europe/Istanbul", _unused_run, _unused_claim)
    # 07:30 UTC is 10:30 local, so the next occurrence is the following Istanbul day.
    next_run = scheduler.next_at(datetime(2026, 9, 7, 7, 30, tzinfo=UTC))
    assert next_run.isoformat() == "2026-09-08T08:00:00+03:00"


@pytest.mark.asyncio
async def test_manual_and_scheduled_collision_skips_without_queuing_provider_work() -> None:
    coordinator = RuntimeRunCoordinator()
    started = asyncio.Event()
    release = asyncio.Event()
    calls: list[str] = []

    async def manual() -> dict[str, object]:
        calls.append("manual")
        started.set()
        await release.wait()
        return {"status": "completed", "counts": {"processed": 1}}

    manual_task = asyncio.create_task(coordinator.run("manual", manual))
    await started.wait()
    skipped = await coordinator.run("scheduled", _unused_run)
    release.set()
    await manual_task

    assert skipped["status"] == "completed_skipped"
    assert skipped["skip_reason"] == "another_run_active"
    assert calls == ["manual"]


async def _unused_run() -> dict[str, object]:
    raise AssertionError("unexpected runtime call")


async def _unused_claim(_: date) -> bool:
    raise AssertionError("unexpected day claim")
