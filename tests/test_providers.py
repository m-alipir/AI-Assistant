import pytest

from app.providers.contracts import ExternalItem, LlmRequest, LlmResponse
from app.providers.fakes import FakeCollectorProvider, FakeLlmProvider


@pytest.mark.asyncio
async def test_fake_collector_is_deterministic_and_offline() -> None:
    item = ExternalItem(title="A fresh item", external_id="item-1")
    collector = FakeCollectorProvider([item])

    collected = [candidate async for candidate in collector.collect()]

    assert collected == [item]


@pytest.mark.asyncio
async def test_fake_llm_records_role_routed_request() -> None:
    provider = FakeLlmProvider(LlmResponse(content="{}", model_id="test-model"))
    request = LlmRequest(role="gatekeeper", content="metadata only")

    response = await provider.complete(request)

    assert response.model_id == "test-model"
    assert provider.requests == [request]
