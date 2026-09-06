"""Deterministic M6 briefing queues and local preview."""

from pydantic import BaseModel, ConfigDict, Field

from app.llm.core import Router


class BriefingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    title: str
    source_urls: list[str]
    importance: int = Field(ge=0, le=10)
    interest: int = Field(ge=0, le=10)
    global_importance: int = Field(ge=0, le=10)
    actionable: bool = False
    video: bool = False
    connection: str | None = None


def build_sections(items: list[BriefingItem]) -> dict[str, list[BriefingItem]]:
    unique = {item.event_id: item for item in items}.values()
    ordered = sorted(unique, key=lambda item: item.importance, reverse=True)
    world = [item for item in ordered if item.global_importance >= 7][:7]
    return {
        "Action Required": [item for item in ordered if item.actionable],
        "For You": [item for item in ordered if item.interest >= 7 and not item.actionable],
        "Tech & Industry": [
            item
            for item in ordered
            if item.importance >= 5 and item not in world and not item.actionable
        ],
        "Connections / Why It Matters": [item for item in ordered if item.connection],
        "World in Brief": world,
        "Worth Watching": [item for item in ordered if item.video],
    }


def render_preview(sections: dict[str, list[BriefingItem]]) -> str:
    return "\n".join(
        f"{section}\n"
        + "\n".join(f"- {item.title}: {', '.join(item.source_urls)}" for item in items)
        for section, items in sections.items()
        if items
    )


class EditedBriefing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    summary: str


async def edit_compact(sections: dict[str, list[BriefingItem]], router: Router) -> EditedBriefing:
    context = {
        name: [item.model_dump(include={"title", "source_urls"}) for item in items]
        for name, items in sections.items()
    }
    return await router.structured("editor", str(context), "briefing", EditedBriefing, "v1", "v1")
