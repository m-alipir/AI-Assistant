"""Deterministic M7 interest layers; world ranking intentionally ignores these weights."""

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict


class Feedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str
    action: str
    at: datetime


class Interest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base: float = 0
    explicit: float = 0
    adaptive: float = 0

    @property
    def effective(self) -> float:
        return self.base + self.explicit + self.adaptive


def explicit_intent(text: str) -> tuple[str, int] | None:
    words = text.casefold().split()
    if "more" in words:
        return (words[-1], 1)
    if "less" in words:
        return (words[-1], -1)
    return None


def nightly(current: Interest, feedback: list[Feedback], now: datetime) -> Interest:
    recent = [f for f in feedback if f.at >= now - timedelta(days=14) and f.action == "positive"]
    days = {f.at.date() for f in recent}
    if len(recent) >= 4 and len(days) >= 3:
        return current.model_copy(update={"adaptive": min(current.adaptive + 0.25, 1)})
    if feedback and max(f.at for f in feedback) < now - timedelta(days=21):
        return current.model_copy(update={"adaptive": current.adaptive * 0.5})
    return current
