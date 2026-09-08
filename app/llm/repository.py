"""Async repository boundary for non-sensitive LLM cache and accounting data."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.llm_models import LlmCall, LlmResultCache
from app.llm.core import Usage


@dataclass(frozen=True)
class DailySpend:
    """UTC-day aggregate used to hydrate hard-budget enforcement after a restart."""

    total_usd: float
    role_usd: dict[str, float]
    provider_calls: int = 0
    role_provider_calls: dict[str, int] | None = None


class LlmRepository(Protocol):
    async def get_cache(self, cache_key: str) -> str | None: ...
    async def put_cache(self, cache_key: str, model_id: str, value: str) -> None: ...
    async def record_call(
        self,
        role: str,
        usage: Usage,
        status: str = "success",
        occurred_at: datetime | None = None,
    ) -> None: ...
    async def daily_spend(self, since: datetime) -> DailySpend: ...


class InMemoryLlmRepository:
    def __init__(self) -> None:
        self.cache: dict[str, str] = {}
        self.calls: list[tuple[str, Usage, str]] = []
        self._call_times: list[datetime] = []

    async def get_cache(self, cache_key: str) -> str | None:
        return self.cache.get(cache_key)

    async def put_cache(self, cache_key: str, model_id: str, value: str) -> None:
        self.cache[cache_key] = value

    async def record_call(
        self,
        role: str,
        usage: Usage,
        status: str = "success",
        occurred_at: datetime | None = None,
    ) -> None:
        self.calls.append((role, usage, status))
        self._call_times.append(occurred_at or datetime.now(UTC))

    async def daily_spend(self, since: datetime) -> DailySpend:
        total = 0.0
        roles: dict[str, float] = {}
        provider_calls = 0
        role_provider_calls: dict[str, int] = {}
        for (role, usage, _), occurred_at in zip(self.calls, self._call_times, strict=True):
            if occurred_at >= since:
                total += usage.estimated_cost_usd
                roles[role] = roles.get(role, 0.0) + usage.estimated_cost_usd
                if not usage.cache_hit:
                    provider_calls += 1
                    role_provider_calls[role] = role_provider_calls.get(role, 0) + 1
        return DailySpend(total, roles, provider_calls, role_provider_calls)


class SqlAlchemyLlmRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_cache(self, cache_key: str) -> str | None:
        async with self._sessions() as session:
            row = await session.get(LlmResultCache, cache_key)
            return row.validated_result_json if row else None

    async def put_cache(self, cache_key: str, model_id: str, value: str) -> None:
        async with self._sessions.begin() as session:
            await session.merge(
                LlmResultCache(cache_key=cache_key, model_id=model_id, validated_result_json=value)
            )

    async def record_call(
        self,
        role: str,
        usage: Usage,
        status: str = "success",
        occurred_at: datetime | None = None,
    ) -> None:
        async with self._sessions.begin() as session:
            session.add(
                LlmCall(
                    role=role,
                    model_id=usage.model_id,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    estimated_cost_usd=usage.estimated_cost_usd,
                    provider_cost_usd=usage.provider_cost_usd,
                    cost_status=usage.cost_status,
                    latency_ms=usage.latency_ms,
                    cache_hit=usage.cache_hit,
                    status=status,
                    created_at=occurred_at,
                )
            )

    async def daily_spend(self, since: datetime) -> DailySpend:
        """Return metadata-only total and per-role costs since the UTC-day boundary."""
        async with self._sessions() as session:
            total = await session.scalar(
                select(func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0.0)).where(
                    LlmCall.created_at >= since
                )
            )
            provider_calls = await session.scalar(
                select(func.count()).where(
                    LlmCall.created_at >= since,
                    LlmCall.cache_hit.is_(False),
                )
            )
            rows = await session.execute(
                select(
                    LlmCall.role,
                    func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0.0),
                    func.count().filter(LlmCall.cache_hit.is_(False)),
                )
                .where(LlmCall.created_at >= since)
                .group_by(LlmCall.role)
            )
        role_rows = list(rows)
        return DailySpend(
            float(total),
            {str(role): float(cost) for role, cost, _ in role_rows},
            int(provider_calls or 0),
            {str(role): int(count) for role, _, count in role_rows},
        )
