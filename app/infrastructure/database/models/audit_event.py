from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, TimestampMixin


class AuditEventRecord(TimestampMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_created_at", "created_at"),
        Index("ix_audit_events_type_source", "event_type", "source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(50))
    symbol: Mapped[str | None] = mapped_column(String(50))
    timeframe: Mapped[str | None] = mapped_column(String(20))
    channel: Mapped[str | None] = mapped_column(String(20))
    related_event_type: Mapped[str | None] = mapped_column(String(100))
    payload_json: Mapped[str | None] = mapped_column(Text)
