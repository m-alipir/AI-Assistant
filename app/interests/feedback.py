"""Shared, transaction-safe briefing feedback boundary for every user interface."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import text


class FeedbackConnection(Protocol):
    async def execute(self, statement: object, parameters: object = ...) -> object: ...


@dataclass(frozen=True)
class FeedbackResult:
    status: str
    selected_action: str
    message: str


async def record_briefing_feedback(
    connection: FeedbackConnection,
    briefing_id: str,
    event_id: str,
    action: str,
    *,
    now: datetime | None = None,
) -> FeedbackResult:
    """Record one allowed signal without allowing a UI to alter ranking rules directly."""
    if action not in {"more", "less", "not_useful"}:
        raise ValueError("invalid feedback action")
    result = await connection.execute(
        text(
            "SELECT bi.section, e.canonical_title, coalesce(m.entities_json, '[]') "
            "AS entities_json FROM briefing_items bi "
            "JOIN events e ON e.id = bi.event_id "
            "LEFT JOIN event_search_metadata m ON m.event_id = e.id "
            "WHERE bi.briefing_id = :briefing_id AND bi.event_id = :event_id"
        ),
        {"briefing_id": briefing_id, "event_id": event_id},
    )
    item = result.mappings().one_or_none()  # type: ignore[union-attr]
    if item is None:
        raise LookupError("briefing item not found")
    section = _display_section(str(item["section"]))
    subjects = _json_strings(item["entities_json"])
    subject = (subjects or [str(item["canonical_title"])])[0][:256]
    recorded_action = {
        "more": "explicit_more",
        "less": "explicit_less",
        "not_useful": "dismissed",
    }[action]
    occurred_at = now or datetime.now(UTC)
    await connection.execute(
        text(
            "INSERT INTO feedback_events (subject, action, occurred_at) "
            "VALUES (:subject, :action, :occurred_at)"
        ),
        {"subject": subject, "action": recorded_action, "occurred_at": occurred_at},
    )
    if section != "Dünyada Neler Oldu? / World in Brief" and action in {"more", "less"}:
        delta = 1 if action == "more" else -1
        await connection.execute(
            text(
                "INSERT INTO interest_profile (subject, base, explicit, adaptive) "
                "VALUES (:subject, 0, :delta, 0) "
                "ON CONFLICT (subject) DO UPDATE SET explicit = "
                "greatest(-10, least(10, interest_profile.explicit + :delta))"
            ),
            {"subject": subject, "delta": delta},
        )
    if section == "Dünyada Neler Oldu? / World in Brief":
        return FeedbackResult(
            "recorded",
            action,
            "Geri bildirim kaydedildi; World in Brief kişisel tercihlerden etkilenmez.",
        )
    if action == "not_useful":
        return FeedbackResult(
            "recorded", "not_useful", "Faydalı değil geri bildiriminiz kaydedildi."
        )
    return FeedbackResult(
        "recorded",
        action,
        "Açık tercihiniz kaydedildi ve sonraki kişisel sıralamada uygulanacak.",
    )


def _display_section(value: str) -> str:
    return {"World in Brief": "Dünyada Neler Oldu? / World in Brief"}.get(value, value)


def _json_strings(value: object) -> list[str]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str)]
