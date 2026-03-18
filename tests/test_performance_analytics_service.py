from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.application.services.performance_analytics_service import (
    PerformanceAnalyticsService,
)
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.position import PositionRecord
from app.infrastructure.database.models.trade import TradeRecord
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def build_session(tmp_path: Path):
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'performance_analytics.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    return create_session_factory(settings)()


def seed_trade(
    session,
    *,
    created_at: datetime,
    mode: str,
    symbol: str,
    side: str,
    quantity: str,
    price: str,
    fee_amount: str | None = None,
) -> None:
    order = OrderRecord(
        exchange="binance",
        symbol=symbol,
        side=side,
        order_type="market",
        status="filled",
        mode=mode,
        quantity=Decimal(quantity),
        price=Decimal(price),
        average_fill_price=Decimal(price),
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(order)
    session.flush()
    session.add(
        TradeRecord(
            order_id=order.id,
            exchange="binance",
            symbol=symbol,
            side=side,
            quantity=Decimal(quantity),
            price=Decimal(price),
            fee_amount=Decimal(fee_amount) if fee_amount is not None else None,
            created_at=created_at,
            updated_at=created_at,
        )
    )


def test_builds_mode_summaries_daily_rows_and_equity_curve(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    try:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        seed_trade(
            session,
            created_at=start,
            mode="paper",
            symbol="BTC/USDT",
            side="buy",
            quantity="1.0",
            price="100",
        )
        seed_trade(
            session,
            created_at=start + timedelta(hours=1),
            mode="paper",
            symbol="BTC/USDT",
            side="sell",
            quantity="0.5",
            price="120",
            fee_amount="1.0",
        )
        seed_trade(
            session,
            created_at=start + timedelta(days=1),
            mode="paper",
            symbol="BTC/USDT",
            side="sell",
            quantity="0.5",
            price="90",
            fee_amount="1.0",
        )
        seed_trade(
            session,
            created_at=start + timedelta(days=1, hours=1),
            mode="live",
            symbol="ETH/USDT",
            side="buy",
            quantity="2.0",
            price="50",
        )
        session.add(
            PositionRecord(
                exchange="binance",
                symbol="ETH/USDT",
                mode="live",
                side="long",
                quantity=Decimal("2.0"),
                average_entry_price=Decimal("50"),
                realized_pnl=Decimal("0"),
                unrealized_pnl=Decimal("5.0"),
                created_at=start + timedelta(days=1, hours=1),
                updated_at=start + timedelta(days=1, hours=1),
            )
        )
        session.commit()

        analytics = PerformanceAnalyticsService(session).build()

        assert [summary.mode for summary in analytics.summaries] == ["live", "paper"]

        paper_summary = next(summary for summary in analytics.summaries if summary.mode == "paper")
        assert paper_summary.total_realized_pnl == Decimal("5.0")
        assert paper_summary.total_fees == Decimal("2.0")
        assert paper_summary.net_pnl == Decimal("3.0")
        assert paper_summary.trade_count == 3
        assert paper_summary.closed_trade_count == 2
        assert paper_summary.winning_trades == 1
        assert paper_summary.losing_trades == 1
        assert paper_summary.win_rate_pct == Decimal("50")
        assert paper_summary.average_win == Decimal("9.0")
        assert paper_summary.average_loss == Decimal("6.0")
        assert paper_summary.profit_factor == Decimal("1.5")
        assert paper_summary.expectancy == Decimal("1.5")
        assert paper_summary.max_drawdown == Decimal("6.0")

        live_summary = next(summary for summary in analytics.summaries if summary.mode == "live")
        assert live_summary.total_unrealized_pnl == Decimal("5.0")
        assert live_summary.net_pnl == Decimal("5.0")
        assert live_summary.open_position_count == 1

        assert analytics.daily_rows[0].trade_date.isoformat() == "2026-01-02"
        assert analytics.daily_rows[0].mode == "paper"
        assert analytics.daily_rows[0].net_pnl == Decimal("-6.0")

        paper_curve = [point for point in analytics.equity_curve if point.mode == "paper"]
        assert paper_curve[-1].net_pnl == Decimal("3.0")
    finally:
        session.close()
