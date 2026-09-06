from app.briefing.core import BriefingItem, build_sections, render_preview


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
