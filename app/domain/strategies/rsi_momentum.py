"""
RSI Momentum (RSI-50 Crossover) Strategy
==========================================

Entry logic
-----------
Buy  : RSI crosses UP through the 50 level from below — signals a shift from
       bearish to bullish momentum.
Sell : RSI crosses DOWN through the 50 level from above — signals a shift from
       bullish to bearish momentum.

This strategy requires only the RSI indicator (no EMA dependency), produces
independent signals from trend-following strategies, and works across timeframes.

Optional: minimum distance filter — RSI must move at least `min_cross_distance`
points through the 50 level to avoid whipsaws near the midline.
"""

from collections.abc import Sequence
from decimal import Decimal

from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.indicators import calculate_rsi

_DEFAULT_RSI_PERIOD = 14
_DEFAULT_MIDLINE = Decimal("50")
_DEFAULT_MIN_DISTANCE = Decimal("0")  # disabled by default


class RsiMomentumStrategy:
    def __init__(
        self,
        rsi_period: int = _DEFAULT_RSI_PERIOD,
        midline: Decimal = _DEFAULT_MIDLINE,
        min_cross_distance: Decimal = _DEFAULT_MIN_DISTANCE,
    ) -> None:
        if rsi_period <= 0:
            raise ValueError("rsi_period must be positive")
        if not (Decimal("0") < midline < Decimal("100")):
            raise ValueError("midline must be between 0 and 100")
        if min_cross_distance < Decimal("0"):
            raise ValueError("min_cross_distance must be non-negative")
        self.rsi_period = rsi_period
        self.midline = midline
        self.min_cross_distance = min_cross_distance

    def minimum_candles(self) -> int:
        # Need 2 RSI readings = rsi_period + 2 candles
        return self.rsi_period + 2

    def evaluate(self, candles: Sequence[Candle]) -> Signal | None:
        ordered = sorted(candles, key=lambda c: c.open_time)
        closes = [c.close_price for c in ordered]

        if len(closes) < self.minimum_candles():
            return None

        # Calculate RSI for last two bars
        rsi_prev = calculate_rsi(closes[-(self.rsi_period + 2) : -1], self.rsi_period)
        rsi_curr = calculate_rsi(closes[-(self.rsi_period + 1) :], self.rsi_period)

        bullish_cross = (
            rsi_prev < self.midline
            and rsi_curr >= self.midline
            and (rsi_curr - self.midline) >= self.min_cross_distance
        )
        bearish_cross = (
            rsi_prev > self.midline
            and rsi_curr <= self.midline
            and (self.midline - rsi_curr) >= self.min_cross_distance
        )

        if bullish_cross:
            return Signal(
                action="buy",
                reason=(
                    f"RSI crossed above midline {self.midline} ({rsi_prev:.2f} → {rsi_curr:.2f})"
                ),
            )

        if bearish_cross:
            return Signal(
                action="sell",
                reason=(
                    f"RSI crossed below midline {self.midline} ({rsi_prev:.2f} → {rsi_curr:.2f})"
                ),
            )

        return None
