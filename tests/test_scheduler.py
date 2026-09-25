import asyncio
from datetime import UTC, date, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo

import pytest

import app.jobs.scheduler as scheduler_module
from app.jobs.scheduler import (
    DailyScheduler,
    RuntimeRunCoordinator,
    _safe_summary,
    format_failure_summary,
)


@pytest.mark.asyncio
async def test_opt_in_scheduler_claims_day_once_without_external_calls() -> None:
    claims: set[date] = set()
    calls: list[str] = []

    async def claim(day: date) -> bool:
        if day in claims:
            return False
        claims.add(day)
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
    async def unexpected_claim(day: date) -> bool:
        raise AssertionError("disabled scheduler must not claim a day")

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
async def test_restart_cannot_claim_a_second_istanbul_local_day_and_records_safe_summary() -> None:
    claims: set[date] = set()
    records: list[tuple[date, str, str | None]] = []

    async def claim(day: date) -> bool:
        if day in claims:
            return False
        claims.add(day)
        return True

    async def run(_: datetime) -> dict[str, object]:
        return {"status": "completed", "counts": {"processed": 0, "llm_calls": 0}}

    async def record(day: date, status: str, summary: str | None) -> None:
        records.append((day, status, summary))

    due = datetime(2026, 9, 7, 4, 45, tzinfo=UTC)
    first = DailyScheduler(True, "08:00", "Europe/Istanbul", run, claim, record)
    restarted = DailyScheduler(True, "08:00", "Europe/Istanbul", run, claim, record)
    target = datetime(2026, 9, 7, 8, 0, tzinfo=first._timezone)

    assert await first.run_due(due, target)
    assert not await restarted.run_due(due, target)
    assert restarted.state.last_skip_reason == "already_claimed_for_local_day"
    assert records == [(date(2026, 9, 7), "completed", "processed=0; llm_calls=0")]


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

    claims: set[date] = set()
    runs: list[date] = []
    sleeps = 0
    daily_sleeps = 0

    async def claim(day: date) -> bool:
        if day in claims:
            return False
        claims.add(day)
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
    scheduler.state.last_skip_reason = "already_claimed_for_local_day"

    with pytest.raises(StopLoop):
        await scheduler._loop()

    assert runs == [first_due.date(), second_due.date()]
    assert claims == set(runs)


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
            "llm_calls": 42,
            "llm_cache_hits": 0,
            "failure_categories": {
                "source_fetch_error": 1,
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
    assert "rss_source_fetch_error=1" in persisted
    assert "provider_payload" not in persisted
    assert "private provider text" not in persisted
    assert "do not include source URL" not in persisted
    assert "RSS: başarısız=4, source_fetch_error=1" in warning
    assert "YouTube: başarısız=2, youtube_feed_access_error=2" in warning
    assert "private provider text" not in warning
    assert len(warning) <= 350


def test_missing_historical_categories_are_reported_as_unknown() -> None:
    warning = format_failure_summary(
        {
            "counts": {
                "failed": 4,
                "youtube": {"failed": 2},
            }
        }
    )

    assert "RSS: başarısız=4, hata türü sayımı yok" in warning
    assert "YouTube: başarısız=2, hata türü sayımı yok" in warning


@pytest.mark.asyncio
async def test_scheduler_claim_uses_target_date_when_preparation_crosses_midnight() -> None:
    claims: list[date] = []
    targets: list[datetime] = []

    async def claim(day: date) -> bool:
        if day in claims:
            return False
        claims.append(day)
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
    assert claims == [date(2026, 9, 25)]
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


async def _unused_claim(_: date) -> bool:
    raise AssertionError("unexpected day claim")
