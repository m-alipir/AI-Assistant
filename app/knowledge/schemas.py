"""Validated boundaries for M3 knowledge records and retrieval requests."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Category(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str
    name: str
    path: str
    parent_path: str | None = None


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)


class SourceBackedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str
    source_item_id: str
    source_locator: str | None = None


class Inference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str
    inference_type: str
    supporting_claim_ids: list[str] = Field(default_factory=list)


class EventDraft(BaseModel):
    """A source-provenanced event; claims and inferences remain separate collections."""

    model_config = ConfigDict(extra="forbid")
    event_id: str
    title: str
    occurred_at: datetime
    category_paths: list[str]
    entities: list[str]
    topics: list[str]
    source_item_ids: list[str]
    claims: list[SourceBackedClaim]
    inferences: list[Inference] = Field(default_factory=list)
    embedding: list[float] = Field(min_length=1)
    raw_content: str | None = None


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category_path: str | None = None
    entity: str | None = None
    topic: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    text: str | None = None
    embedding: list[float] | None = None
    limit: int = Field(default=10, ge=1, le=50)


class RetrievedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: EventDraft
    lexical_score: float
    semantic_score: float
    combined_score: float
