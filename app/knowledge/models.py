"""Narrow SQLAlchemy model metadata for the M3 relational knowledge schema."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CategoryRow(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True)
    name: Mapped[str] = mapped_column(String(256))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"))
    materialized_path: Mapped[str] = mapped_column(String(512), unique=True)


class EntityRow(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(256), unique=True)
    entity_type: Mapped[str] = mapped_column(String(64), default="other")


class EntityAliasRow(Base):
    __tablename__ = "entity_aliases"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    alias: Mapped[str] = mapped_column(String(256))
    normalized_alias: Mapped[str] = mapped_column(String(256), unique=True)


class TopicRow(Base):
    __tablename__ = "topics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True)
    name: Mapped[str] = mapped_column(String(256))


class EventRow(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canonical_title: Mapped[str] = mapped_column(String(512))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    embedding_dimensions: Mapped[int] = mapped_column(Integer)
    raw_content: Mapped[str | None] = mapped_column(Text)


class EventSourceRow(Base):
    __tablename__ = "event_sources"
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), primary_key=True)
    source_item_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    relation: Mapped[str] = mapped_column(String(32), default="primary")


class ClaimRow(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    source_item_id: Mapped[str] = mapped_column(String(256))
    statement: Mapped[str] = mapped_column(Text)
    source_locator: Mapped[str | None] = mapped_column(String(512))


class InferenceRow(Base):
    __tablename__ = "inferences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    inference_text: Mapped[str] = mapped_column(Text)
    inference_type: Mapped[str] = mapped_column(String(64))
