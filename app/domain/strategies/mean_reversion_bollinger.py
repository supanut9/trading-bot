"""
Mean-Reversion Bollinger Band Strategy
======================================

Entry logic
-----------
Buy  : close price touches or breaches the lower Bollinger Band AND RSI is below
       the oversold threshold.
Sell : close price touches or breaches the upper Bollinger Band OR RSI is above
       the overbought threshold (whichever comes first).

This strategy is complementary to EMA-crossover: it performs better in ranging/
sideways markets where trend-following strategies underperform.
"""

from collections.abc import Sequence
from decimal import Decimal

from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.indicators import calculate_bollinger_bands, calculate_rsi

_DEFAULT_BB_PERIOD = 20
_DEFAULT_BB_STD_DEV = Decimal("2")
_DEFAULT_RSI_PERIOD = 14
_DEFAULT_RSI_OVERSOLD = Decimal("35")
_DEFAULT_RSI_OVERBOUGHT = Decimal("65")


class MeanReversionBollingerStrategy:
    def __init__(
        self,
        bb_period: int = _DEFAULT_BB_PERIOD,
        bb_std_dev: Decimal = _DEFAULT_BB_STD_DEV,
        rsi_period: int = _DEFAULT_RSI_PERIOD,
        rsi_oversold: Decimal = _DEFAULT_RSI_OVERSOLD,
        rsi_overbought: Decimal = _DEFAULT_RSI_OVERBOUGHT,
    ) -> None:
        if bb_period <= 0:
            raise ValueError("bb_period must be positive")
        if rsi_period <= 0:
            raise ValueError("rsi_period must be positive")
        if rsi_oversold >= rsi_overbought:
            raise ValueError("rsi_oversold must be below rsi_overbought")
        self.bb_period = bb_period
        self.bb_std_dev = bb_std_dev
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    def minimum_candles(self) -> int:
        return max(self.bb_period, self.rsi_period + 1) + 1

    def evaluate(self, candles: Sequence[Candle]) -> Signal | None:
        ordered = sorted(candles, key=lambda c: c.open_time)
        closes = [c.close_price for c in ordered]

        if len(closes) < self.minimum_candles():
            return None

        bands = calculate_bollinger_bands(closes, self.bb_period, self.bb_std_dev)
        rsi_window = closes[-(self.rsi_period + 1) :]
        rsi = calculate_rsi(rsi_window, self.rsi_period)

        current_close = closes[-1]

        at_lower_band = current_close <= bands.lower
        at_upper_band = current_close >= bands.upper
        oversold = rsi <= self.rsi_oversold
        overbought = rsi >= self.rsi_overbought

        if at_lower_band and oversold:
            return Signal(
                action="buy",
                reason=(
                    f"price {current_close} touched lower BB {bands.lower:.4f}"
                    f" with RSI {rsi:.2f} oversold"
                ),
            )

        if at_upper_band or overbought:
            reason_parts = []
            if at_upper_band:
                reason_parts.append(f"price {current_close} reached upper BB {bands.upper:.4f}")
            if overbought:
                reason_parts.append(f"RSI {rsi:.2f} overbought")
            return Signal(action="sell", reason=" / ".join(reason_parts))

        return None
