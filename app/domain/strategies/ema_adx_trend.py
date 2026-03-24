from collections.abc import Sequence
from decimal import Decimal

from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.indicators import calculate_adx, calculate_ema


class EmaAdxTrendStrategy:
    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        *,
        trend_period: int = 100,
        adx_period: int = 14,
        adx_threshold: Decimal = Decimal("20"),
    ) -> None:
        if fast_period <= 0 or slow_period <= 0 or trend_period <= 0:
            raise ValueError("EMA periods must be positive")
        if adx_period <= 0:
            raise ValueError("adx_period must be positive")
        if fast_period >= slow_period:
            raise ValueError("fast_period must be smaller than slow_period")
        if slow_period >= trend_period:
            raise ValueError("slow_period must be smaller than trend_period")

        self.fast_period = fast_period
        self.slow_period = slow_period
        self.trend_period = trend_period
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold

    def minimum_candles(self) -> int:
        return max(self.trend_period + 1, (2 * self.adx_period) + 1)

    def evaluate(self, candles: Sequence[Candle]) -> Signal | None:
        ordered_candles = sorted(candles, key=lambda candle: candle.open_time)
        closes = [candle.close_price for candle in ordered_candles]
        if len(closes) < self.minimum_candles():
            return None

        fast_emas = calculate_ema(closes, self.fast_period)
        slow_emas = calculate_ema(closes, self.slow_period)
        trend_emas = calculate_ema(closes, self.trend_period)

        fast_previous, fast_current = fast_emas[-2], fast_emas[-1]
        slow_previous, slow_current = slow_emas[-2], slow_emas[-1]
        trend_current = trend_emas[-1]
        close_current = closes[-1]

        bullish_cross = fast_previous <= slow_previous and fast_current > slow_current
        bearish_cross = fast_previous >= slow_previous and fast_current < slow_current
        if not bullish_cross and not bearish_cross:
            return None

        highs = [candle.high_price for candle in ordered_candles]
        lows = [candle.low_price for candle in ordered_candles]
        try:
            adx = calculate_adx(highs, lows, closes, self.adx_period)
        except ValueError:
            return None
        if adx < self.adx_threshold:
            return None

        bullish_trend = (
            fast_current > trend_current
            and slow_current > trend_current
            and close_current > trend_current
        )
        bearish_trend = (
            fast_current < trend_current
            and slow_current < trend_current
            and close_current < trend_current
        )

        if bullish_cross and bullish_trend:
            return Signal(
                action="buy",
                reason="fast EMA crossed above slow EMA with 100 EMA trend and ADX confirmation",
                fast_value=fast_current,
                slow_value=slow_current,
            )
        if bearish_cross and bearish_trend:
            return Signal(
                action="sell",
                reason="fast EMA crossed below slow EMA with 100 EMA trend and ADX confirmation",
                fast_value=fast_current,
                slow_value=slow_current,
            )
        return None
