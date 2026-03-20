from decimal import Decimal

from sqlalchemy import Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, TimestampMixin


class ShadowTradeRecord(TimestampMixin, Base):
    __tablename__ = "shadow_trades"
    __table_args__ = (
        Index("ix_shadow_trades_lookup", "exchange", "symbol", "status"),
        Index("ix_shadow_trades_created_at", "created_at"),
        UniqueConstraint("client_order_id", name="uq_shadow_trades_client_order_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    signal_reason: Mapped[str | None] = mapped_column(Text)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    simulated_fill_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    simulated_exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    simulated_exit_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    entry_fee: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    exit_fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    gross_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    net_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "open" | "closed"
    client_order_id: Mapped[str | None] = mapped_column(String(100))
