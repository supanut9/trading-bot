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


def test_normalizes_newest_first_input_before_evaluating_ema() -> None:
    strategy = EmaCrossoverStrategy(fast_period=3, slow_period=5)
    candles = list(reversed(build_candles([10, 10, 10, 10, 10, 9, 9, 9, 20])))

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "buy"


def build_candles_with_volume(closes: list[int], volumes: list[int]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for index, (close, volume) in enumerate(zip(closes, volumes, strict=True)):
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open_price=Decimal(close),
                high_price=Decimal(close),
                low_price=Decimal(close),
                close_price=Decimal(close),
                volume=Decimal(volume),
            )
        )
    return candles


def test_rsi_filter_suppresses_buy_when_overbought() -> None:
    # Strongly rising prices → RSI will be high (overbought territory).
    # With rsi_period=3 and overbought=70, the crossover buy should be filtered out.
    strategy = EmaCrossoverStrategy(
        fast_period=3,
        slow_period=5,
        rsi_period=3,
        rsi_overbought=Decimal("70"),
    )
    # Prices rising strongly cause overbought RSI at the crossover candle.
    candles = build_candles([10, 10, 10, 10, 10, 11, 14, 18, 30])

    signal = strategy.evaluate(candles)

    assert signal is None


def test_rsi_filter_allows_buy_when_threshold_is_max() -> None:
    # rsi_overbought=100 means RSI can never exceed it → buy signal always allowed.
    strategy = EmaCrossoverStrategy(
        fast_period=3,
        slow_period=5,
        rsi_period=3,
        rsi_overbought=Decimal("100"),
    )
    candles = build_candles([10, 10, 10, 10, 10, 9, 9, 9, 20])

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "buy"


def test_rsi_filter_suppresses_sell_when_oversold() -> None:
    # Strongly falling prices → RSI will be low (oversold territory).
    # With rsi_period=3 and oversold=30, the crossover sell should be filtered out.
    strategy = EmaCrossoverStrategy(
        fast_period=3,
        slow_period=5,
        rsi_period=3,
        rsi_oversold=Decimal("30"),
    )
    candles = build_candles([30, 28, 25, 20, 18, 15, 12, 8, 3])

    signal = strategy.evaluate(candles)

    assert signal is None


def test_volume_filter_suppresses_signal_when_volume_below_average() -> None:
    # Crossover occurs on low-volume candle → filtered out.
    strategy = EmaCrossoverStrategy(fast_period=3, slow_period=5, volume_ma_period=3)
    closes = [10, 10, 10, 10, 10, 9, 9, 9, 20]
    # Previous 3 volumes are high; last candle volume is low (below average).
    volumes = [10, 10, 10, 10, 10, 10, 10, 10, 1]
    candles = build_candles_with_volume(closes, volumes)

    signal = strategy.evaluate(candles)

    assert signal is None


def test_volume_filter_allows_signal_when_volume_above_average() -> None:
    # Crossover occurs on high-volume candle → signal passes.
    strategy = EmaCrossoverStrategy(fast_period=3, slow_period=5, volume_ma_period=3)
    closes = [10, 10, 10, 10, 10, 9, 9, 9, 20]
    # Previous 3 volumes are low; last candle volume is high (above average).
    volumes = [1, 1, 1, 1, 1, 1, 1, 1, 100]
    candles = build_candles_with_volume(closes, volumes)

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "buy"


def test_minimum_candles_increases_with_rsi_and_volume_period() -> None:
    strategy = EmaCrossoverStrategy(fast_period=3, slow_period=5, rsi_period=10, volume_ma_period=8)
    # slow_period+1=6, rsi_period+1=11, volume_ma=8 → minimum is 11
    assert strategy.minimum_candles() == 11
