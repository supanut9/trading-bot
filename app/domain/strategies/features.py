"""Feature engineering for ML-based strategies.

All functions are pure (no IO, no config). The feature set is extensible:
add new features by adding a key to _FEATURE_COMPUTERS and ALL_FEATURE_NAMES.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import Decimal

from app.domain.strategies.base import Candle
from app.domain.strategies.indicators import (
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_volume_sma,
)

# ── Feature catalogue ────────────────────────────────────────────────────────

FEATURE_GROUPS: dict[str, list[str]] = {
    "Trend": ["ema_diff_pct", "bb_position", "roc_5", "adx"],
    "Momentum": ["rsi", "macd_histogram", "stoch_k"],
    "Volatility": ["atr_pct", "bb_width", "high_low_pct"],
    "Volume": ["volume_ratio"],
    "Candle": ["candle_body_pct", "wick_upper_pct", "wick_lower_pct"],
    "Lag Returns": ["close_lag_1", "close_lag_2", "close_lag_3"],
    "Time": ["hour_sin", "hour_cos"],
}

ALL_FEATURE_NAMES: list[str] = [f for group in FEATURE_GROUPS.values() for f in group]

# Default feature set (original 8, kept for backward compat)
DEFAULT_FEATURE_NAMES: list[str] = [
    "ema_diff_pct",
    "rsi",
    "macd_histogram",
    "atr_pct",
    "volume_ratio",
    "bb_position",
    "candle_body_pct",
    "high_low_pct",
]

# Backward-compat alias used by old code that imported FEATURE_NAMES
FEATURE_NAMES: list[str] = DEFAULT_FEATURE_NAMES

# Minimum candle window needed regardless of feature selection
_BASE_WARMUP = 37


def _safe_div(a: Decimal, b: Decimal, default: float = 0.0) -> float:
    return float(a / b) if b != Decimal("0") else default


def build_feature_vector(
    candles: Sequence[Candle],
    feature_names: list[str] | None = None,
    # Legacy keyword-only params kept for backward compat — ignored when feature_names provided
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
) -> list[float] | None:
    """Compute feature vector for the latest candle. Returns None if not enough data."""
    names = feature_names if feature_names is not None else DEFAULT_FEATURE_NAMES
    ordered = sorted(candles, key=lambda c: c.open_time)

    # Need enough candles for all requested features
    min_needed = _min_candles_for_features(names)
    if len(ordered) < min_needed:
        return None

    closes = [c.close_price for c in ordered]
    highs = [c.high_price for c in ordered]
    lows = [c.low_price for c in ordered]
    volumes = [c.volume for c in ordered]
    latest = ordered[-1]

    try:
        computed: dict[str, float] = {}

        if "ema_diff_pct" in names:
            fast = calculate_ema(closes, 12)[-1]
            slow = calculate_ema(closes, 26)[-1]
            computed["ema_diff_pct"] = _safe_div(fast - slow, latest.close_price)

        if "bb_position" in names or "bb_width" in names:
            bb = calculate_bollinger_bands(closes[-20:], 20, Decimal("2"))
            band_range = bb.upper - bb.lower
            computed["bb_position"] = _safe_div(latest.close_price - bb.lower, band_range, 0.5)
            computed["bb_width"] = _safe_div(band_range, bb.middle, 0.0)

        if "rsi" in names:
            computed["rsi"] = float(calculate_rsi(closes[-15:], 14))

        if "macd_histogram" in names:
            macd_results = calculate_macd(closes, 12, 26, 9)
            computed["macd_histogram"] = float(macd_results[-1].histogram) if macd_results else 0.0

        if "stoch_k" in names:
            period = 14
            window_h = highs[-period:]
            window_l = lows[-period:]
            highest_h = max(window_h)
            lowest_l = min(window_l)
            rng = highest_h - lowest_l
            computed["stoch_k"] = _safe_div(latest.close_price - lowest_l, rng, 0.5) * 100

        if "atr_pct" in names:
            atr = calculate_atr(highs[-15:], lows[-15:], closes[-15:], 14)
            computed["atr_pct"] = _safe_div(atr, latest.close_price)

        if "volume_ratio" in names:
            vol_sma = calculate_volume_sma(volumes[-20:], 20)
            computed["volume_ratio"] = _safe_div(latest.volume, vol_sma, 1.0)

        if "candle_body_pct" in names:
            computed["candle_body_pct"] = _safe_div(
                abs(latest.close_price - latest.open_price), latest.open_price
            )

        if "wick_upper_pct" in names:
            body_top = max(latest.open_price, latest.close_price)
            computed["wick_upper_pct"] = _safe_div(latest.high_price - body_top, latest.open_price)

        if "wick_lower_pct" in names:
            body_bot = min(latest.open_price, latest.close_price)
            computed["wick_lower_pct"] = _safe_div(body_bot - latest.low_price, latest.open_price)

        if "high_low_pct" in names:
            computed["high_low_pct"] = _safe_div(
                latest.high_price - latest.low_price, latest.open_price
            )

        if "roc_5" in names:
            if len(closes) >= 6:
                computed["roc_5"] = _safe_div(closes[-1] - closes[-6], closes[-6])
            else:
                computed["roc_5"] = 0.0

        if "adx" in names:
            computed["adx"] = float(calculate_adx(highs[-30:], lows[-30:], closes[-30:], 14))

        if "close_lag_1" in names:
            computed["close_lag_1"] = (
                _safe_div(closes[-1] - closes[-2], closes[-2]) if len(closes) >= 2 else 0.0
            )

        if "close_lag_2" in names:
            computed["close_lag_2"] = (
                _safe_div(closes[-2] - closes[-3], closes[-3]) if len(closes) >= 3 else 0.0
            )

        if "close_lag_3" in names:
            computed["close_lag_3"] = (
                _safe_div(closes[-3] - closes[-4], closes[-4]) if len(closes) >= 4 else 0.0
            )

        if "hour_sin" in names:
            computed["hour_sin"] = math.sin(2 * math.pi * latest.open_time.hour / 24)

        if "hour_cos" in names:
            computed["hour_cos"] = math.cos(2 * math.pi * latest.open_time.hour / 24)

    except (ValueError, ZeroDivisionError, IndexError):
        return None

    return [computed[name] for name in names]


def _min_candles_for_features(names: list[str]) -> int:
    needs = [_BASE_WARMUP]
    if "adx" in names:
        needs.append(30)
    if any(f in names for f in ("close_lag_3",)):
        needs.append(5)
    return max(needs)


# Backward-compat alias: old callers used MIN_CANDLES_FOR_FEATURES
MIN_CANDLES_FOR_FEATURES: int = _BASE_WARMUP


def build_feature_matrix(
    candles: Sequence[Candle],
    feature_names: list[str] | None = None,
    label_type: str = "next_candle",
    label_horizon: int = 5,
    label_threshold: float = 0.003,
    # Legacy keyword-only params kept for backward compat
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
) -> tuple[list[list[float]], list[int]]:
    """Build feature matrix X and label vector y for model training.

    label_type options:
      - "next_candle": 1 if close[i+1] > close[i]
      - "forward_return": 1 if (close[i+horizon] - close[i]) / close[i] > threshold
    """
    ordered = sorted(candles, key=lambda c: c.open_time)
    names = feature_names if feature_names is not None else DEFAULT_FEATURE_NAMES
    X: list[list[float]] = []
    y: list[int] = []

    # We need at least horizon candles after each sample
    max_i = len(ordered) - label_horizon - 1

    for i in range(max_i + 1):
        window = ordered[: i + 1]
        features = build_feature_vector(window, names)
        if features is None:
            continue

        current_close = ordered[i].close_price
        if label_type == "forward_return":
            future_close = ordered[i + label_horizon].close_price
            ret = (
                float((future_close - current_close) / current_close)
                if current_close != Decimal("0")
                else 0.0
            )
            label = 1 if ret > label_threshold else 0
        else:  # next_candle
            label = 1 if ordered[i + 1].close_price > current_close else 0

        X.append(features)
        y.append(label)

    return X, y
