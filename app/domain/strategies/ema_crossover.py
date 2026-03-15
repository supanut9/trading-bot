from collections.abc import Sequence
from decimal import Decimal

from app.domain.strategies.base import Candle, Signal


def calculate_ema(prices: Sequence[Decimal], period: int) -> list[Decimal]:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(prices) < period:
        raise ValueError("not enough prices to calculate EMA")

    smoothing = Decimal("2") / Decimal(period + 1)
    seed = sum(prices[:period], start=Decimal("0")) / Decimal(period)
    values: list[Decimal] = [seed]
    previous = seed

    for price in prices[period:]:
        previous = (price - previous) * smoothing + previous
        values.append(previous)

    return values


class EmaCrossoverStrategy:
    def __init__(self, fast_period: int = 20, slow_period: int = 50) -> None:
        if fast_period <= 0 or slow_period <= 0:
            raise ValueError("EMA periods must be positive")
        if fast_period >= slow_period:
            raise ValueError("fast_period must be smaller than slow_period")

        self.fast_period = fast_period
        self.slow_period = slow_period

    def evaluate(self, candles: Sequence[Candle]) -> Signal | None:
        ordered_candles = sorted(candles, key=lambda candle: candle.open_time)
        closes = [candle.close_price for candle in ordered_candles]
        minimum_candles = self.slow_period + 1
        if len(closes) < minimum_candles:
            return None

        fast_emas = calculate_ema(closes, self.fast_period)
        slow_emas = calculate_ema(closes, self.slow_period)

        fast_previous, fast_current = fast_emas[-2], fast_emas[-1]
        slow_previous, slow_current = slow_emas[-2], slow_emas[-1]

        if fast_previous <= slow_previous and fast_current > slow_current:
            return Signal(
                action="buy",
                reason="fast EMA crossed above slow EMA on closed candle",
                fast_value=fast_current,
                slow_value=slow_current,
            )

        if fast_previous >= slow_previous and fast_current < slow_current:
            return Signal(
                action="sell",
                reason="fast EMA crossed below slow EMA on closed candle",
                fast_value=fast_current,
                slow_value=slow_current,
            )

        return None
