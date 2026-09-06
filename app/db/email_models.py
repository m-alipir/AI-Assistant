"""Minimal persistent Gmail account/checkpoint and classification records."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GmailAccountRow(Base):
    __tablename__ = "gmail_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    encrypted_refresh_token: Mapped[str] = mapped_column(Text)
    history_id: Mapped[str | None] = mapped_column(String(128))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailClassificationRow(Base):
    __tablename__ = "email_classifications"
    source_item_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    classification: Mapped[str] = mapped_column(String(32))
    action_summary: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    application_company: Mapped[str | None] = mapped_column(String(256))
