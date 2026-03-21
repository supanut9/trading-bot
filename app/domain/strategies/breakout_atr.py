"""
Breakout + ATR Strategy
========================

Entry logic
-----------
Buy  : Close price breaks above the N-period high by at least `atr_breakout_multiplier`
       × ATR. This confirms the breakout is significant, not just noise.
Sell : Close price falls more than `atr_stop_multiplier` × ATR below the entry
       high (trailing stop), OR close drops back below the period high (channel exit).

This strategy is designed for trending/breakout market regimes. It is
complementary to the mean-reversion Bollinger strategy.
"""

from collections.abc import Sequence
from decimal import Decimal

from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.indicators import calculate_atr

_DEFAULT_BREAKOUT_PERIOD = 20
_DEFAULT_ATR_PERIOD = 14
_DEFAULT_ATR_BREAKOUT_MULT = Decimal("0.5")
_DEFAULT_ATR_STOP_MULT = Decimal("2.0")


class BreakoutAtrStrategy:
    def __init__(
        self,
        breakout_period: int = _DEFAULT_BREAKOUT_PERIOD,
        atr_period: int = _DEFAULT_ATR_PERIOD,
        atr_breakout_multiplier: Decimal = _DEFAULT_ATR_BREAKOUT_MULT,
        atr_stop_multiplier: Decimal = _DEFAULT_ATR_STOP_MULT,
    ) -> None:
        if breakout_period <= 0:
            raise ValueError("breakout_period must be positive")
        if atr_period <= 0:
            raise ValueError("atr_period must be positive")
        if atr_breakout_multiplier <= Decimal("0"):
            raise ValueError("atr_breakout_multiplier must be positive")
        if atr_stop_multiplier <= Decimal("0"):
            raise ValueError("atr_stop_multiplier must be positive")
        self.breakout_period = breakout_period
        self.atr_period = atr_period
        self.atr_breakout_multiplier = atr_breakout_multiplier
        self.atr_stop_multiplier = atr_stop_multiplier

    def minimum_candles(self) -> int:
        return max(self.breakout_period, self.atr_period) + 2

    def evaluate(self, candles: Sequence[Candle]) -> Signal | None:
        ordered = sorted(candles, key=lambda c: c.open_time)

        if len(ordered) < self.minimum_candles():
            return None

        closes = [c.close_price for c in ordered]
        highs = [c.high_price for c in ordered]
        lows = [c.low_price for c in ordered]

        current_close = closes[-1]

        # ATR over the most recent period
        atr = calculate_atr(
            highs[-(self.atr_period + 1) :],
            lows[-(self.atr_period + 1) :],
            closes[-(self.atr_period + 1) :],
            self.atr_period,
        )

        # N-period high excluding the current candle
        period_high = max(highs[-self.breakout_period - 1 : -1])
        period_low = min(lows[-self.breakout_period - 1 : -1])

        breakout_threshold = period_high + self.atr_breakout_multiplier * atr
        stop_threshold = period_low - self.atr_stop_multiplier * atr

        if current_close > breakout_threshold:
            return Signal(
                action="buy",
                reason=(
                    f"price {current_close} broke above {self.breakout_period}-period high"
                    f" {period_high:.4f} by {self.atr_breakout_multiplier}×ATR"
                    f" (ATR={atr:.4f}, threshold={breakout_threshold:.4f})"
                ),
            )

        if current_close < stop_threshold or current_close < period_high:
            return Signal(
                action="sell",
                reason=(
                    f"price {current_close} fell below breakout channel"
                    f" (period high={period_high:.4f},"
                    f" ATR stop={stop_threshold:.4f})"
                ),
            )

        return None
