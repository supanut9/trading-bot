"""Feature engineering for ML-based strategies.

All functions are pure (no IO, no config). Features are returned as plain float
lists so they can be passed to any model without a Decimal → float conversion
scattered across callers.
"""

from collections.abc import Sequence
from decimal import Decimal

from app.domain.strategies.base import Candle
from app.domain.strategies.indicators import (
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_volume_sma,
)

# Feature names — order must match the feature vector returned by build_feature_vector
FEATURE_NAMES: list[str] = [
    "ema_diff_pct",
    "rsi",
    "macd_histogram",
    "atr_pct",
    "volume_ratio",
    "bb_position",
    "candle_body_pct",
    "high_low_pct",
]

# Minimum candles needed for a valid feature vector with default indicator periods.
# max(slow_ema=26, macd_slow+signal=35, rsi=14, bb=20, atr=14, vol_ma=20) + 2 warmup
MIN_CANDLES_FOR_FEATURES: int = 37


def build_feature_vector(
    candles: Sequence[Candle],
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
    """Compute the feature vector for the latest candle in the window.

    Returns None when there are not enough candles or a computation fails.
    Candles need not be pre-sorted — this function sorts by open_time internally.
    """
    ordered = sorted(candles, key=lambda c: c.open_time)
    min_needed = (
        max(
            slow_ema_period,
            macd_slow + macd_signal,
            rsi_period + 1,
            bb_period,
            atr_period + 1,
            volume_ma_period,
        )
        + 1
    )
    if len(ordered) < min_needed:
        return None

    closes = [c.close_price for c in ordered]
    highs = [c.high_price for c in ordered]
    lows = [c.low_price for c in ordered]
    volumes = [c.volume for c in ordered]
    latest = ordered[-1]

    try:
        # EMA diff pct
        fast_ema = calculate_ema(closes, fast_ema_period)[-1]
        slow_ema = calculate_ema(closes, slow_ema_period)[-1]
        close = latest.close_price
        ema_diff_pct = float((fast_ema - slow_ema) / close) if close != Decimal("0") else 0.0

        # RSI
        rsi_window = closes[-(rsi_period + 1) :]
        rsi = float(calculate_rsi(rsi_window, rsi_period))

        # MACD histogram
        macd_results = calculate_macd(closes, macd_fast, macd_slow, macd_signal)
        macd_histogram = float(macd_results[-1].histogram) if macd_results else 0.0

        # ATR pct
        atr_window_size = atr_period + 1
        atr = calculate_atr(
            highs[-atr_window_size:],
            lows[-atr_window_size:],
            closes[-atr_window_size:],
            atr_period,
        )
        atr_pct = float(atr / close) if close != Decimal("0") else 0.0

        # Volume ratio
        vol_sma = calculate_volume_sma(volumes[-volume_ma_period:], volume_ma_period)
        volume_ratio = float(latest.volume / vol_sma) if vol_sma != Decimal("0") else 1.0

        # Bollinger Band position  (0 = at lower, 1 = at upper, can exceed 0–1)
        bb = calculate_bollinger_bands(closes[-bb_period:], bb_period, Decimal("2"))
        band_range = bb.upper - bb.lower
        bb_position = float((close - bb.lower) / band_range) if band_range != Decimal("0") else 0.5

        # Candle body pct
        open_price = latest.open_price
        candle_body_pct = (
            float(abs(close - open_price) / open_price) if open_price != Decimal("0") else 0.0
        )

        # High-low range pct
        high_low_pct = (
            float((latest.high_price - latest.low_price) / open_price)
            if open_price != Decimal("0")
            else 0.0
        )

    except (ValueError, ZeroDivisionError, IndexError):
        return None

    return [
        ema_diff_pct,
        rsi,
        macd_histogram,
        atr_pct,
        volume_ratio,
        bb_position,
        candle_body_pct,
        high_low_pct,
    ]


def build_feature_matrix(
    candles: Sequence[Candle],
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

    Label: 1 if next candle's close > current candle's close, else 0.
    Rows without enough history or a valid next candle are skipped.

    Returns (X, y) where len(X) == len(y).
    """
    ordered = sorted(candles, key=lambda c: c.open_time)
    X: list[list[float]] = []
    y: list[int] = []

    kwargs = dict(
        fast_ema_period=fast_ema_period,
        slow_ema_period=slow_ema_period,
        rsi_period=rsi_period,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal=macd_signal,
        atr_period=atr_period,
        bb_period=bb_period,
        volume_ma_period=volume_ma_period,
    )

    for i in range(len(ordered) - 1):
        window = ordered[: i + 1]
        features = build_feature_vector(window, **kwargs)
        if features is None:
            continue
        label = 1 if ordered[i + 1].close_price > ordered[i].close_price else 0
        X.append(features)
        y.append(label)

    return X, y
