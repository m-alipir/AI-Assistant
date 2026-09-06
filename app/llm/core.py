"""Direct OpenRouter client, strict structured outputs, cache, and budget-aware routing."""

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from datetime import time as datetime_time
from typing import TYPE_CHECKING, Any, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:
    from app.llm.repository import DailySpend, LlmRepository


logger = logging.getLogger(__name__)


class LlmError(RuntimeError):
    """Safe LLM boundary failure that never contains request content or credentials."""


class BudgetExceeded(LlmError):
    """Raised before an optional request would exceed the configured hard limit."""


class RoleConfig(BaseModel):
    """Configuration-only model routing and price metadata for one LLM role."""

    model_config = ConfigDict(extra="forbid")
    model: str
    fallbacks: list[str] = Field(default_factory=list)
    require_structured_outputs: bool = True
    temperature: float = Field(default=0.0, ge=0, le=2)
    max_output_tokens: int = Field(default=1000, ge=1, le=10000)
    input_usd_per_million: float = Field(default=0.0, ge=0)
    output_usd_per_million: float = Field(default=0.0, ge=0)
    dimensions: int | None = Field(default=None, ge=1)
    daily_soft_usd: float | None = Field(default=None, ge=0)
    daily_hard_usd: float | None = Field(default=None, ge=0)
    estimated_input_tokens: int = Field(default=1000, ge=0)

    @property
    def candidates(self) -> list[str]:
        """Return configured primary then ordered configured fallbacks."""
        return [self.model, *self.fallbacks]


class BudgetPolicy(BaseModel):
    """Daily spending guardrails; email action work may use its reserved allowance."""

    daily_soft_usd: float = Field(ge=0)
    daily_hard_usd: float = Field(ge=0)
    reserve_email_action_usd: float = Field(default=0, ge=0)


class OpenRouterConfig(BaseModel):
    """Typed non-secret OpenRouter endpoint configuration."""

    base_url: str = "https://openrouter.ai/api/v1"


class ModelSettings(BaseModel):
    """Validated model configuration loaded at the application edge."""

    roles: dict[str, RoleConfig]
    budgets: BudgetPolicy
    openrouter: OpenRouterConfig = Field(default_factory=OpenRouterConfig)


class Usage(BaseModel):
    """Non-sensitive usage/cost metadata retained for operational accounting."""

    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0
    latency_ms: int = 0
    cache_hit: bool = False


class OpenRouterResponse(BaseModel):
    """Normalized response from the direct OpenRouter client."""

    content: str
    usage: Usage


class OpenRouterClient:
    """Small direct HTTP client with bounded retries and no payload logging."""

    def __init__(
        self, api_key: str, base_url: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    async def complete(
        self, model: str, prompt: str, config: RoleConfig, schema: dict[str, Any]
    ) -> OpenRouterResponse:
        """Request strict JSON-schema output, retrying transient transport/server failures once."""
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config.temperature,
            "max_tokens": config.max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "result", "strict": True, "schema": schema},
            },
        }
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        started = time.perf_counter()
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=15, transport=self._transport) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions", json=body, headers=headers
                    )
                    if response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            "provider server error", request=response.request, response=response
                        )
                    response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                raw_usage = data.get("usage", {})
                usage = Usage(
                    model_id=model,
                    input_tokens=raw_usage.get("prompt_tokens", 0),
                    output_tokens=raw_usage.get("completion_tokens", 0),
                    latency_ms=round((time.perf_counter() - started) * 1000),
                )
                return OpenRouterResponse(content=content, usage=usage)
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
                if attempt:
                    raise LlmError("OpenRouter request failed") from error
                await asyncio.sleep(0.1)
        raise AssertionError("unreachable")

    async def list_models(self) -> list[Mapping[str, Any]]:
        """Retrieve the advisory-only catalog; this never changes configured role mappings."""
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=15, transport=self._transport) as client:
            response = await client.get(f"{self._base_url}/models", headers=headers)
            response.raise_for_status()
        data = response.json().get("data", [])
        return [entry for entry in data if isinstance(entry, Mapping)]


T = TypeVar("T", bound=BaseModel)


@dataclass
class InMemoryResultCache:
    """Validated-result cache keyed by all fields required by the cost policy."""

    values: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def key(
        content_hash: str, task_type: str, prompt_version: str, model_id: str, schema_version: str
    ) -> str:
        """Create an opaque stable cache key from the mandatory components."""
        return hashlib.sha256(
            "|".join([content_hash, task_type, prompt_version, model_id, schema_version]).encode()
        ).hexdigest()


@dataclass
class BudgetTracker:
    """UTC-day budget state, hydrated from metadata-only persistence before preflight."""

    spent_usd: float = 0
    role_spend: dict[str, float] = field(default_factory=dict)
    day: date = field(default_factory=lambda: datetime.now(UTC).date())

    def _rollover(self, now: datetime) -> None:
        if now.astimezone(UTC).date() != self.day:
            self.day, self.spent_usd, self.role_spend = now.astimezone(UTC).date(), 0, {}

    def hydrate(self, total_usd: float, role_usd: Mapping[str, float], now: datetime) -> None:
        """Replace this process's daily view with durable aggregate spending."""
        self._rollover(now)
        self.spent_usd = total_usd
        self.role_spend = dict(role_usd)

    def soft_exceeded(
        self, role: str, policy: BudgetPolicy, config: RoleConfig, now: datetime
    ) -> bool:
        """Report whether prior daily spending reached a total or role soft threshold."""
        self._rollover(now)
        return self.spent_usd >= policy.daily_soft_usd or (
            config.daily_soft_usd is not None
            and self.role_spend.get(role, 0) >= config.daily_soft_usd
        )

    def allow(
        self,
        role: str,
        estimated_cost: float,
        policy: BudgetPolicy,
        config: RoleConfig,
        email_action: bool = False,
        now: datetime | None = None,
    ) -> None:
        """Reject hard-limit requests while preserving the configured email-action reserve."""
        self._rollover(now or datetime.now(UTC))
        limit = (
            policy.daily_hard_usd
            if email_action
            else policy.daily_hard_usd - policy.reserve_email_action_usd
        )
        if self.spent_usd + estimated_cost > limit:
            raise BudgetExceeded("daily LLM hard budget would be exceeded")
        if (
            config.daily_hard_usd is not None
            and self.role_spend.get(role, 0) + estimated_cost > config.daily_hard_usd
        ):
            raise BudgetExceeded("role LLM hard budget would be exceeded")

    def record(
        self,
        role: str,
        cost: float,
        policy: BudgetPolicy,
        config: RoleConfig,
        now: datetime | None = None,
    ) -> bool:
        """Record completed cost and return whether the soft limit is now exceeded."""
        self._rollover(now or datetime.now(UTC))
        self.spent_usd += cost
        self.role_spend[role] = self.role_spend.get(role, 0) + cost
        return self.spent_usd >= policy.daily_soft_usd or (
            config.daily_soft_usd is not None and self.role_spend[role] >= config.daily_soft_usd
        )


class Router:
    """Configuration-driven fallback router with cache, strict validation, and accounting."""

    def __init__(
        self,
        client: OpenRouterClient,
        settings: ModelSettings,
        cache: InMemoryResultCache,
        budget: BudgetTracker,
        repository: "LlmRepository | None" = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client, self._settings, self._cache, self._budget = client, settings, cache, budget
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[Usage] = []
        self.soft_limit_reached = False
        self.soft_limit_roles: set[str] = set()

    def _now(self) -> datetime:
        return self._clock().astimezone(UTC)

    async def _sync_budget(self, now: datetime) -> None:
        if self._repository is None:
            return
        since = datetime.combine(now.date(), datetime_time.min, tzinfo=UTC)
        spend: DailySpend = await self._repository.daily_spend(since)
        self._budget.hydrate(spend.total_usd, spend.role_usd, now)

    async def _record_attempt(
        self, role: str, usage: Usage, status: str, config: RoleConfig, now: datetime
    ) -> None:
        """Account for every provider/cache attempt without retaining request/response payloads."""
        soft_limit = self._budget.record(
            role, usage.estimated_cost_usd, self._settings.budgets, config, now
        )
        self.calls.append(usage)
        if self._repository:
            await self._repository.record_call(role, usage, status, now)
        if soft_limit:
            self.soft_limit_reached = True
            self.soft_limit_roles.add(role)
            logger.warning("LLM soft budget reached for role %s", role)

    async def _record_cache_hit(self, role: str, model_id: str, now: datetime) -> Usage:
        usage = Usage(model_id=model_id, cache_hit=True)
        self.calls.append(usage)
        if self._repository:
            await self._repository.record_call(role, usage, "cache_hit", now)
        return usage

    async def structured(
        self,
        role: str,
        prompt: str,
        content_hash: str,
        result_type: type[T],
        prompt_version: str,
        schema_version: str,
        email_action: bool = False,
        optional: bool = False,
    ) -> T:
        """Return cached or provider-validated structured data with safe fallback behavior."""
        config = self._settings.roles[role]
        schema = result_type.model_json_schema()
        now = self._now()
        for cached_model in config.candidates:
            cache_key = self._cache.key(
                content_hash, role, prompt_version, cached_model, schema_version
            )
            if cached := self._cache.values.get(cache_key):
                await self._record_cache_hit(role, cached_model, now)
                return result_type.model_validate_json(cached)
            if self._repository and (persisted := await self._repository.get_cache(cache_key)):
                result = result_type.model_validate_json(persisted)
                self._cache.values[cache_key] = persisted
                await self._record_cache_hit(role, cached_model, now)
                return result
        last_error: Exception | None = None
        for model_id in config.candidates:
            key = self._cache.key(content_hash, role, prompt_version, model_id, schema_version)
            if cached := self._cache.values.get(key):
                result = result_type.model_validate_json(cached)
                await self._record_cache_hit(role, model_id, now)
                return result
            now = self._now()
            await self._sync_budget(now)
            if optional and self._budget.soft_exceeded(role, self._settings.budgets, config, now):
                self.soft_limit_reached = True
                self.soft_limit_roles.add(role)
                logger.info("Skipping optional LLM work after soft budget limit for role %s", role)
                raise BudgetExceeded("optional LLM work skipped after soft budget limit")
            estimated = (
                config.max_output_tokens * config.output_usd_per_million
                + config.estimated_input_tokens * config.input_usd_per_million
            ) / 1_000_000
            self._budget.allow(role, estimated, self._settings.budgets, config, email_action)
            response: OpenRouterResponse | None = None
            try:
                response = await self._client.complete(model_id, prompt, config, schema)
                response.usage.estimated_cost_usd = (
                    response.usage.input_tokens * config.input_usd_per_million
                    + response.usage.output_tokens * config.output_usd_per_million
                ) / 1_000_000
                result = result_type.model_validate_json(response.content)
            except ValidationError as error:
                if response:
                    await self._record_attempt(role, response.usage, "invalid_output", config, now)
                last_error = error
                continue
            except LlmError as error:
                await self._record_attempt(
                    role, Usage(model_id=model_id), "provider_failed", config, now
                )
                last_error = error
                continue
            await self._record_attempt(role, response.usage, "success", config, now)
            self._cache.values[key] = result.model_dump_json()
            if self._repository:
                await self._repository.put_cache(key, model_id, self._cache.values[key])
            return result
        raise LlmError("all configured model candidates failed validation") from last_error


class GatekeeperResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relevant: bool
    global_importance: int = Field(ge=0, le=10)
    personal_relevance: int = Field(ge=0, le=10)
    category_paths: list[str]
    entities: list[str]
    topics: list[str]
    importance: int = Field(ge=0, le=10)
    needs_full_extraction: bool


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str
    source_locator: str | None = None


class ExtractorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    compact_summary: str
    what_changed: str
    claims: list[ExtractedClaim]
    entities: list[str]
    topics: list[str]
    uncertainty_markers: list[str]


class ExtractionFlow:
    """Minimal gatekeeper/extractor flow that sends only compact delimited source content."""

    def __init__(self, router: Router) -> None:
        self._router = router

    async def gate(self, title: str, snippet: str, content_hash: str) -> GatekeeperResult:
        prompt = f"Classify only this delimited metadata.\nTITLE: {title}\nSNIPPET: {snippet}"
        return await self._router.structured(
            "gatekeeper", prompt, content_hash, GatekeeperResult, "v1", "v1"
        )

    async def extract(self, content: str, content_hash: str) -> ExtractorResult:
        prompt = (
            "Extract source-backed facts only from this delimited content.\n<source>\n"
            f"{content}\n</source>"
        )
        return await self._router.structured(
            "extractor", prompt, content_hash, ExtractorResult, "v1", "v1"
        )


def advisory_candidates(catalog: list[Mapping[str, Any]], require_structured: bool) -> list[str]:
    """Filter catalog IDs for display only; active role mappings remain configuration-controlled."""
    return [
        str(item["id"])
        for item in catalog
        if "id" in item and (not require_structured or item.get("structured_outputs", False))
    ]
