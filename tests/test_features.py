"""Unit tests for XGBoost feature engineering."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.strategies.base import Candle
from app.domain.strategies.features import (
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


def test_feature_names_length() -> None:
    assert len(FEATURE_NAMES) == 8


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
    import math

    for v in result:
        assert not math.isnan(v), f"NaN in features: {result}"
        assert not math.isinf(v), f"Inf in features: {result}"


def test_rsi_in_valid_range() -> None:
    candles = _make_candles(100)
    result = build_feature_vector(candles)
    assert result is not None
    rsi = result[FEATURE_NAMES.index("rsi")]
    assert 0.0 <= rsi <= 100.0


def test_volume_ratio_positive() -> None:
    candles = _make_candles(100)
    result = build_feature_vector(candles)
    assert result is not None
    vol_ratio = result[FEATURE_NAMES.index("volume_ratio")]
    assert vol_ratio > 0.0


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


def test_unsorted_candles_produce_same_result() -> None:
    candles = _make_candles(60)
    reversed_candles = list(reversed(candles))
    r1 = build_feature_vector(candles)
    r2 = build_feature_vector(reversed_candles)
    assert r1 is not None and r2 is not None
    assert r1 == pytest.approx(r2, rel=1e-6)
