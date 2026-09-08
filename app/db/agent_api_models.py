"""Metadata-only audit records for the separate read-only Agent API."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentApiAuditRow(Base):
    """Never stores caller identity, token, question, source content, or response payload."""

    __tablename__ = "agent_api_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    response_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
