"""Opt-in daily scheduler with durable delivery-slot claims."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

RunCallback = Callable[[], Awaitable[dict[str, object]]]
ScheduledRunCallback = Callable[[datetime], Awaitable[dict[str, object]]]
ClaimSlot = Callable[[datetime], Awaitable[bool]]
RecordResult = Callable[[datetime, str, str | None], Awaitable[None]]
PREPARATION_LEAD = timedelta(minutes=15)
logger = logging.getLogger(__name__)

SAFE_FAILURE_CATEGORIES = {
    "rss": (
        "briefing_render_error",
        "briefing_persistence_error",
        "gatekeeper_error",
        "extractor_error",
        "article_fetch_error",
        "event_persistence_error",
        "item_processing_error",
        "source_fetch_error",
        "source_cooldown",
        "source_health_persistence_error",
        "provider_busy",
    ),
    "youtube": (
        "youtube_feed_access_error",
        "yt_dlp_caption_access_error",
        "gatekeeper_error",
        "extractor_error",
        "event_persistence_error",
        "briefing_item_error",
        "processing_error",
        "source_health_persistence_error",
        "provider_busy",
    ),
    "gmail": ("account_access_error", "classification_error", "checkpoint_error"),
}


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
        run: ScheduledRunCallback,
        claim: ClaimSlot,
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

    async def configure(self, enabled: bool, daily_time: str) -> None:
        """Apply a persisted operator choice without interrupting an active run."""
        if self.state.running:
            raise RuntimeError("scheduler is running")
        await self.stop()
        self._at = time.fromisoformat(daily_time)
        self.state.enabled = enabled
        self.state.daily_time = daily_time
        self.state.next_run = None
        self.start()

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def next_at(self, now: datetime | None = None) -> datetime:
        """Return the next configured local delivery target, not its prep start."""
        local_now = (now or datetime.now(UTC)).astimezone(self._timezone)
        return self._next_delivery_at(local_now)

    def next_preparation_at(self, now: datetime | None = None) -> datetime:
        """Return the next prep start, including a prep interval that began yesterday."""
        return self._preparation_at(self.next_at(now))

    def _preparation_at(self, delivery_target_at: datetime) -> datetime:
        target_utc = delivery_target_at.astimezone(UTC)
        return (target_utc - PREPARATION_LEAD).astimezone(self._timezone)

    def _next_delivery_at(self, local_now: datetime) -> datetime:
        candidate = datetime.combine(local_now.date(), self._at, tzinfo=self._timezone)
        return (
            candidate
            if candidate.astimezone(UTC) > local_now.astimezone(UTC)
            else candidate + timedelta(days=1)
        )

    async def run_due(
        self,
        now: datetime | None = None,
        delivery_target_at: datetime | None = None,
    ) -> bool:
        local_now = (now or datetime.now(UTC)).astimezone(self._timezone)
        if not self.state.enabled:
            return False
        self.state.last_skip_reason = None
        if delivery_target_at is None:
            local_now_utc = local_now.astimezone(UTC)
            candidates = (
                datetime.combine(local_now.date(), self._at, tzinfo=self._timezone),
                datetime.combine(
                    local_now.date() + timedelta(days=1),
                    self._at,
                    tzinfo=self._timezone,
                ),
            )
            delivery_target_at = next(
                (
                    target
                    for target in candidates
                    if target.astimezone(UTC) - PREPARATION_LEAD
                    <= local_now_utc
                    < target.astimezone(UTC)
                ),
                None,
            )
        else:
            delivery_target_at = delivery_target_at.astimezone(self._timezone)
        if delivery_target_at is None or (
            local_now.astimezone(UTC)
            < delivery_target_at.astimezone(UTC) - PREPARATION_LEAD
        ):
            return False
        slot_at = delivery_target_at.astimezone(UTC)
        if not await self._claim(slot_at):
            self.state.last_skip_reason = "already_claimed_for_delivery_slot"
            return False
        self.state.running = True
        self.state.last_run_at = local_now.isoformat()
        try:
            result = await self._run(delivery_target_at)
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
                await self._record_result(slot_at, status, summary)
        except Exception:
            self.state.last_run = "failed"
            self.state.last_error = "scheduled_run_failed"
            self.state.last_summary = "Scheduled run failed safely."
            if self._record_result:
                await self._record_result(slot_at, "failed", self.state.last_summary)
        finally:
            self.state.running = False
            self.state.next_run = (delivery_target_at + timedelta(days=1)).isoformat()
        return True

    async def _loop(self) -> None:
        target_at = self.next_at()
        while True:
            preparation_at = self._preparation_at(target_at)
            self.state.next_run = target_at.isoformat()
            await asyncio.sleep(
                max((preparation_at - datetime.now(UTC)).total_seconds(), 1)
            )
            while True:
                if await self.run_due(delivery_target_at=target_at):
                    target_at += timedelta(days=1)
                    break
                if (
                    not self.state.enabled
                    or self.state.last_skip_reason == "already_claimed_for_delivery_slot"
                ):
                    if self.state.last_skip_reason == "already_claimed_for_delivery_slot":
                        target_at += timedelta(days=1)
                    break
                await asyncio.sleep(
                    max((preparation_at - datetime.now(UTC)).total_seconds(), 1)
                )
            if not self.state.enabled:
                return


class GmailPollingScheduler:
    """Read-only Gmail sync on a persisted, bounded interval; never pushes immediately."""

    def __init__(
        self,
        enabled: bool,
        interval_minutes: int,
        run: Callable[[], Awaitable[None]],
    ) -> None:
        self._enabled = enabled
        self.interval_minutes = interval_minutes
        self._run = run
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._enabled and self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def configure(self, interval_minutes: int) -> None:
        if not 15 <= interval_minutes <= 1440:
            raise ValueError("Gmail polling interval must be between 15 and 1440 minutes")
        self.interval_minutes = interval_minutes
        self._wake.set()

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
        while self._enabled:
            self._wake.clear()
            try:
                await asyncio.wait_for(
                    self._wake.wait(), timeout=self.interval_minutes * 60
                )
                continue
            except TimeoutError:
                pass
            try:
                await self._run()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("gmail_poll_scheduler_failed", extra={"category": "safe_failure"})


async def wait_until(
    target_at: datetime,
    *,
    now: Callable[[], datetime],
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> datetime:
    """Wait for an aware timestamp, rechecking the clock after early sleep wakeups."""
    target_utc = target_at.astimezone(UTC)
    while True:
        current = now().astimezone(UTC)
        remaining = (target_utc - current).total_seconds()
        if remaining <= 0:
            return current
        await sleep(remaining)


def _safe_summary(result: dict[str, object]) -> str:
    """Persist only aggregate operational counts, never source or provider payloads."""
    counts = result.get("counts")
    if not isinstance(counts, dict):
        return "Scheduled run completed."
    fields = ("processed", "failed", "llm_calls", "llm_cache_hits")
    parts = [
        f"{field}={counts[field]}"
        for field in fields
        if isinstance(counts.get(field), int)
        and not isinstance(counts.get(field), bool)
        and counts[field] >= 0
    ]
    budget_skips = counts.get("budget_exhausted")
    if isinstance(budget_skips, int) and not isinstance(budget_skips, bool) and budget_skips >= 0:
        parts.append(f"rss_budget_exhausted_skipped={budget_skips}")
    youtube = counts.get("youtube")
    if isinstance(youtube, dict):
        parts.extend(
            f"youtube_{field}={youtube[field]}"
            for field in ("processed", "failed")
            if isinstance(youtube.get(field), int)
            and not isinstance(youtube.get(field), bool)
            and youtube[field] >= 0
        )
        youtube_budget_skips = youtube.get("budget_exhausted")
        if (
            isinstance(youtube_budget_skips, int)
            and not isinstance(youtube_budget_skips, bool)
            and youtube_budget_skips >= 0
        ):
            parts.append(f"youtube_budget_exhausted_skipped={youtube_budget_skips}")
    gmail = counts.get("gmail")
    if isinstance(gmail, dict):
        parts.extend(
            f"gmail_{field}={gmail[field]}"
            for field in ("processed", "failed")
            if isinstance(gmail.get(field), int)
            and not isinstance(gmail.get(field), bool)
            and gmail[field] >= 0
        )
    safe_categories: list[str] = []
    for flow_name, category_keys in SAFE_FAILURE_CATEGORIES.items():
        flow_counts = counts if flow_name == "rss" else counts.get(flow_name)
        categories = (
            flow_counts.get("failure_categories") if isinstance(flow_counts, dict) else None
        )
        if not isinstance(categories, dict):
            continue
        safe_categories.extend(
            f"{flow_name}_{key}={categories[key]}"
            for key in category_keys
            if isinstance(categories.get(key), int)
            and not isinstance(categories.get(key), bool)
            and categories[key] > 0
        )
    parts.extend(safe_categories[:8])
    if len(safe_categories) > 8:
        parts.append(f"more_safe_categories={len(safe_categories) - 8}")
    return "; ".join(parts)[:500] if parts else "No new items; no briefing/editor work."


def format_failure_summary(result: dict[str, object]) -> str:
    """Describe only aggregate counts of items that actually failed processing."""
    counts = result.get("counts")
    if not isinstance(counts, dict):
        return ""
    flows = (("RSS", counts), ("YouTube", counts.get("youtube")), ("Gmail", counts.get("gmail")))
    details: list[str] = []
    for label, flow_counts in flows:
        if not isinstance(flow_counts, dict):
            continue
        failed = flow_counts.get("failed")
        if not isinstance(failed, int) or isinstance(failed, bool) or failed <= 0:
            continue
        details.append(f"{label}: {failed} öğe")
    return "; ".join(details)[:120]
