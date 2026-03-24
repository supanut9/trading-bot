from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.strategies.base import Candle
from app.domain.strategies.ema_adx_trend import EmaAdxTrendStrategy


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


def test_returns_buy_signal_when_crossover_and_trend_alignment_match() -> None:
    strategy = EmaAdxTrendStrategy(
        fast_period=3,
        slow_period=5,
        trend_period=8,
        adx_period=3,
        adx_threshold=Decimal("20"),
    )

    signal = strategy.evaluate(build_candles([100, 100, 100, 100, 100, 100, 100, 99, 99, 99, 120]))

    assert signal is not None
    assert signal.action == "buy"
    assert signal.fast_value is not None
    assert signal.slow_value is not None
    assert signal.fast_value > signal.slow_value


def test_returns_sell_signal_when_bearish_crossover_and_trend_alignment_match() -> None:
    strategy = EmaAdxTrendStrategy(
        fast_period=3,
        slow_period=5,
        trend_period=8,
        adx_period=3,
        adx_threshold=Decimal("20"),
    )

    signal = strategy.evaluate(
        build_candles([120, 120, 120, 120, 120, 120, 120, 121, 121, 121, 80])
    )

    assert signal is not None
    assert signal.action == "sell"
    assert signal.fast_value is not None
    assert signal.slow_value is not None
    assert signal.fast_value < signal.slow_value


def test_returns_none_when_crossover_happens_against_trend_filter() -> None:
    strategy = EmaAdxTrendStrategy(
        fast_period=3,
        slow_period=5,
        trend_period=8,
        adx_period=3,
        adx_threshold=Decimal("20"),
    )

    signal = strategy.evaluate(
        build_candles([120, 120, 120, 120, 120, 120, 120, 100, 100, 100, 110])
    )

    assert signal is None


def test_returns_none_when_adx_threshold_is_too_high() -> None:
    strategy = EmaAdxTrendStrategy(
        fast_period=3,
        slow_period=5,
        trend_period=8,
        adx_period=3,
        adx_threshold=Decimal("99"),
    )

    signal = strategy.evaluate(build_candles([100, 100, 100, 100, 100, 100, 100, 99, 99, 99, 120]))

    assert signal is None


def test_minimum_candles_uses_trend_and_adx_requirements() -> None:
    strategy = EmaAdxTrendStrategy(
        fast_period=20,
        slow_period=50,
        trend_period=100,
        adx_period=14,
    )

    assert strategy.minimum_candles() == 101
