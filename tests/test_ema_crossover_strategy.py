from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.strategies.base import Candle
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


def test_returns_buy_signal_when_fast_ema_crosses_above_slow_ema() -> None:
    strategy = EmaCrossoverStrategy(fast_period=3, slow_period=5)
    candles = build_candles([10, 10, 10, 10, 10, 9, 9, 9, 20])

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "buy"
    assert signal.fast_value > signal.slow_value


def test_returns_sell_signal_when_fast_ema_crosses_below_slow_ema() -> None:
    strategy = EmaCrossoverStrategy(fast_period=3, slow_period=5)
    candles = build_candles([20, 20, 20, 20, 20, 21, 21, 21, 5])

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "sell"
    assert signal.fast_value < signal.slow_value


def test_returns_none_when_not_enough_candles_are_available() -> None:
    strategy = EmaCrossoverStrategy(fast_period=3, slow_period=5)

    signal = strategy.evaluate(build_candles([10, 11, 12, 13, 14]))

    assert signal is None


def test_returns_none_when_no_crossover_occurs() -> None:
    strategy = EmaCrossoverStrategy(fast_period=3, slow_period=5)
    candles = build_candles([10, 11, 12, 13, 14, 15, 16, 17])

    signal = strategy.evaluate(candles)

    assert signal is None
