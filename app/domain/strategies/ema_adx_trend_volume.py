from collections.abc import Sequence
from decimal import Decimal

from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.indicators import calculate_adx, calculate_ema


class EmaAdxTrendVolumeStrategy:
    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        *,
        trend_period: int = 100,
        adx_period: int = 14,
        adx_threshold: Decimal = Decimal("20"),
        volume_ema_period: int = 20,
        volume_multiplier: Decimal = Decimal("1.2"),
        stop_lookback_candles: int = 10,
        risk_reward_multiple: Decimal = Decimal("2.0"),
        risk_per_trade_pct: Decimal = Decimal("0.01"),
    ) -> None:
        if fast_period <= 0 or slow_period <= 0 or trend_period <= 0:
            raise ValueError("EMA periods must be positive")
        if fast_period >= slow_period:
            raise ValueError("fast_period must be smaller than slow_period")
        if slow_period >= trend_period:
            raise ValueError("slow_period must be smaller than trend_period")
        if adx_period <= 0:
            raise ValueError("adx_period must be positive")
        if volume_ema_period <= 0:
            raise ValueError("volume_ema_period must be positive")
        if stop_lookback_candles <= 0:
            raise ValueError("stop_lookback_candles must be positive")
        if volume_multiplier <= Decimal("0"):
            raise ValueError("volume_multiplier must be positive")
        if risk_reward_multiple <= Decimal("0"):
            raise ValueError("risk_reward_multiple must be positive")
        if risk_per_trade_pct <= Decimal("0"):
            raise ValueError("risk_per_trade_pct must be positive")

        self.fast_period = fast_period
        self.slow_period = slow_period
        self.trend_period = trend_period
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.volume_ema_period = volume_ema_period
        self.volume_multiplier = volume_multiplier
        self.stop_lookback_candles = stop_lookback_candles
        self.risk_reward_multiple = risk_reward_multiple
        self.risk_per_trade_pct = risk_per_trade_pct

    def minimum_candles(self) -> int:
        return max(
            self.trend_period + 1,
            (2 * self.adx_period) + 1,
            self.volume_ema_period,
            self.stop_lookback_candles + 1,
        )

    def evaluate(self, candles: Sequence[Candle]) -> Signal | None:
        ordered_candles = sorted(candles, key=lambda candle: candle.open_time)
        if len(ordered_candles) < self.minimum_candles():
            return None

        closes = [candle.close_price for candle in ordered_candles]
        volumes = [candle.volume for candle in ordered_candles]
        highs = [candle.high_price for candle in ordered_candles]
        lows = [candle.low_price for candle in ordered_candles]

        fast_emas = calculate_ema(closes, self.fast_period)
        slow_emas = calculate_ema(closes, self.slow_period)
        trend_emas = calculate_ema(closes, self.trend_period)
        volume_emas = calculate_ema(volumes, self.volume_ema_period)

        fast_previous, fast_current = fast_emas[-2], fast_emas[-1]
        slow_previous, slow_current = slow_emas[-2], slow_emas[-1]
        trend_current = trend_emas[-1]
        close_current = closes[-1]
        volume_current = volumes[-1]
        volume_ema_current = volume_emas[-1]

        bullish_cross = fast_previous <= slow_previous and fast_current > slow_current
        if not bullish_cross:
            return None

        if close_current <= trend_current:
            return None

        try:
            adx = calculate_adx(highs, lows, closes, self.adx_period)
        except ValueError:
            return None
        if adx < self.adx_threshold:
            return None

        if volume_current < (volume_ema_current * self.volume_multiplier):
            return None

        stop_price = min(
            candle.low_price for candle in ordered_candles[-self.stop_lookback_candles :]
        )
        if stop_price >= close_current:
            return None

        return Signal(
            action="buy",
            reason=(
                "fast EMA crossed above slow EMA with close above EMA 100, "
                "ADX confirmation, and volume confirmation"
            ),
            fast_value=fast_current,
            slow_value=slow_current,
        )
