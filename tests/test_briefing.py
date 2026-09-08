import json
from datetime import UTC, datetime

import httpx
import pytest

from app.briefing.core import BriefingItem, build_sections, edit_compact, render_preview
from app.briefing.presentation import (
    BRIEFING_SECTIONS,
    BriefingViewItem,
    format_istanbul,
    legacy_sections,
    shown_because,
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


def test_m6_world_remains_and_sources_render() -> None:
    world = BriefingItem(
        event_id="world",
        title="Global event",
        source_urls=["https://source"],
        importance=9,
        interest=0,
        global_importance=9,
    )
    action = BriefingItem(
        event_id="mail",
        title="Interview",
        source_urls=["https://mail"],
        importance=8,
        interest=3,
        global_importance=0,
        actionable=True,
    )
    sections = build_sections([world, action, action])
    assert sections["Action Required"][0].event_id == "mail"
    assert sections["World in Brief"][0].event_id == "world"
    assert render_preview(sections).count("Interview") == 1
    assert "https://source" in render_preview(sections)


def test_youtube_item_renders_worth_watching_metadata() -> None:
    video = BriefingItem(
        event_id="video-1",
        title="A useful video",
        source_urls=["https://www.youtube.com/watch?v=abc"],
        importance=8,
        interest=8,
        global_importance=0,
        video=True,
        source_type="youtube",
        published_at=datetime(2026, 9, 7, 12, tzinfo=UTC),
        why_watch="Explains the new technique.",
    )

    rendered = render_preview(build_sections([video]))

    assert "Worth Watching" in rendered
    assert "A useful video" in rendered
    assert "https://www.youtube.com/watch?v=abc" in rendered
    assert "Published: 2026-09-07T12:00:00+00:00" in rendered
    assert "Explains the new technique." in rendered


def test_briefing_presentation_keeps_legacy_records_and_renders_istanbul_time() -> None:
    sections = legacy_sections(
        "For You\n- NVIDIA update: https://example.test/nvidia\nWorld in Brief\n- Global event"
    )

    assert tuple(sections) == BRIEFING_SECTIONS
    assert sections["Senin İçin / For You"][0].source_links == ["https://example.test/nvidia"]
    assert format_istanbul(datetime(2026, 9, 7, 12, tzinfo=UTC)) == "07.09.2026 15:00"


def test_world_reason_is_independent_of_personal_preferences() -> None:
    assert "kişisel tercihler" in shown_because(
        "Dünyada Neler Oldu? / World in Brief", "NVIDIA", explicit=10, adaptive=10
    )
    assert "Açık“" not in shown_because("Senin İçin / For You", "NVIDIA", 1, 0)
    assert "NVIDIA" in shown_because("Senin İçin / For You", "NVIDIA", 1, 0)
    assert shown_because("Tech & Industry", None, 0, 0) == ""


def test_new_turkish_snapshot_and_legacy_original_text_remain_distinct() -> None:
    current = BriefingViewItem(
        event_id="new", section="Tech & Industry", title="Turkce baslik",
        summary="Turkce kisa ozet.", what_changed="Turkce degisiklik.",
        shown_because="", original_text=False,
    )
    legacy = legacy_sections("For You\n- Original English title: original English text")[
        "Senin İçin / For You"
    ][0]

    assert current.original_text is False
    assert current.summary == "Turkce kisa ozet."
    assert legacy.original_text is True
    assert "original English" in legacy.summary


@pytest.mark.asyncio
async def test_editor_hashes_bounded_current_briefing_and_rejects_empty_input() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content)["messages"][0]["content"])
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"title":"Brief","summary":"Safe"}'}}]},
        )

    router = Router(
        OpenRouterClient("test-key", "https://example.test", httpx.MockTransport(handler)),
        ModelSettings(
            roles={"editor": RoleConfig(model="fake/editor", max_input_chars=300)},
            budgets=BudgetPolicy(daily_soft_usd=1, daily_hard_usd=1),
        ),
        InMemoryResultCache(),
        BudgetTracker(),
    )
    first = {
        "For You": [
            BriefingItem(
                event_id="one",
                title="one",
                source_urls=[],
                importance=6,
                interest=7,
                global_importance=0,
            )
        ]
    }
    second = {
        "For You": [
            BriefingItem(
                event_id="two",
                title="two",
                source_urls=[],
                importance=6,
                interest=7,
                global_importance=0,
            )
        ]
    }

    assert (await edit_compact(first, router)).title == "Brief"
    assert (await edit_compact(second, router)).title == "Brief"
    with pytest.raises(ValueError, match="empty briefing"):
        await edit_compact({"For You": []}, router)

    assert len(calls) == 2
    assert all(len(prompt) <= 300 for prompt in calls)
