"""Opt-in daily scheduler with durable per-day claims."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

RunCallback = Callable[[], Awaitable[dict[str, object]]]
ClaimDay = Callable[[date], Awaitable[bool]]
RecordResult = Callable[[date, str, str | None], Awaitable[None]]


@dataclass
class SchedulerState:
    enabled: bool
    timezone: str
    daily_time: str
    last_run: str | None = None
    next_run: str | None = None
    last_run_at: str | None = None
    last_summary: str | None = None
    last_error: str | None = None
    last_skip_reason: str | None = None
    running: bool = False


class RuntimeRunCoordinator:
    """Process-local non-blocking guard shared by manual and scheduled operations."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.active_kind: str | None = None

    async def run(self, kind: str, callback: RunCallback) -> dict[str, object]:
        """Run once or return a safe skip rather than queueing concurrent expensive work."""
        if self._lock.locked():
            active = self.active_kind or "another"
            return {
                "status": "completed_skipped",
                "counts": {},
                "message": f"Run skipped: {active}_run_active.",
                "skip_reason": "another_run_active",
            }
        await self._lock.acquire()
        self.active_kind = kind
        try:
            return await callback()
        finally:
            self.active_kind = None
            self._lock.release()


class DailyScheduler:
    """One daily opt-in job; durable claiming prevents restart double-runs."""

    def __init__(
        self,
        enabled: bool,
        daily_time: str,
        timezone: str,
        run: RunCallback,
        claim: ClaimDay,
        record_result: RecordResult | None = None,
    ) -> None:
        self._timezone = ZoneInfo(timezone)
        self._at = time.fromisoformat(daily_time)
        self._run, self._claim = run, claim
        self.state = SchedulerState(enabled, timezone, daily_time)
        self._record_result = record_result
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self.state.enabled and self._task is None:
            self.state.next_run = self.next_at().isoformat()
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def next_at(self, now: datetime | None = None) -> datetime:
        local_now = (now or datetime.now(UTC)).astimezone(self._timezone)
        candidate = datetime.combine(local_now.date(), self._at, tzinfo=self._timezone)
        if candidate <= local_now:
            candidate += timedelta(days=1)
        return candidate

    async def run_due(self, now: datetime | None = None) -> bool:
        local_now = (now or datetime.now(UTC)).astimezone(self._timezone)
        if not self.state.enabled or local_now.time() < self._at:
            return False
        if not await self._claim(local_now.date()):
            self.state.last_skip_reason = "already_claimed_for_local_day"
            return False
        self.state.running = True
        self.state.last_run_at = local_now.isoformat()
        try:
            result = await self._run()
            status = str(result.get("status", "completed"))
            summary = _safe_summary(result)
            self.state.last_run = status
            self.state.last_summary = summary
            self.state.last_skip_reason = (
                str(result.get("skip_reason")) if result.get("skip_reason") else None
            )
            self.state.last_error = (
                "scheduled_run_completed_with_errors"
                if status in {"failed", "completed_with_errors"}
                else None
            )
            if self._record_result:
                await self._record_result(local_now.date(), status, summary)
        except Exception:
            self.state.last_run = "failed"
            self.state.last_error = "scheduled_run_failed"
            self.state.last_summary = "Scheduled run failed safely."
            if self._record_result:
                await self._record_result(local_now.date(), "failed", self.state.last_summary)
        finally:
            self.state.running = False
            self.state.next_run = self.next_at(local_now).isoformat()
        return True

    async def _loop(self) -> None:
        while True:
            next_run = self.next_at()
            self.state.next_run = next_run.isoformat()
            await asyncio.sleep(max((next_run - datetime.now(UTC)).total_seconds(), 1))
            await self.run_due()


def _safe_summary(result: dict[str, object]) -> str:
    """Persist only aggregate operational counts, never source or provider payloads."""
    counts = result.get("counts")
    if not isinstance(counts, dict):
        return "Scheduled run completed."
    fields = ("processed", "failed", "llm_calls", "llm_cache_hits")
    parts = [f"{field}={counts[field]}" for field in fields if field in counts]
    youtube = counts.get("youtube")
    if isinstance(youtube, dict):
        parts.extend(
            f"youtube_{field}={youtube[field]}"
            for field in ("processed", "failed")
            if field in youtube
        )
    gmail = counts.get("gmail")
    if isinstance(gmail, dict):
        parts.extend(
            f"gmail_{field}={gmail[field]}"
            for field in ("processed", "failed")
            if field in gmail
        )
    return "; ".join(parts) if parts else "No new items; no briefing/editor work."
