"""Safe, Turkish-first presentation models for persisted briefings."""

import re
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

BRIEFING_SECTIONS = (
    "Action Required",
    "Senin İçin / For You",
    "Tech & Industry",
    "Connections / Why It Matters",
    "Dünyada Neler Oldu? / World in Brief",
    "Worth Watching",
)

_LEGACY_SECTION_MAP = {
    "Action Required": "Action Required",
    "For You": "Senin İçin / For You",
    "Tech & Industry": "Tech & Industry",
    "Connections / Why It Matters": "Connections / Why It Matters",
    "World in Brief": "Dünyada Neler Oldu? / World in Brief",
    "Worth Watching": "Worth Watching",
}


class BriefingViewItem(BaseModel):
    """Bounded, safe display data; no raw source/transcript/email field exists here."""

    model_config = ConfigDict(extra="forbid")
    event_id: str | None = None
    section: str
    title: str
    summary: str
    what_changed: str | None = None
    why_important: str | None = None
    verified_facts: list[str] = Field(default_factory=list)
    model_inferences: list[str] = Field(default_factory=list)
    source_links: list[str] = Field(default_factory=list)
    source_type: str = "unknown"
    published_at: str | None = None
    shown_because: str
    feedback_subject: str | None = None
    feedback_action: str | None = None
    original_text: bool = False


def compact_sentences(value: str | None, *, limit: int = 3, max_chars: int = 520) -> str:
    """Keep a persisted compact summary readable without rendering raw retained content."""
    normalized = " ".join((value or "").split())[:max_chars]
    if not normalized:
        return "Kaynakta doğrulanmış kısa bir kayıt mevcut; ayrıntı için kaynağı açın."
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    return " ".join(sentences[:limit])


def format_istanbul(value: datetime | None) -> str | None:
    """Render a UTC-aware timestamp for people without changing the stored UTC value."""
    if value is None or value.tzinfo is None:
        return None
    return value.astimezone(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")


def safe_links(values: object) -> list[str]:
    """Preserve only absolute HTTP(S) provenance links in the presentation layer."""
    links: list[str] = []
    for value in values if isinstance(values, list) else []:
        candidate = str(value)
        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            links.append(candidate[:2048])
    return links[:3]


def legacy_sections(rendered: str) -> dict[str, list[BriefingViewItem]]:
    """Read old compact renderings without attempting to reinterpret them as raw source content."""
    sections = {section: [] for section in BRIEFING_SECTIONS}
    current: str | None = None
    for raw_line in rendered.splitlines():
        line = raw_line.strip()
        if line in _LEGACY_SECTION_MAP:
            current = _LEGACY_SECTION_MAP[line]
            continue
        if not current or not line.startswith("- "):
            continue
        body = line[2:]
        title, _, detail = body.partition(":")
        urls = re.findall(r"https?://[^\s,]+", detail)
        sections[current].append(
            BriefingViewItem(
                section=current,
                title=title.strip()[:512] or "Kaydedilmiş briefing öğesi",
                summary=compact_sentences(detail or title),
                source_links=safe_links(urls),
                source_type="legacy",
                shown_because="",
                original_text=True,
            )
        )
    return sections


def shown_because(section: str, subject: str | None, explicit: float, adaptive: float) -> str:
    """Explain placement without exposing ranking internals or hidden source content."""
    if section == "Dünyada Neler Oldu? / World in Brief":
        return "Yüksek küresel önem nedeniyle gösterildi; kişisel tercihler bunu etkilemez."
    if subject and explicit > 0:
        return f"Açık “daha fazla {subject}” tercihinizle eşleştiği için gösterildi."
    if subject and adaptive > 0:
        return f"Zaman içinde öğrenilen {subject} ilginizle eşleştiği için gösterildi."
    if section == "Worth Watching":
        return "Video kaynağı, izlemeye değer içerik olarak sınıflandırıldığı için gösterildi."
    if section == "Action Required":
        return "İşlem veya takip gerektiren bir kayıt olarak sınıflandırıldığı için gösterildi."
    return ""
