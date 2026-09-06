import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.config.models import load_model_settings
from app.llm.core import (
    BudgetExceeded,
    BudgetPolicy,
    BudgetTracker,
    ExtractionFlow,
    GatekeeperResult,
    InMemoryResultCache,
    LlmError,
    ModelSettings,
    OpenRouterClient,
    RoleConfig,
    Router,
    Usage,
    advisory_candidates,
)
from app.llm.repository import InMemoryLlmRepository, SqlAlchemyLlmRepository


def settings() -> ModelSettings:
    return ModelSettings(
        roles={
            "gatekeeper": RoleConfig(
                model="fake/primary", fallbacks=["fake/fallback"], max_output_tokens=10
            ),
            "extractor": RoleConfig(model="fake/extractor", max_output_tokens=10),
        },
        budgets=BudgetPolicy(daily_soft_usd=1, daily_hard_usd=1, reserve_email_action_usd=0.1),
    )


def priced_settings(*, soft: float = 5, hard: float = 10) -> ModelSettings:
    role = RoleConfig(
        model="fake/primary",
        fallbacks=["fake/fallback"],
        max_output_tokens=1,
        input_usd_per_million=0,
        output_usd_per_million=200_000,
    )
    return ModelSettings(
        roles={"gatekeeper": role, "extractor": role},
        budgets=BudgetPolicy(daily_soft_usd=soft, daily_hard_usd=hard),
    )


@pytest.mark.asyncio
async def test_mocked_gatekeeper_uses_fallback_validates_schema_and_hits_cache() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content)["model"])
        if len(calls) == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})
        payload = {
            "relevant": True,
            "global_importance": 3,
            "personal_relevance": 4,
            "category_paths": [],
            "entities": [],
            "topics": [],
            "importance": 4,
            "needs_full_extraction": False,
        }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(payload)}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3},
            },
        )

    client = OpenRouterClient("test-key", "https://example.test", httpx.MockTransport(handler))
    router = Router(client, settings(), InMemoryResultCache(), BudgetTracker())
    flow = ExtractionFlow(router)
    digest = hashlib.sha256(b"item").hexdigest()

    first = await flow.gate("title", "snippet", digest)
    second = await flow.gate("title", "snippet", digest)

    assert first.relevant and second.relevant
    assert calls == ["fake/primary", "fake/fallback"]
    assert router.calls[-1].cache_hit is True


def test_budget_reserves_capacity_for_email_actions() -> None:
    policy = BudgetPolicy(daily_soft_usd=0.5, daily_hard_usd=1, reserve_email_action_usd=0.2)
    tracker = BudgetTracker(spent_usd=0.75)
    config = RoleConfig(model="fake/model")
    with pytest.raises(BudgetExceeded):
        tracker.allow("gatekeeper", 0.1, policy, config)
    tracker.allow("gatekeeper", 0.1, policy, config, email_action=True)


def test_budget_enforces_role_and_total_limits_and_rolls_over_at_utc_midnight() -> None:
    policy = BudgetPolicy(daily_soft_usd=0.5, daily_hard_usd=1, reserve_email_action_usd=0.1)
    role = RoleConfig(model="fake/model", daily_soft_usd=0.2, daily_hard_usd=0.3)
    tracker = BudgetTracker(day=datetime(2026, 9, 6, 23, 0, tzinfo=UTC).date())

    assert not tracker.record(
        "gatekeeper", 0.19, policy, role, datetime(2026, 9, 6, 23, 0, tzinfo=UTC)
    )
    assert tracker.record("gatekeeper", 0.02, policy, role, datetime(2026, 9, 6, 23, 1, tzinfo=UTC))
    with pytest.raises(BudgetExceeded, match="role"):
        tracker.allow("gatekeeper", 0.1, policy, role, now=datetime(2026, 9, 6, 23, 2, tzinfo=UTC))

    tracker.allow("gatekeeper", 0.3, policy, role, now=datetime(2026, 9, 7, 0, 1, tzinfo=UTC))
    assert tracker.spent_usd == 0
    assert tracker.role_spend == {}


@pytest.mark.asyncio
async def test_persistent_repository_cache_survives_router_restart() -> None:
    calls: list[str] = []
    payload = {
        "relevant": True,
        "global_importance": 1,
        "personal_relevance": 1,
        "category_paths": [],
        "entities": [],
        "topics": [],
        "importance": 1,
        "needs_full_extraction": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content)["model"])
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(payload)}}]}
        )

    repository = InMemoryLlmRepository()
    digest = hashlib.sha256(b"persistent-item").hexdigest()
    first_router = Router(
        OpenRouterClient("test-key", "https://example.test", httpx.MockTransport(handler)),
        settings(),
        InMemoryResultCache(),
        BudgetTracker(),
        repository,
    )
    assert (await ExtractionFlow(first_router).gate("title", "snippet", digest)).relevant

    restarted_router = Router(
        OpenRouterClient("test-key", "https://example.test", httpx.MockTransport(handler)),
        settings(),
        InMemoryResultCache(),
        BudgetTracker(),
        repository,
    )
    assert (await ExtractionFlow(restarted_router).gate("title", "snippet", digest)).relevant
    assert calls == ["fake/primary"]
    assert len(repository.calls) == 2
    assert repository.calls[-1][1].cache_hit is True


@pytest.mark.asyncio
async def test_invalid_structured_outputs_fail_safely_after_all_fallbacks() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content)["model"])
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    router = Router(
        OpenRouterClient("test-key", "https://example.test", httpx.MockTransport(handler)),
        settings(),
        InMemoryResultCache(),
        BudgetTracker(),
    )
    with pytest.raises(LlmError, match="all configured"):
        await ExtractionFlow(router).gate("title", "snippet", "digest")
    assert calls == ["fake/primary", "fake/fallback"]


@pytest.mark.asyncio
async def test_mocked_extractor_returns_validated_claims() -> None:
    payload = {
        "compact_summary": "A source-backed summary.",
        "what_changed": "A change.",
        "claims": [{"statement": "A source fact.", "source_locator": "paragraph 1"}],
        "entities": ["Example Corp"],
        "topics": ["Example"],
        "uncertainty_markers": [],
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(payload)}}]}
        )

    router = Router(
        OpenRouterClient("test-key", "https://example.test", httpx.MockTransport(handler)),
        settings(),
        InMemoryResultCache(),
        BudgetTracker(),
    )
    result = await ExtractionFlow(router).extract("source content", "extract-digest")
    assert result.claims[0].statement == "A source fact."


@pytest.mark.asyncio
async def test_invalid_outputs_are_charged_and_persisted_without_raw_response() -> None:
    repository = InMemoryLlmRepository()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2},
            },
        )

    router = Router(
        OpenRouterClient("test-key", "https://example.test", httpx.MockTransport(handler)),
        priced_settings(),
        InMemoryResultCache(),
        BudgetTracker(),
        repository,
    )
    with pytest.raises(LlmError):
        await ExtractionFlow(router).gate("title", "snippet", "invalid-digest")

    assert router._budget.spent_usd == pytest.approx(0.8)
    assert [status for _, _, status in repository.calls] == ["invalid_output", "invalid_output"]
    assert all(usage.output_tokens == 2 for _, usage, _ in repository.calls)


@pytest.mark.asyncio
async def test_restart_hydrates_daily_budget_before_provider_preflight() -> None:
    now = datetime(2026, 9, 6, 12, tzinfo=UTC)
    repository = InMemoryLlmRepository()
    await repository.record_call(
        "gatekeeper",
        Usage(model_id="fake/previous", estimated_cost_usd=0.8),
        occurred_at=now,
    )
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(500)

    router = Router(
        OpenRouterClient("test-key", "https://example.test", httpx.MockTransport(handler)),
        priced_settings(hard=0.9),
        InMemoryResultCache(),
        BudgetTracker(),
        repository,
        clock=lambda: now,
    )
    with pytest.raises(BudgetExceeded, match="hard budget"):
        await ExtractionFlow(router).gate("title", "snippet", "restart-digest")
    assert requests == 0
    assert router._budget.spent_usd == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_soft_limit_skips_optional_work_but_not_mandatory_work() -> None:
    now = datetime(2026, 9, 6, 12, tzinfo=UTC)
    requests = 0
    payload = {
        "relevant": True,
        "global_importance": 1,
        "personal_relevance": 1,
        "category_paths": [],
        "entities": [],
        "topics": [],
        "importance": 1,
        "needs_full_extraction": False,
    }

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(payload)}}]}
        )

    tracker = BudgetTracker(spent_usd=0.5, day=now.date())
    router = Router(
        OpenRouterClient("test-key", "https://example.test", httpx.MockTransport(handler)),
        priced_settings(soft=0.5, hard=2),
        InMemoryResultCache(),
        tracker,
        clock=lambda: now,
    )
    with pytest.raises(BudgetExceeded, match="optional"):
        await router.structured(
            "gatekeeper", "prompt", "optional-digest", GatekeeperResult, "v1", "v1", optional=True
        )
    assert requests == 0
    assert router.soft_limit_reached

    result = await router.structured(
        "gatekeeper", "prompt", "mandatory-digest", GatekeeperResult, "v1", "v1"
    )
    assert result.relevant
    assert requests == 1


@pytest.mark.asyncio
async def test_memory_cache_hit_is_persisted_as_operational_metadata() -> None:
    repository = InMemoryLlmRepository()
    cache = InMemoryResultCache()
    payload = GatekeeperResult(
        relevant=True,
        global_importance=1,
        personal_relevance=1,
        category_paths=[],
        entities=[],
        topics=[],
        importance=1,
        needs_full_extraction=False,
    )
    key = cache.key("memory-digest", "gatekeeper", "v1", "fake/primary", "v1")
    cache.values[key] = payload.model_dump_json()
    router = Router(
        OpenRouterClient("test-key", "https://example.test"),
        settings(),
        cache,
        BudgetTracker(),
        repository,
    )

    assert (await ExtractionFlow(router).gate("title", "snippet", "memory-digest")).relevant
    assert repository.calls[-1][1].cache_hit is True
    assert repository.calls[-1][2] == "cache_hit"


@pytest.mark.asyncio
async def test_sqlalchemy_repository_aggregates_metadata_only_daily_spend() -> None:
    class Result:
        def __iter__(self):
            return iter([("gatekeeper", 0.3), ("extractor", 0.2)])

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def scalar(self, _: object) -> float:
            return 0.5

        async def execute(self, _: object) -> Result:
            return Result()

    class Sessions:
        def __call__(self) -> Session:
            return Session()

    repository = SqlAlchemyLlmRepository(Sessions())  # type: ignore[arg-type]
    spend = await repository.daily_spend(datetime(2026, 9, 6, tzinfo=UTC))
    assert spend.total_usd == 0.5
    assert spend.role_usd == {"gatekeeper": 0.3, "extractor": 0.2}


def test_catalog_advice_is_non_mutating_and_filters_capability() -> None:
    catalog = [{"id": "a", "structured_outputs": True}, {"id": "b", "structured_outputs": False}]
    assert advisory_candidates(catalog, require_structured=True) == ["a"]


def test_role_mappings_load_from_example_configuration() -> None:
    loaded = load_model_settings(Path("config/models.example.yaml"))
    assert loaded.roles["gatekeeper"].model.startswith("REPLACE_")
    assert loaded.budgets.reserve_email_action_usd == 0.1
