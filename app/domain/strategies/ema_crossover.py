from collections.abc import Sequence
from decimal import Decimal

from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.indicators import (
    calculate_adx,
    calculate_ema,
    calculate_rsi,
    calculate_volume_sma,
)


class EmaCrossoverStrategy:
    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        *,
        rsi_period: int | None = None,
        rsi_overbought: Decimal = Decimal("70"),
        rsi_oversold: Decimal = Decimal("30"),
        volume_ma_period: int | None = None,
        adx_period: int | None = None,
        adx_threshold: Decimal = Decimal("25"),
    ) -> None:
        if fast_period <= 0 or slow_period <= 0:
            raise ValueError("EMA periods must be positive")
        if fast_period >= slow_period:
            raise ValueError("fast_period must be smaller than slow_period")
        if rsi_period is not None and rsi_period <= 0:
            raise ValueError("rsi_period must be positive")
        if volume_ma_period is not None and volume_ma_period <= 0:
            raise ValueError("volume_ma_period must be positive")
        if adx_period is not None and adx_period <= 0:
            raise ValueError("adx_period must be positive")

        self.fast_period = fast_period
        self.slow_period = slow_period
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.volume_ma_period = volume_ma_period
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold

    def minimum_candles(self) -> int:
        base = self.slow_period + 1
        rsi_min = (self.rsi_period + 1) if self.rsi_period is not None else 0
        vol_min = self.volume_ma_period if self.volume_ma_period is not None else 0
        adx_min = (2 * self.adx_period + 1) if self.adx_period is not None else 0
        return max(base, rsi_min, vol_min, adx_min)

    def evaluate(self, candles: Sequence[Candle]) -> Signal | None:
        ordered_candles = sorted(candles, key=lambda candle: candle.open_time)
        closes = [candle.close_price for candle in ordered_candles]
        if len(closes) < self.minimum_candles():
            return None

        fast_emas = calculate_ema(closes, self.fast_period)
        slow_emas = calculate_ema(closes, self.slow_period)

        fast_previous, fast_current = fast_emas[-2], fast_emas[-1]
        slow_previous, slow_current = slow_emas[-2], slow_emas[-1]

        bullish_cross = fast_previous <= slow_previous and fast_current > slow_current
        bearish_cross = fast_previous >= slow_previous and fast_current < slow_current

        if not bullish_cross and not bearish_cross:
            return None

        if self.adx_period is not None:
            highs = [c.high_price for c in ordered_candles]
            lows = [c.low_price for c in ordered_candles]
            try:
                adx = calculate_adx(highs, lows, closes, self.adx_period)
            except ValueError:
                return None
            if adx < self.adx_threshold:
                return None

        if self.rsi_period is not None:
            rsi_window = closes[-(self.rsi_period + 1) :]
            rsi_value = calculate_rsi(rsi_window, self.rsi_period)
            if bullish_cross and rsi_value > self.rsi_overbought:
                return None
            if bearish_cross and rsi_value < self.rsi_oversold:
                return None

        if self.volume_ma_period is not None:
            volumes = [candle.volume for candle in ordered_candles]
            vol_ma = calculate_volume_sma(volumes[:-1], self.volume_ma_period)
            if volumes[-1] <= vol_ma:
                return None

        if bullish_cross:
            return Signal(
                action="buy",
                reason="fast EMA crossed above slow EMA on closed candle",
                fast_value=fast_current,
                slow_value=slow_current,
            )

        return Signal(
            action="sell",
            reason="fast EMA crossed below slow EMA on closed candle",
            fast_value=fast_current,
            slow_value=slow_current,
        )
