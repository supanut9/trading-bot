"""ML signal strategy — works with XGBoost, LightGBM, or Random Forest.

The strategy is pure: no IO. It receives a pre-loaded model and the feature
names it was trained on via constructor. The application layer owns model loading.
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.features import (
    DEFAULT_FEATURE_NAMES,
    _min_candles_for_features,
    build_all_feature_vectors,
    build_feature_vector,
)


class MLSignalStrategy:
    """Unified ML signal strategy supporting XGBoost, LightGBM, and Random Forest."""

    def __init__(
        self,
        model: Any,
        feature_names: list[str] | None = None,
        *,
        buy_threshold: Decimal = Decimal("0.60"),
        sell_threshold: Decimal = Decimal("0.40"),
    ) -> None:
        if model is None:
            raise ValueError("MLSignalStrategy requires a pre-loaded model")
        if buy_threshold <= Decimal("0.5"):
            raise ValueError("buy_threshold must be > 0.5")
        if sell_threshold >= Decimal("0.5"):
            raise ValueError("sell_threshold must be < 0.5")

        self._model = model
        self._feature_names = feature_names if feature_names is not None else DEFAULT_FEATURE_NAMES
        self._buy_threshold = buy_threshold
        self._sell_threshold = sell_threshold

    def minimum_candles(self) -> int:
        return _min_candles_for_features(self._feature_names)

    def batch_evaluate(self, candles: Sequence[Candle]) -> list[Signal | None]:
        """Evaluate all candle positions at once — much faster for backtesting.

        Builds all feature vectors in one pass then calls predict_proba once
        on the full matrix instead of once per candle.
        """
        feature_vectors = build_all_feature_vectors(candles, self._feature_names)

        # Collect valid rows for batch inference
        valid_indices: list[int] = []
        valid_vectors: list[list[float]] = []
        for i, vec in enumerate(feature_vectors):
            if vec is not None:
                valid_indices.append(i)
                valid_vectors.append(vec)

        results: list[Signal | None] = [None] * len(candles)
        if not valid_vectors:
            return results

        try:
            probas = self._model.predict_proba(valid_vectors)
        except Exception:
            return results

        for i, proba in zip(valid_indices, probas, strict=False):
            up_prob = Decimal(str(round(float(proba[1]), 6)))
            if up_prob >= self._buy_threshold:
                results[i] = Signal(
                    action="buy",
                    reason=f"ML up probability {up_prob:.4f} >= {self._buy_threshold}",
                    fast_value=up_prob,
                )
            elif up_prob <= self._sell_threshold:
                sell_prob = Decimal("1") - up_prob
                min_sell = Decimal("1") - self._sell_threshold
                results[i] = Signal(
                    action="sell",
                    reason=f"ML down probability {sell_prob:.4f} >= {min_sell}",
                    fast_value=up_prob,
                )

        return results

    def evaluate(self, candles: Sequence[Candle]) -> Signal | None:
        if len(candles) < self.minimum_candles():
            return None

        features = build_feature_vector(candles, self._feature_names)
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
                reason=f"ML up probability {up_prob:.4f} >= {self._buy_threshold}",
                fast_value=up_prob,
            )
        if up_prob <= self._sell_threshold:
            sell_prob = Decimal("1") - up_prob
            return Signal(
                action="sell",
                reason=(
                    f"ML down probability {sell_prob:.4f} >= {Decimal('1') - self._sell_threshold}"
                ),
                fast_value=up_prob,
            )
        return None
