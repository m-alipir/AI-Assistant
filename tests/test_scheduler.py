import asyncio
from datetime import UTC, date, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo

import pytest

import app.jobs.scheduler as scheduler_module
from app.jobs.scheduler import (
    DailyScheduler,
    GmailPollingScheduler,
    RuntimeRunCoordinator,
    _safe_summary,
    format_failure_summary,
)


@pytest.mark.asyncio
async def test_opt_in_scheduler_claims_day_once_without_external_calls() -> None:
    claims: set[datetime] = set()
    calls: list[str] = []

    async def claim(slot_at: datetime) -> bool:
        if slot_at in claims:
            return False
        claims.add(slot_at)
        return True

    async def run(_: datetime) -> dict[str, object]:
        calls.append("run")
        return {"status": "completed"}

    scheduler = DailyScheduler(True, "08:00", "Europe/Istanbul", run, claim)
    due = datetime(2026, 9, 7, 4, 45, tzinfo=UTC)  # 07:45 Istanbul; prep begins.
    target = datetime(2026, 9, 7, 8, 0, tzinfo=scheduler._timezone)
    assert await scheduler.run_due(due, target)
    assert not await scheduler.run_due(due, target)
    assert calls == ["run"]


@pytest.mark.asyncio
async def test_disabled_scheduler_never_claims_or_runs() -> None:
    async def unexpected_claim(slot_at: datetime) -> bool:
        raise AssertionError("disabled scheduler must not claim a slot")

    async def unexpected_run(_: datetime) -> dict[str, object]:
        raise AssertionError("disabled scheduler must not run")

    scheduler = DailyScheduler(False, "08:00", "Europe/Istanbul", unexpected_run, unexpected_claim)
    assert not await scheduler.run_due(datetime(2026, 9, 7, 6, 0, tzinfo=UTC))


@pytest.mark.asyncio
async def test_scheduler_can_apply_an_operator_preference_when_idle() -> None:
    scheduler = DailyScheduler(
        False, "08:00", "Europe/Istanbul", _unused_scheduled_run, _unused_claim
    )

    await scheduler.configure(True, "07:30")

    assert scheduler.state.enabled
    assert scheduler.state.daily_time == "07:30"
    await scheduler.stop()


@pytest.mark.asyncio
async def test_restart_cannot_claim_the_same_slot_and_records_safe_summary() -> None:
    claims: set[datetime] = set()
    records: list[tuple[datetime, str, str | None]] = []

    async def claim(slot_at: datetime) -> bool:
        if slot_at in claims:
            return False
        claims.add(slot_at)
        return True

    async def run(_: datetime) -> dict[str, object]:
        return {"status": "completed", "counts": {"processed": 0, "llm_calls": 0}}

    async def record(slot_at: datetime, status: str, summary: str | None) -> None:
        records.append((slot_at, status, summary))

    due = datetime(2026, 9, 7, 4, 45, tzinfo=UTC)
    first = DailyScheduler(True, "08:00", "Europe/Istanbul", run, claim, record)
    restarted = DailyScheduler(True, "08:00", "Europe/Istanbul", run, claim, record)
    target = datetime(2026, 9, 7, 8, 0, tzinfo=first._timezone)

    assert await first.run_due(due, target)
    assert not await restarted.run_due(due, target)
    assert restarted.state.last_skip_reason == "already_claimed_for_delivery_slot"
    assert records == [(target.astimezone(UTC), "completed", "processed=0; llm_calls=0")]


@pytest.mark.asyncio
async def test_changed_time_can_claim_a_second_delivery_slot_on_the_same_local_day() -> None:
    claims: set[datetime] = set()
    targets: list[datetime] = []

    async def claim(slot_at: datetime) -> bool:
        if slot_at in claims:
            return False
        claims.add(slot_at)
        return True

    async def run(target: datetime) -> dict[str, object]:
        targets.append(target)
        return {"status": "completed"}

    first = DailyScheduler(True, "14:00", "Europe/Istanbul", run, claim)
    second = DailyScheduler(True, "22:00", "Europe/Istanbul", run, claim)
    first_target = datetime(2026, 9, 26, 14, 0, tzinfo=first._timezone)
    second_target = datetime(2026, 9, 26, 22, 0, tzinfo=second._timezone)

    assert await first.run_due(first_target - timedelta(minutes=15), first_target)
    assert await second.run_due(second_target - timedelta(minutes=15), second_target)
    assert targets == [first_target, second_target]
    assert len(claims) == 2


@pytest.mark.asyncio
async def test_concurrent_instances_claim_the_same_delivery_slot_once() -> None:
    claims: set[datetime] = set()
    calls: list[datetime] = []

    async def claim(slot_at: datetime) -> bool:
        if slot_at in claims:
            return False
        claims.add(slot_at)
        await asyncio.sleep(0)
        return True

    async def run(target: datetime) -> dict[str, object]:
        calls.append(target)
        return {"status": "completed"}

    scheduler_a = DailyScheduler(True, "22:00", "Europe/Istanbul", run, claim)
    scheduler_b = DailyScheduler(True, "22:00", "Europe/Istanbul", run, claim)
    target = datetime(2026, 9, 26, 22, 0, tzinfo=scheduler_a._timezone)

    results = await asyncio.gather(
        scheduler_a.run_due(target - timedelta(minutes=15), target),
        scheduler_b.run_due(target - timedelta(minutes=15), target),
    )

    assert results.count(True) == 1
    assert results.count(False) == 1
    assert calls == [target]


@pytest.mark.asyncio
async def test_gmail_poll_scheduler_waits_interval_and_applies_updates_after_current_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_wait_for = asyncio.wait_for
    timeouts: list[float] = []
    calls = 0
    scheduler: GmailPollingScheduler

    class StopLoop(Exception):
        pass

    async def fake_wait_for(awaitable: object, *, timeout: float) -> None:
        timeouts.append(timeout)
        if hasattr(awaitable, "close"):
            awaitable.close()  # type: ignore[attr-defined]
        if len(timeouts) == 1:
            raise TimeoutError
        raise StopLoop

    async def run() -> None:
        nonlocal calls
        calls += 1
        await scheduler.configure(120)

    monkeypatch.setattr(scheduler_module.asyncio, "wait_for", fake_wait_for)
    scheduler = GmailPollingScheduler(True, 60, run)
    scheduler.start()

    with pytest.raises(StopLoop):
        await real_wait_for(scheduler._task, timeout=0.5)

    assert calls == 1
    assert timeouts == [3600, 7200]


@pytest.mark.asyncio
async def test_disabled_gmail_poll_scheduler_never_calls_gmail() -> None:
    async def unexpected_run() -> None:
        raise AssertionError("disabled Gmail polling must not call Gmail")

    scheduler = GmailPollingScheduler(False, 60, unexpected_run)
    scheduler.start()

    assert scheduler._task is None


@pytest.mark.asyncio
async def test_loop_retries_early_wakeup_without_skipping_consecutive_local_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_due = datetime(2026, 9, 23, 10, 45, tzinfo=UTC)
    second_due = datetime(2026, 9, 24, 10, 45, tzinfo=UTC)

    class ClockDateTime(datetime):
        # Advance across the configured 13:45 preparation start between due checks.
        current = first_due - timedelta(microseconds=3)

        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            current = cls.current
            cls.current += timedelta(microseconds=1)
            return current.astimezone(tz) if tz else current.replace(tzinfo=None)

    claims: set[datetime] = set()
    runs: list[date] = []
    sleeps = 0
    daily_sleeps = 0

    async def claim(slot_at: datetime) -> bool:
        if slot_at in claims:
            return False
        claims.add(slot_at)
        return True

    async def run(target: datetime) -> dict[str, object]:
        runs.append(target.date())
        return {"status": "completed"}

    async def fake_sleep(seconds: float) -> None:
        nonlocal daily_sleeps, sleeps
        sleeps += 1
        if sleeps == 1:
            ClockDateTime.current = first_due - timedelta(microseconds=1)
        elif seconds > 3600:
            daily_sleeps += 1
            if daily_sleeps == 2:
                raise StopLoop
            ClockDateTime.current += timedelta(seconds=seconds) - timedelta(microseconds=1)
        else:
            ClockDateTime.current += timedelta(seconds=seconds)

    class StopLoop(Exception):
        pass

    monkeypatch.setattr(scheduler_module, "datetime", ClockDateTime)
    monkeypatch.setattr(scheduler_module.asyncio, "sleep", fake_sleep)
    scheduler = DailyScheduler(True, "14:00", "Europe/Istanbul", run, claim)
    scheduler.state.last_skip_reason = "already_claimed_for_delivery_slot"

    with pytest.raises(StopLoop):
        await scheduler._loop()

    assert runs == [first_due.date(), second_due.date()]
    assert [slot.date() for slot in sorted(claims)] == runs


def test_next_run_uses_istanbul_local_clock() -> None:
    scheduler = DailyScheduler(
        True, "08:00", "Europe/Istanbul", _unused_scheduled_run, _unused_claim
    )
    # 07:30 UTC is 10:30 local, so the next occurrence is the following Istanbul day.
    next_run = scheduler.next_at(datetime(2026, 9, 7, 7, 30, tzinfo=UTC))
    assert next_run.isoformat() == "2026-09-08T08:00:00+03:00"


@pytest.mark.asyncio
async def test_fall_back_second_hour_skips_the_first_occurrence_target() -> None:
    timezone = ZoneInfo("America/New_York")
    scheduler = DailyScheduler(
        True, "01:30", "America/New_York", _unused_scheduled_run, _unused_claim
    )
    second_one_am = datetime(2026, 11, 1, 1, 0, tzinfo=timezone, fold=1)

    target = scheduler.next_at(second_one_am)
    preparation = scheduler.next_preparation_at(second_one_am)

    assert target == datetime(2026, 11, 2, 1, 30, tzinfo=timezone)
    assert target.astimezone(UTC) > second_one_am.astimezone(UTC)
    assert preparation.astimezone(UTC) > second_one_am.astimezone(UTC)
    assert not await scheduler.run_due(second_one_am)


def test_preparation_starts_fifteen_minutes_before_configured_time() -> None:
    scheduler = DailyScheduler(
        True, "09:37", "Europe/Istanbul", _unused_scheduled_run, _unused_claim
    )
    preparation = scheduler.next_preparation_at(datetime(2026, 9, 7, 5, 0, tzinfo=UTC))

    assert preparation.isoformat() == "2026-09-07T09:22:00+03:00"


def test_spring_forward_preparation_is_fifteen_real_minutes_before_target() -> None:
    timezone = ZoneInfo("America/New_York")
    scheduler = DailyScheduler(
        True, "03:00", "America/New_York", _unused_scheduled_run, _unused_claim
    )
    before_target = datetime(2026, 3, 8, 0, 30, tzinfo=timezone)

    target = scheduler.next_at(before_target)
    preparation = scheduler.next_preparation_at(before_target)

    assert target.isoformat() == "2026-03-08T03:00:00-04:00"
    assert preparation.isoformat() == "2026-03-08T01:45:00-05:00"
    assert (target.astimezone(UTC) - preparation.astimezone(UTC)).total_seconds() == 900


def test_scheduled_failure_summaries_keep_only_fixed_safe_counters() -> None:
    result = {
        "status": "completed_with_errors",
        "message": "do not include source URL or provider output",
        "counts": {
            "processed": 8,
            "failed": 4,
            "budget_exhausted": 250,
            "llm_calls": 42,
            "llm_cache_hits": 0,
            "failure_categories": {
                "source_fetch_error": 1,
                "budget_exhausted": 250,
                "provider_payload": "private provider text",
            },
            "youtube": {
                "processed": 0,
                "failed": 2,
                "failure_categories": {"youtube_feed_access_error": 2},
            },
            "gmail": {"processed": 0, "failed": 0, "failure_categories": {}},
        },
    }

    persisted = _safe_summary(result)
    warning = format_failure_summary(result)

    assert "processed=8" in persisted and "llm_calls=42" in persisted
    assert "rss_budget_exhausted_skipped=250" in persisted
    assert "rss_source_fetch_error=1" in persisted
    assert "provider_payload" not in persisted
    assert "private provider text" not in persisted
    assert "do not include source URL" not in persisted
    assert warning == "RSS: 4 öğe; YouTube: 2 öğe"
    assert "budget_exhausted" not in warning
    assert "private provider text" not in warning
    assert len(warning) <= 350


def test_failure_summary_uses_only_actual_failed_item_counts() -> None:
    warning = format_failure_summary(
        {
            "counts": {
                "failed": 4,
                "youtube": {"failed": 2},
            }
        }
    )

    assert warning == "RSS: 4 öğe; YouTube: 2 öğe"


def test_budget_exhaustion_alone_does_not_create_a_failure_warning() -> None:
    warning = format_failure_summary(
        {
            "status": "completed",
            "counts": {
                "failed": 0,
                "budget_exhausted": 250,
                "failure_categories": {"budget_exhausted": 250},
                "youtube": {
                    "failed": 0,
                    "budget_exhausted": 100,
                    "failure_categories": {"budget_exhausted": 100},
                },
            },
        }
    )

    assert warning == ""


@pytest.mark.asyncio
async def test_scheduler_claim_uses_target_date_when_preparation_crosses_midnight() -> None:
    claims: list[datetime] = []
    targets: list[datetime] = []

    async def claim(slot_at: datetime) -> bool:
        if slot_at in claims:
            return False
        claims.append(slot_at)
        return True

    async def run(target: datetime) -> dict[str, object]:
        targets.append(target)
        return {"status": "completed"}

    scheduler = DailyScheduler(True, "00:05", "Europe/Istanbul", run, claim)
    before_prep = datetime(2026, 9, 24, 20, 49, tzinfo=UTC)  # 23:49 Istanbul.
    prep = datetime(2026, 9, 24, 20, 50, tzinfo=UTC)  # 23:50 Istanbul.
    target = datetime(2026, 9, 25, 0, 5, tzinfo=scheduler._timezone)

    assert not await scheduler.run_due(before_prep)
    assert await scheduler.run_due(prep, target)
    assert not await scheduler.run_due(prep, target)
    assert claims == [target.astimezone(UTC)]
    assert targets == [target]


@pytest.mark.asyncio
async def test_wait_until_never_returns_before_target_even_after_early_sleep_wakeup() -> None:
    current = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)
    target = current + timedelta(seconds=5)
    waits = 0

    def now() -> datetime:
        return current

    async def sleep(seconds: float) -> None:
        nonlocal current, waits
        waits += 1
        current += timedelta(seconds=min(seconds, 2))

    result = await scheduler_module.wait_until(target, now=now, sleep=sleep)

    assert result >= target
    assert waits == 3


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


async def _unused_scheduled_run(_: datetime) -> dict[str, object]:
    raise AssertionError("unexpected scheduled runtime call")


async def _unused_claim(_: datetime) -> bool:
    raise AssertionError("unexpected day claim")
