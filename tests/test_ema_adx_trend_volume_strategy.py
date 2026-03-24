from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.strategies.base import Candle
from app.domain.strategies.ema_adx_trend_volume import EmaAdxTrendVolumeStrategy


def build_candles(
    closes: list[int],
    *,
    volumes: list[int] | None = None,
) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    volume_values = volumes or [100] * len(closes)
    for index, close in enumerate(closes):
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open_price=Decimal(close),
                high_price=Decimal(close),
                low_price=Decimal(close - 1),
                close_price=Decimal(close),
                volume=Decimal(volume_values[index]),
            )
        )
    return candles


def test_returns_buy_signal_when_crossover_trend_adx_and_volume_match() -> None:
    strategy = EmaAdxTrendVolumeStrategy(
        fast_period=3,
        slow_period=5,
        trend_period=8,
        adx_period=3,
        volume_ema_period=3,
        stop_lookback_candles=4,
    )

    signal = strategy.evaluate(
        build_candles(
            [100, 100, 100, 100, 100, 100, 100, 99, 99, 99, 120],
            volumes=[10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 100],
        )
    )

    assert signal is not None
    assert signal.action == "buy"


def test_returns_none_when_volume_confirmation_fails() -> None:
    strategy = EmaAdxTrendVolumeStrategy(
        fast_period=3,
        slow_period=5,
        trend_period=8,
        adx_period=3,
        volume_ema_period=3,
        stop_lookback_candles=4,
    )

    signal = strategy.evaluate(
        build_candles(
            [100, 100, 100, 100, 100, 100, 100, 99, 99, 99, 120],
            volumes=[10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 11],
        )
    )

    assert signal is None


def test_minimum_candles_uses_trend_adx_volume_and_stop_requirements() -> None:
    strategy = EmaAdxTrendVolumeStrategy(
        fast_period=20,
        slow_period=50,
        trend_period=100,
        adx_period=14,
        volume_ema_period=20,
        stop_lookback_candles=10,
    )

    assert strategy.minimum_candles() == 101
