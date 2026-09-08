"""Offline contract and privacy regressions for the separate read-only Agent API."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config.settings import Settings
from app.main import create_app

TOKEN = "agent-api-test-token-with-at-least-24-characters"


def _app(**overrides: object):
    settings = Settings(
        _env_file=None,
        agent_api_enabled=True,
        agent_api_token=TOKEN,
        **overrides,
    )
    app = create_app(
        settings=settings,
        readiness_check=lambda: __import__("asyncio").sleep(0, result=True),
    )
    audit: list[tuple[str, str, int]] = []

    async def write_audit(endpoint: str, outcome: str, response_bytes: int) -> None:
        audit.append((endpoint, outcome, response_bytes))

    app.state.agent_api_audit_writer = write_audit
    app.state.test_agent_audit = audit
    return app


def _headers(token: str = TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _briefing() -> dict[str, object]:
    return {
        "id": "briefing-1",
        "created_at": datetime(2026, 9, 8, tzinfo=UTC),
        "items": [
            {
                "section": "Tech & Industry",
                "title": "Safe title",
                "summary": "Short persisted summary.",
                "published_at": datetime(2026, 9, 8, tzinfo=UTC),
                "source_links": ["https://example.test/source"],
                "verified_facts": ["Source-backed fact."],
                "stored_inferences": ["Stored inference."],
                "original_text": False,
            }
        ],
    }


def test_agent_api_is_disabled_by_default_and_token_is_separate_from_admin() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    with TestClient(app) as client:
        assert client.get("/api/v1/briefings/latest").status_code == 404


def test_agent_api_fails_closed_when_enabled_without_a_strong_dedicated_token() -> None:
    with pytest.raises(ValidationError, match="AGENT_API_TOKEN"):
        Settings(_env_file=None, agent_api_enabled=True)


def test_agent_api_rejects_missing_or_invalid_token_without_echoing_it() -> None:
    app = _app()
    with TestClient(app) as client:
        missing = client.get("/api/v1/briefings/latest")
        invalid = client.get("/api/v1/briefings/latest", headers=_headers("wrong-token"))
    assert missing.status_code == invalid.status_code == 401
    assert TOKEN not in missing.text
    assert "wrong-token" not in invalid.text
    assert app.state.test_agent_audit == [
        ("briefings.latest", "unauthorized", 0),
        ("briefings.latest", "unauthorized", 0),
    ]


def test_agent_api_returns_bounded_briefing_with_facts_and_labelled_inferences() -> None:
    app = _app()

    async def latest() -> dict[str, object]:
        return _briefing()

    app.state.agent_api_latest_briefing = latest
    with TestClient(app) as client:
        response = client.get("/api/v1/briefings/latest", headers=_headers())
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["verified_facts"] == ["Source-backed fact."]
    assert item["stored_inferences"] == ["Stored inference."]
    assert item["source_links"] == ["https://example.test/source"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Authorization"
    assert app.state.test_agent_audit[-1][0:2] == ("briefings.latest", "ok")
    assert app.state.test_agent_audit[-1][2] > 0


def test_agent_api_briefing_pagination_is_bounded() -> None:
    app = _app()
    seen: list[tuple[int, datetime | None]] = []

    async def list_briefings(limit: int, before: datetime | None) -> dict[str, object]:
        seen.append((limit, before))
        return {
            "items": [
                {
                    "id": "briefing-1",
                    "created_at": datetime(2026, 9, 8, tzinfo=UTC),
                    "item_count": 1,
                }
            ],
            "next_before": None,
        }

    app.state.agent_api_list_briefings = list_briefings
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/briefings?limit=1&before=2026-09-09T00:00:00Z", headers=_headers()
        )
        invalid = client.get("/api/v1/briefings?limit=21", headers=_headers())
    assert response.status_code == 200
    assert seen == [(1, datetime(2026, 9, 9, tzinfo=UTC))]
    assert invalid.status_code == 422


def test_agent_api_rejects_response_over_its_configured_bound() -> None:
    app = _app(agent_api_max_response_bytes=1024)

    async def latest() -> dict[str, object]:
        value = _briefing()
        value["items"] = [
            {**value["items"][0], "summary": "x" * 600, "verified_facts": ["y" * 400] * 5}
            for _ in range(5)
        ]
        return value

    app.state.agent_api_latest_briefing = latest
    with TestClient(app) as client:
        response = client.get("/api/v1/briefings/latest", headers=_headers())
    assert response.status_code == 413
    assert app.state.test_agent_audit[-1] == ("briefings.latest", "response_too_large", 0)


def test_agent_api_search_keeps_gmail_boundary_and_drops_provider_metadata() -> None:
    app = _app()
    seen_questions: list[str] = []

    async def ask(filters) -> dict[str, object]:
        seen_questions.append(filters.question)
        return {
            "status": "ok",
            "answer_tr": "Kısa cevap.",
            "events": [
                {
                    "event_id": "event-1",
                    "title": "Event title",
                    "occurred_at": datetime(2026, 9, 8, tzinfo=UTC),
                    "source_links": ["https://example.test/event"],
                    "verified_facts": ["Verified fact"],
                    "stored_inferences": ["Stored inference"],
                    "category_paths": ["technology.ai"],
                    "entities": ["Example"],
                    "topics": ["test"],
                }
            ],
            "emails": [
                {
                    "classification": "security",
                    "action_summary": "Güvenlik ayarını inceleyin.",
                    "deadline": datetime(2026, 9, 9, tzinfo=UTC),
                    "application_company": "Example Corp",
                    "recorded_at": datetime(2026, 9, 8, tzinfo=UTC),
                }
            ],
            "model_inferences": ["Model inference"],
            "llm": {"provider_calls": 1, "raw_provider_secret": "must-not-return"},
        }

    app.state.ask_callback = ask
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/knowledge/search",
            headers=_headers(),
            json={"question": "Güvenlik e-postası ve olay ne oldu?"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert seen_questions == ["Güvenlik e-postası ve olay ne oldu?"]
    assert payload["events"][0]["verified_facts"] == ["Verified fact"]
    assert payload["events"][0]["stored_inferences"] == ["Stored inference"]
    assert payload["model_inferences"] == ["Model inference"]
    assert payload["email_actions"][0]["classification"] == "security"
    rendered = response.text.casefold()
    assert "raw_provider_secret" not in rendered
    assert "sender" not in rendered and "subject" not in rendered and "token" not in rendered


def test_agent_api_search_no_result_preserves_existing_zero_provider_behavior() -> None:
    app = _app()
    calls = 0

    async def ask(_filters) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "status": "insufficient_sources",
            "answer_tr": "Yeterli kaynak bulunamadı.",
            "events": [],
            "emails": [],
            "model_inferences": [],
            "llm": {"provider_calls": 0, "cache_hits": 0, "by_role": {}},
        }

    app.state.ask_callback = ask
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/knowledge/search", headers=_headers(), json={"question": "Bilinmeyen konu"}
        )
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_sources"
    assert calls == 1


def test_agent_api_enforces_request_size_and_rate_limit() -> None:
    app = _app(agent_api_rate_limit_per_minute=1, agent_api_max_request_bytes=256)

    async def ask(_filters) -> dict[str, object]:
        return {
            "status": "insufficient_sources",
            "answer_tr": "Yeterli kaynak bulunamadı.",
            "events": [],
            "emails": [],
            "model_inferences": [],
            "llm": {},
        }

    app.state.ask_callback = ask
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/knowledge/search", headers=_headers(), json={"question": "kısa"}
        )
        second = client.post(
            "/api/v1/knowledge/search", headers=_headers(), json={"question": "kısa"}
        )
    assert first.status_code == 200
    assert second.status_code == 429

    large_app = _app(agent_api_max_request_bytes=256)
    large_app.state.ask_callback = ask
    with TestClient(large_app) as client:
        oversized = client.post(
            "/api/v1/knowledge/search", headers=_headers(), json={"question": "x" * 400}
        )
    assert oversized.status_code == 413
