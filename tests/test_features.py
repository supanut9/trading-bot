"""Unit tests for ML feature engineering."""

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.strategies.base import Candle
from app.domain.strategies.features import (
    ALL_FEATURE_NAMES,
    DEFAULT_FEATURE_NAMES,
    FEATURE_GROUPS,
    FEATURE_NAMES,
    build_feature_matrix,
    build_feature_vector,
)


def _make_candles(n: int, base_price: float = 100.0, trend: float = 0.001) -> list[Candle]:
    """Make n candles with a gentle uptrend."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []
    price = base_price
    for i in range(n):
        t = start + timedelta(hours=i)
        p = Decimal(str(round(price, 2)))
        vol = Decimal("1000")
        candles.append(
            Candle(
                open_time=t,
                close_time=t + timedelta(hours=1),
                open_price=p,
                high_price=p * Decimal("1.002"),
                low_price=p * Decimal("0.998"),
                close_price=p * Decimal(str(1 + trend)),
                volume=vol,
            )
        )
        price *= 1 + trend
    return candles


# ── Backward-compat exports ──────────────────────────────────────────────────


def test_feature_names_backward_compat() -> None:
    """FEATURE_NAMES alias still points at the 8 default features."""
    assert FEATURE_NAMES is DEFAULT_FEATURE_NAMES
    assert len(FEATURE_NAMES) == 8


def test_all_feature_names_length() -> None:
    """ALL_FEATURE_NAMES should contain all features from FEATURE_GROUPS."""
    total = sum(len(v) for v in FEATURE_GROUPS.values())
    assert len(ALL_FEATURE_NAMES) == total


def test_feature_groups_cover_all_features() -> None:
    from_groups = [f for group in FEATURE_GROUPS.values() for f in group]
    assert sorted(from_groups) == sorted(ALL_FEATURE_NAMES)


# ── build_feature_vector — default (8-feature) mode ─────────────────────────


def test_returns_none_when_too_few_candles() -> None:
    candles = _make_candles(20)
    assert build_feature_vector(candles) is None


def test_returns_feature_vector_with_enough_candles() -> None:
    candles = _make_candles(50)
    result = build_feature_vector(candles)
    assert result is not None
    assert len(result) == 8
    assert all(isinstance(v, float) for v in result)


def test_feature_vector_no_nan_or_inf() -> None:
    candles = _make_candles(100)
    result = build_feature_vector(candles)
    assert result is not None
    for v in result:
        assert not math.isnan(v), f"NaN in features: {result}"
        assert not math.isinf(v), f"Inf in features: {result}"


def test_rsi_in_valid_range() -> None:
    candles = _make_candles(100)
    result = build_feature_vector(candles)
    assert result is not None
    rsi = result[DEFAULT_FEATURE_NAMES.index("rsi")]
    assert 0.0 <= rsi <= 100.0


def test_volume_ratio_positive() -> None:
    candles = _make_candles(100)
    result = build_feature_vector(candles)
    assert result is not None
    vol_ratio = result[DEFAULT_FEATURE_NAMES.index("volume_ratio")]
    assert vol_ratio > 0.0


def test_unsorted_candles_produce_same_result() -> None:
    candles = _make_candles(60)
    reversed_candles = list(reversed(candles))
    r1 = build_feature_vector(candles)
    r2 = build_feature_vector(reversed_candles)
    assert r1 is not None and r2 is not None
    assert r1 == pytest.approx(r2, rel=1e-6)


# ── build_feature_vector — selective feature_names ──────────────────────────


def test_selective_feature_names_returns_correct_length() -> None:
    candles = _make_candles(100)
    subset = ["rsi", "atr_pct", "volume_ratio"]
    result = build_feature_vector(candles, subset)
    assert result is not None
    assert len(result) == 3


def test_new_features_wick_upper_and_lower() -> None:
    candles = _make_candles(100)
    result = build_feature_vector(candles, ["wick_upper_pct", "wick_lower_pct"])
    assert result is not None
    assert len(result) == 2
    assert all(v >= 0.0 for v in result)


def test_bb_width_feature() -> None:
    candles = _make_candles(100)
    result = build_feature_vector(candles, ["bb_width"])
    assert result is not None
    assert result[0] >= 0.0


def test_stoch_k_in_range() -> None:
    candles = _make_candles(100)
    result = build_feature_vector(candles, ["stoch_k"])
    assert result is not None
    # Stochastic K is in [0, 100] range normally, but can be 0.0 if range == 0
    assert result[0] >= 0.0


def test_time_features_in_unit_circle() -> None:
    candles = _make_candles(60)
    result = build_feature_vector(candles, ["hour_sin", "hour_cos"])
    assert result is not None
    assert len(result) == 2
    # Both are in [-1, 1]
    assert -1.0 <= result[0] <= 1.0
    assert -1.0 <= result[1] <= 1.0


def test_lag_return_features() -> None:
    candles = _make_candles(60)
    result = build_feature_vector(candles, ["close_lag_1", "close_lag_2", "close_lag_3"])
    assert result is not None
    assert len(result) == 3


def test_adx_feature_needs_more_candles() -> None:
    # Should return None with only 20 candles for ADX
    candles = _make_candles(20)
    result = build_feature_vector(candles, ["adx"])
    assert result is None

    # Should succeed with enough candles
    candles = _make_candles(50)
    result = build_feature_vector(candles, ["adx"])
    assert result is not None
    assert result[0] >= 0.0


def test_roc_5_feature() -> None:
    candles = _make_candles(60)
    result = build_feature_vector(candles, ["roc_5"])
    assert result is not None
    assert len(result) == 1
    assert not math.isnan(result[0])


# ── build_feature_matrix ─────────────────────────────────────────────────────


def test_build_feature_matrix_returns_matching_lengths() -> None:
    candles = _make_candles(100)
    X, y = build_feature_matrix(candles)
    assert len(X) == len(y)
    assert len(X) > 0


def test_build_feature_matrix_labels_binary() -> None:
    candles = _make_candles(100)
    _, y = build_feature_matrix(candles)
    assert all(label in (0, 1) for label in y)


def test_build_feature_matrix_consistent_feature_count() -> None:
    candles = _make_candles(100)
    X, _ = build_feature_matrix(candles)
    assert all(len(row) == 8 for row in X)


def test_build_feature_matrix_next_candle_label() -> None:
    candles = _make_candles(100)
    X, y = build_feature_matrix(candles, label_type="next_candle")
    assert len(X) == len(y)
    assert len(X) > 0
    assert all(label in (0, 1) for label in y)


def test_build_feature_matrix_forward_return_label() -> None:
    candles = _make_candles(150)
    X, y = build_feature_matrix(
        candles,
        label_type="forward_return",
        label_horizon=5,
        label_threshold=0.003,
    )
    assert len(X) == len(y)
    assert len(X) > 0
    assert all(label in (0, 1) for label in y)


def test_build_feature_matrix_custom_feature_names() -> None:
    candles = _make_candles(100)
    subset = ["rsi", "atr_pct"]
    X, y = build_feature_matrix(candles, feature_names=subset)
    assert len(X) > 0
    assert all(len(row) == 2 for row in X)
