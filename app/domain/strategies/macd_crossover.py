"""
MACD Signal-Line Crossover Strategy
=====================================

Entry logic
-----------
Buy  : MACD line crosses above the Signal line (bullish crossover) AND histogram
       is positive (momentum confirmation).
Sell : MACD line crosses below the Signal line (bearish crossover) AND histogram
       is negative.

Default periods follow the classic 12/26/9 configuration.
"""

from collections.abc import Sequence
from decimal import Decimal

from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.indicators import calculate_macd

_DEFAULT_FAST = 12
_DEFAULT_SLOW = 26
_DEFAULT_SIGNAL = 9


class MacdCrossoverStrategy:
    def __init__(
        self,
        fast_period: int = _DEFAULT_FAST,
        slow_period: int = _DEFAULT_SLOW,
        signal_period: int = _DEFAULT_SIGNAL,
    ) -> None:
        if fast_period <= 0 or slow_period <= 0 or signal_period <= 0:
            raise ValueError("all periods must be positive")
        if fast_period >= slow_period:
            raise ValueError("fast_period must be smaller than slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def minimum_candles(self) -> int:
        # Need enough for slow EMA + signal EMA on MACD line
        return self.slow_period + self.signal_period + 1

    def evaluate(self, candles: Sequence[Candle]) -> Signal | None:
        ordered = sorted(candles, key=lambda c: c.open_time)
        closes = [c.close_price for c in ordered]

        if len(closes) < self.minimum_candles():
            return None

        try:
            results = calculate_macd(closes, self.fast_period, self.slow_period, self.signal_period)
        except ValueError:
            return None

        if len(results) < 2:
            return None

        prev = results[-2]
        curr = results[-1]

        bullish_cross = prev.macd_line <= prev.signal_line and curr.macd_line > curr.signal_line
        bearish_cross = prev.macd_line >= prev.signal_line and curr.macd_line < curr.signal_line

        if bullish_cross and curr.histogram > Decimal("0"):
            return Signal(
                action="buy",
                reason=(
                    f"MACD {curr.macd_line:.6f} crossed above signal"
                    f" {curr.signal_line:.6f}"
                    f" (histogram {curr.histogram:.6f})"
                ),
            )

        if bearish_cross and curr.histogram < Decimal("0"):
            return Signal(
                action="sell",
                reason=(
                    f"MACD {curr.macd_line:.6f} crossed below signal"
                    f" {curr.signal_line:.6f}"
                    f" (histogram {curr.histogram:.6f})"
                ),
            )

        return None
