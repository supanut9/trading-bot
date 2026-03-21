"""XGBoost-based signal strategy.

The strategy receives a pre-loaded model object from the application layer.
It is pure: no file IO, no config access.

The model must expose a sklearn-compatible predict_proba(X) method that returns
an array of shape (n_samples, 2) where column 1 is the probability of class 1 (up).
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.features import build_feature_vector


class XGBoostSignalStrategy:
    """Signal strategy driven by a pre-trained XGBoost classifier.

    The constructor accepts a pre-loaded model object.  The strategy is
    intentionally agnostic to how the model was trained; the only contract is
    that model.predict_proba([[f0..f7]]) returns probabilities for classes
    [0, 1] where 1 == "up".
    """

    def __init__(
        self,
        model: Any,
        *,
        fast_ema_period: int = 12,
        slow_ema_period: int = 26,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        atr_period: int = 14,
        bb_period: int = 20,
        volume_ma_period: int = 20,
        buy_threshold: Decimal = Decimal("0.55"),
        sell_threshold: Decimal = Decimal("0.45"),
    ) -> None:
        if model is None:
            raise ValueError("XGBoostSignalStrategy requires a pre-loaded model")
        if buy_threshold <= Decimal("0.5"):
            raise ValueError("buy_threshold must be greater than 0.5")
        if sell_threshold >= Decimal("0.5"):
            raise ValueError("sell_threshold must be less than 0.5")

        self._model = model
        self._fast_ema_period = fast_ema_period
        self._slow_ema_period = slow_ema_period
        self._rsi_period = rsi_period
        self._macd_fast = macd_fast
        self._macd_slow = macd_slow
        self._macd_signal = macd_signal
        self._atr_period = atr_period
        self._bb_period = bb_period
        self._volume_ma_period = volume_ma_period
        self._buy_threshold = buy_threshold
        self._sell_threshold = sell_threshold

    def minimum_candles(self) -> int:
        return (
            max(
                self._slow_ema_period,
                self._macd_slow + self._macd_signal,
                self._rsi_period + 1,
                self._bb_period,
                self._atr_period + 1,
                self._volume_ma_period,
            )
            + 1
        )

    def evaluate(self, candles: Sequence[Candle]) -> Signal | None:
        if len(candles) < self.minimum_candles():
            return None

        features = build_feature_vector(
            candles,
            fast_ema_period=self._fast_ema_period,
            slow_ema_period=self._slow_ema_period,
            rsi_period=self._rsi_period,
            macd_fast=self._macd_fast,
            macd_slow=self._macd_slow,
            macd_signal=self._macd_signal,
            atr_period=self._atr_period,
            bb_period=self._bb_period,
            volume_ma_period=self._volume_ma_period,
        )
        if features is None:
            return None

        try:
            proba = self._model.predict_proba([features])[0]
            up_prob = Decimal(str(round(float(proba[1]), 6)))
        except Exception:
            return None

        if up_prob >= self._buy_threshold:
            return Signal(
                action="buy",
                reason=f"XGBoost up probability {up_prob:.4f} >= threshold {self._buy_threshold}",
                fast_value=up_prob,
            )
        if up_prob <= self._sell_threshold:
            sell_prob = Decimal("1") - up_prob
            down_threshold = Decimal("1") - self._sell_threshold
            return Signal(
                action="sell",
                reason=f"XGBoost down probability {sell_prob:.4f} >= threshold {down_threshold}",
                fast_value=up_prob,
            )
        return None
