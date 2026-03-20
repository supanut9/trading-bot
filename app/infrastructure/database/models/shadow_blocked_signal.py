from decimal import Decimal

from sqlalchemy import Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, TimestampMixin


class ShadowBlockedSignalRecord(TimestampMixin, Base):
    __tablename__ = "shadow_blocked_signals"
    __table_args__ = (
        Index("ix_shadow_blocked_signals_created_at", "created_at"),
        Index("ix_shadow_blocked_signals_lookup", "exchange", "symbol"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(20), nullable=False)
    signal_action: Mapped[str] = mapped_column(String(10), nullable=False)
    signal_reason: Mapped[str | None] = mapped_column(Text)
    block_reason: Mapped[str] = mapped_column(Text, nullable=False)
    block_source: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "risk" | "position_check"
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    client_order_id: Mapped[str | None] = mapped_column(String(100))
