from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.application.services.backtest_service import BacktestService
from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.ema_crossover import EmaCrossoverStrategy


def build_candles(closes: list[int]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for index, close in enumerate(closes):
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open_price=Decimal(close),
                high_price=Decimal(close),
                low_price=Decimal(close),
                close_price=Decimal(close),
                volume=Decimal("1"),
            )
        )
    return candles


class StubStrategy:
    def evaluate(self, candles: list[Candle]) -> Signal | None:
        latest_close = candles[-1].close_price
        if latest_close == Decimal("20"):
            return Signal(
                action="buy",
                reason="stub entry",
                fast_value=Decimal("1"),
                slow_value=Decimal("0"),
            )
        if latest_close == Decimal("30"):
            return Signal(
                action="sell",
                reason="stub exit",
                fast_value=Decimal("0"),
                slow_value=Decimal("1"),
            )
        return None


def test_backtest_runs_round_trip_and_realizes_profit() -> None:
    service = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
    )

    result = service.run(build_candles([10, 12, 20, 30]))

    assert result.total_trades >= 2
    assert result.ending_equity > result.starting_equity
    assert result.realized_pnl > Decimal("0")
    assert result.winning_trades >= 1


def test_backtest_returns_no_trades_when_no_crossover_occurs() -> None:
    service = BacktestService(
        strategy=EmaCrossoverStrategy(fast_period=3, slow_period=5),
        starting_equity=Decimal("10000"),
    )

    result = service.run(build_candles([10, 11, 12, 13, 14, 15, 16, 17]))

    assert result.total_trades == 0
    assert result.ending_equity == Decimal("10000")
    assert result.realized_pnl == Decimal("0")


def test_backtest_forces_close_open_position_on_final_candle() -> None:
    service = BacktestService(
        strategy=EmaCrossoverStrategy(fast_period=3, slow_period=5),
        starting_equity=Decimal("10000"),
    )

    result = service.run(build_candles([10, 10, 10, 10, 10, 9, 9, 9, 20]))

    assert result.total_trades == 2
    assert result.executions[-1].reason == "forced close on final candle"
    assert result.ending_equity == result.starting_equity


def test_backtest_marks_equity_to_market_for_drawdown() -> None:
    service = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
    )

    result = service.run(build_candles([10, 20, 10, 30]))

    assert result.max_drawdown_pct > Decimal("0")
