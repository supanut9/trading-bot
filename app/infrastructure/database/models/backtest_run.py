from decimal import Decimal

from sqlalchemy import Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, TimestampMixin


class BacktestRunRecord(TimestampMixin, Base):
    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_backtest_runs_created_at", "created_at"),
        Index("ix_backtest_runs_strategy_market", "strategy_name", "symbol", "timeframe"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(20), nullable=False)
    fast_period: Mapped[int | None]
    slow_period: Mapped[int | None]
    starting_equity_input: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    candle_count: Mapped[int] = mapped_column(nullable=False)
    required_candles: Mapped[int] = mapped_column(nullable=False)
    starting_equity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    ending_equity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    total_return_pct: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    max_drawdown_pct: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    total_trades: Mapped[int | None]
    winning_trades: Mapped[int | None]
    losing_trades: Mapped[int | None]
    total_fees_paid: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    slippage_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    fee_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    walk_forward_split_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    walk_forward_in_sample_candles: Mapped[int | None]
    walk_forward_oos_candles: Mapped[int | None]
    walk_forward_in_sample_return_pct: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    walk_forward_oos_return_pct: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    walk_forward_oos_drawdown_pct: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    walk_forward_oos_total_trades: Mapped[int | None]
    walk_forward_return_degradation_pct: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    walk_forward_overfitting_warning: Mapped[bool | None]
    rules_json: Mapped[str | None] = mapped_column(Text)
