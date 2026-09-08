"""Shared SQLAlchemy declarative metadata."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for persisted models introduced in later milestones."""
