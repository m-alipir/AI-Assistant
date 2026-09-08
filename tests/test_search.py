import json
from datetime import UTC, datetime

import httpx
import pytest

from app.knowledge.search import (
    KnowledgeSearchError,
    KnowledgeSearchService,
    SafeEmailResult,
    SearchEvent,
    SearchFilters,
    answer_question,
)
from app.llm.core import (
    BudgetPolicy,
    BudgetTracker,
    InMemoryResultCache,
    ModelSettings,
    OpenRouterClient,
    RoleConfig,
    Router,
)


def event(
    event_id: str, title: str, occurred_at: datetime, *, entities: list[str], topic: str
) -> SearchEvent:
    return SearchEvent(
        event_id=event_id,
        title=title,
        occurred_at=occurred_at,
        source_links=[f"https://example.test/{event_id}"],
        verified_facts=[f"{title} source-backed fact."],
        entities=entities,
        category_paths=["technology.ai"],
        topics=[topic],
    )


@pytest.mark.asyncio
async def test_search_applies_turkish_week_filter_and_hybrid_ranking_before_model() -> None:
    records = [
        event(
            "nvidia",
            "NVIDIA AI update",
            datetime(2026, 9, 7, tzinfo=UTC),
            entities=["NVIDIA"],
            topic="ai",
        ),
        event(
            "amd", "AMD update", datetime(2026, 9, 1, tzinfo=UTC), entities=["AMD"], topic="chips"
        ),
    ]

    async def fetch(_: SearchFilters):
        return records, []

    service = KnowledgeSearchService(fetch, clock=lambda: datetime(2026, 9, 7, 12, tzinfo=UTC))
    results, emails = await service.search(
        SearchFilters(question="Bu hafta NVIDIA hakkında ne oldu?")
    )

    assert [result.event_id for result in results] == ["nvidia"]
    assert results[0].source_links == ["https://example.test/nvidia"]
    assert emails == []


@pytest.mark.asyncio
async def test_empty_search_never_calls_a_model_or_invents_an_answer() -> None:
    async def fetch(_: SearchFilters):
        return [], []

    response = await answer_question(
        SearchFilters(question="Bulunmayan bir konu"), KnowledgeSearchService(fetch), None
    )

    assert response.status == "insufficient_sources"
    assert response.answer_tr == "Yeterli kaynak bulunamadı."
    assert response.llm["provider_calls"] == 0


@pytest.mark.asyncio
async def test_bounded_reasoner_context_returns_inferences_separate_from_verified_facts() -> None:
    recorded_prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_prompts.append(request.content.decode())
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"answer_tr":"NVIDIA için bir gelişme bulundu.",'
                            '"model_inferences":["Bu gelişme önceki eğilimle ilişkili olabilir."]}'
                        }
                    }
                ]
            },
        )

    async def fetch(_: SearchFilters):
        return [
            event(
                "nvidia",
                "NVIDIA AI update",
                datetime(2026, 9, 7, tzinfo=UTC),
                entities=["NVIDIA"],
                topic="ai",
            )
        ], [
            SafeEmailResult(
                classification="security", action_summary="Review account security alert."
            )
        ]

    settings = ModelSettings(
        roles={"reasoner": RoleConfig(model="fake/reasoner", max_output_tokens=100)},
        budgets=BudgetPolicy(daily_soft_usd=1, daily_hard_usd=1),
    )
    router = Router(
        OpenRouterClient("test-key", "https://example.test", httpx.MockTransport(handler)),
        settings,
        InMemoryResultCache(),
        BudgetTracker(),
    )
    response = await answer_question(
        SearchFilters(question="NVIDIA ile ilgili gelişme var mı?"),
        KnowledgeSearchService(fetch),
        router,
    )

    assert response.events[0].verified_facts == ["NVIDIA AI update source-backed fact."]
    assert response.model_inferences == ["Bu gelişme önceki eğilimle ilişkili olabilir."]
    assert response.llm["provider_calls"] == 1
    assert "email body" not in recorded_prompts[0].casefold()


@pytest.mark.asyncio
async def test_reasoner_context_respects_role_limit_with_large_retained_fields() -> None:
    recorded_prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_prompts.append(json.loads(request.content)["messages"][0]["content"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"answer_tr":"Tamam.","model_inferences":[]}'}}
                ]
            },
        )

    async def fetch(_: SearchFilters):
        return [
            SearchEvent(
                event_id="large",
                title="T" * 4_000,
                occurred_at=datetime(2026, 9, 7, tzinfo=UTC),
                source_links=["https://example.test/" + "u" * 4_000],
                verified_facts=["F" * 4_000 for _ in range(10)],
                category_paths=["technology.ai"],
                entities=["NVIDIA"],
                topics=["ai"],
            )
        ], [
            SafeEmailResult(
                classification="security",
                action_summary="A" * 4_000,
                application_company="C" * 1_000,
            )
        ]

    router = Router(
        OpenRouterClient("test-key", "https://example.test", httpx.MockTransport(handler)),
        ModelSettings(
            roles={"reasoner": RoleConfig(model="fake/reasoner", max_input_chars=700)},
            budgets=BudgetPolicy(daily_soft_usd=1, daily_hard_usd=1),
        ),
        InMemoryResultCache(),
        BudgetTracker(),
    )
    await answer_question(
        SearchFilters(question="NVIDIA hakkında ne var?"), KnowledgeSearchService(fetch), router
    )

    assert len(recorded_prompts) == 1
    assert len(recorded_prompts[0]) <= 700


@pytest.mark.asyncio
async def test_legacy_event_without_search_metadata_remains_searchable() -> None:
    legacy = SearchEvent(
        event_id="legacy-nvidia",
        title="NVIDIA legacy RSS event",
        occurred_at=datetime(2026, 9, 7, tzinfo=UTC),
        verified_facts=["NVIDIA published a source-backed update."],
    )

    async def fetch(_: SearchFilters):
        return [legacy], []

    response = await answer_question(
        SearchFilters(question="NVIDIA hakkında ne oldu?"), KnowledgeSearchService(fetch), None
    )

    assert response.status == "ok"
    assert [item.event_id for item in response.events] == ["legacy-nvidia"]


@pytest.mark.asyncio
async def test_gmail_action_item_is_returned_without_event_metadata() -> None:
    async def fetch(_: SearchFilters):
        return [], [
            SafeEmailResult(
                classification="security",
                action_summary="Hesap güvenlik uyarısını inceleyin.",
            )
        ]

    response = await answer_question(
        SearchFilters(question="Son önemli e-postalarım neler?"),
        KnowledgeSearchService(fetch),
        None,
    )

    assert response.status == "ok"
    assert response.emails[0].classification == "security"


@pytest.mark.asyncio
async def test_reasoner_validation_failure_keeps_source_results() -> None:
    def malformed_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not-json"}}]})

    async def fetch(_: SearchFilters):
        return [
            event(
                "nvidia",
                "NVIDIA RSS update",
                datetime(2026, 9, 7, tzinfo=UTC),
                entities=["NVIDIA"],
                topic="ai",
            )
        ], []

    router = Router(
        OpenRouterClient(
            "test-key", "https://example.test", httpx.MockTransport(malformed_handler)
        ),
        ModelSettings(
            roles={"reasoner": RoleConfig(model="fake/reasoner")},
            budgets=BudgetPolicy(daily_soft_usd=1, daily_hard_usd=1),
        ),
        InMemoryResultCache(),
        BudgetTracker(),
    )
    response = await answer_question(
        SearchFilters(question="NVIDIA hakkında ne oldu?"), KnowledgeSearchService(fetch), router
    )

    assert response.events[0].title == "NVIDIA RSS update"
    assert response.answer_tr == "İlgili kaynaklar bulundu; model özeti şu anda kullanılamıyor."


@pytest.mark.asyncio
async def test_search_runtime_error_is_available_to_the_admin_as_a_safe_category() -> None:
    async def fetch(_: SearchFilters):
        raise KnowledgeSearchError("search_migration_or_schema_error")

    with pytest.raises(KnowledgeSearchError, match="search_migration_or_schema_error"):
        await KnowledgeSearchService(fetch).search(SearchFilters(question="NVIDIA"))
