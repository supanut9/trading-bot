from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class SymbolRulesRecord(Base):
    __tablename__ = "symbol_rules"
    __table_args__ = (UniqueConstraint("exchange", "symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    min_qty: Mapped[Decimal] = mapped_column(Numeric(precision=30, scale=10), nullable=False)
    max_qty: Mapped[Decimal] = mapped_column(Numeric(precision=30, scale=10), nullable=False)
    step_size: Mapped[Decimal] = mapped_column(Numeric(precision=30, scale=10), nullable=False)
    min_notional: Mapped[Decimal] = mapped_column(Numeric(precision=30, scale=10), nullable=False)
    tick_size: Mapped[Decimal] = mapped_column(Numeric(precision=30, scale=10), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
