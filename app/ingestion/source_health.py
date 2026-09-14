"""Safe, deterministic pre-LLM source health and cooldown policy."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FetchFailure(StrEnum):
    TIMEOUT = "timeout"
    NETWORK = "network_error"
    FORBIDDEN = "http_403"
    NOT_FOUND = "http_404"
    RATE_LIMITED = "http_429"
    SERVER_ERROR = "http_5xx"
    MALFORMED = "malformed_content"
    EMPTY = "empty_content"
    UNSUPPORTED = "unsupported_content"
    TRANSCRIPT_UNAVAILABLE = "transcript_unavailable"
    TRANSCRIPT_FETCH = "transcript_fetch_failure"
    TEMPORARY = "temporarily_unavailable"
    INVALID = "permanently_invalid"


@dataclass(frozen=True)
class HealthDecision:
    category: FetchFailure
    retry_after: timedelta | None
    terminal: bool = False


def classify_fetch_failure(error: BaseException) -> HealthDecision:
    """Classify only safe transport/content categories; never retain response bodies."""
    if isinstance(error, httpx.TimeoutException):
        return HealthDecision(FetchFailure.TIMEOUT, timedelta(minutes=2))
    if isinstance(error, httpx.NetworkError):
        return HealthDecision(FetchFailure.NETWORK, timedelta(minutes=2))
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 403:
            return HealthDecision(FetchFailure.FORBIDDEN, timedelta(hours=6))
        if status == 404:
            return HealthDecision(FetchFailure.NOT_FOUND, None, terminal=True)
        if status == 429:
            retry_after = _retry_after(error.response.headers.get("retry-after"))
            return HealthDecision(FetchFailure.RATE_LIMITED, retry_after or timedelta(minutes=15))
        if status >= 500:
            return HealthDecision(FetchFailure.SERVER_ERROR, timedelta(minutes=5))
    message = str(error).casefold()
    if "parse" in message or "xml" in message or "html extraction" in message:
        return HealthDecision(FetchFailure.MALFORMED, timedelta(minutes=15))
    if "sufficient" in message or "empty" in message:
        return HealthDecision(FetchFailure.EMPTY, timedelta(minutes=15))
    if "unsupported" in message or "content type" in message:
        return HealthDecision(FetchFailure.UNSUPPORTED, None, terminal=True)
    if "subtitle" in message or "caption" in message:
        return HealthDecision(FetchFailure.TRANSCRIPT_FETCH, timedelta(minutes=30))
    if "safe absolute" in message or "non-public" in message:
        return HealthDecision(FetchFailure.INVALID, None, terminal=True)
    return HealthDecision(FetchFailure.TEMPORARY, timedelta(minutes=5))


def next_retry_at(
    decision: HealthDecision, failures: int, now: datetime | None = None
) -> datetime | None:
    """Bound exponential cooldown; terminal source/config errors require an operator change."""
    if decision.terminal or decision.retry_after is None:
        return None
    multiplier = min(2 ** max(failures - 1, 0), 12)
    delay = min(decision.retry_after * multiplier, timedelta(hours=24))
    return (now or datetime.now(UTC)).astimezone(UTC) + delay


def _retry_after(value: str | None) -> timedelta | None:
    try:
        seconds = int(value or "")
    except ValueError:
        return None
    return timedelta(seconds=max(1, min(seconds, 86_400)))


def database_source_health(
    sessions: async_sessionmaker[AsyncSession],
) -> tuple[
    "SourceReady", "SourceSuccess", "SourceFailure", "SourceValidators", "SourceValidatorsSave"
]:
    async def ready(kind: str, name: str) -> bool:
        async with sessions() as session:
            retry_at = await session.scalar(
                text(
                    "SELECT next_retry_at FROM source_health WHERE source_kind = :kind "
                    "AND source_name = :name"
                ),
                {"kind": kind, "name": name},
            )
        return retry_at is None or retry_at <= datetime.now(UTC)

    async def success(kind: str, name: str, strategy: str) -> None:
        async with sessions.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO source_health (source_kind, source_name, status, last_attempt_at, "
                    "last_success_at, consecutive_failures, last_error_category, next_retry_at, "
                    "last_successful_strategy) VALUES (:kind, :name, 'healthy', now(), now(), 0, "
                    "NULL, NULL, :strategy) ON CONFLICT (source_kind, source_name) DO UPDATE SET "
                    "status = 'healthy', last_attempt_at = now(), last_success_at = now(), "
                    "consecutive_failures = 0, last_error_category = NULL, next_retry_at = NULL, "
                    "last_successful_strategy = EXCLUDED.last_successful_strategy"
                ),
                {"kind": kind, "name": name, "strategy": strategy[:64]},
            )

    async def failure(kind: str, name: str, error: BaseException) -> None:
        async with sessions.begin() as session:
            failures = await session.scalar(
                text(
                    "SELECT consecutive_failures FROM source_health WHERE source_kind = :kind "
                    "AND source_name = :name FOR UPDATE"
                ),
                {"kind": kind, "name": name},
            )
            next_count = int(failures or 0) + 1
            decision = classify_fetch_failure(error)
            retry_at = next_retry_at(decision, next_count)
            status = "invalid" if decision.terminal else "cooldown"
            await session.execute(
                text(
                    "INSERT INTO source_health (source_kind, source_name, status, last_attempt_at, "
                    "consecutive_failures, last_error_category, next_retry_at) VALUES "
                    "(:kind, :name, :status, now(), :failures, :category, :retry_at) "
                    "ON CONFLICT (source_kind, source_name) DO UPDATE SET "
                    "status = EXCLUDED.status, last_attempt_at = now(), "
                    "consecutive_failures = EXCLUDED.consecutive_failures, "
                    "last_error_category = EXCLUDED.last_error_category, "
                    "next_retry_at = EXCLUDED.next_retry_at"
                ),
                {
                    "kind": kind,
                    "name": name,
                    "status": status,
                    "failures": next_count,
                    "category": decision.category.value,
                    "retry_at": retry_at,
                },
            )

    async def validators(kind: str, name: str) -> tuple[str | None, str | None]:
        async with sessions() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT http_etag, http_last_modified FROM source_health "
                        "WHERE source_kind = :kind AND source_name = :name"
                    ),
                    {"kind": kind, "name": name},
                )
            ).mappings().one_or_none()
        return (
            str(row["http_etag"]) if row and row["http_etag"] else None,
            str(row["http_last_modified"]) if row and row["http_last_modified"] else None,
        )

    async def save_validators(
        kind: str, name: str, etag: str | None, last_modified: str | None
    ) -> None:
        if etag is None and last_modified is None:
            return
        async with sessions.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO source_health (source_kind, source_name, status, "
                    "consecutive_failures, http_etag, http_last_modified) "
                    "VALUES (:kind, :name, 'healthy', 0, :etag, :last_modified) "
                    "ON CONFLICT (source_kind, source_name) DO UPDATE SET "
                    "http_etag = COALESCE(EXCLUDED.http_etag, source_health.http_etag), "
                    "http_last_modified = COALESCE(EXCLUDED.http_last_modified, "
                    "source_health.http_last_modified)"
                ),
                {"kind": kind, "name": name, "etag": etag, "last_modified": last_modified},
            )

    return ready, success, failure, validators, save_validators


SourceReady = Callable[[str, str], Awaitable[bool]]
SourceSuccess = Callable[[str, str, str], Awaitable[None]]
SourceFailure = Callable[[str, str, BaseException], Awaitable[None]]
SourceValidators = Callable[[str, str], Awaitable[tuple[str | None, str | None]]]
SourceValidatorsSave = Callable[[str, str, str | None, str | None], Awaitable[None]]
