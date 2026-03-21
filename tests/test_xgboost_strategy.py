"""Unit tests for XGBoostSignalStrategy."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.domain.strategies.base import Candle
from app.domain.strategies.xgboost_signal import XGBoostSignalStrategy


def _make_candles(n: int, base_price: float = 100.0, trend: float = 0.001) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []
    price = base_price
    for i in range(n):
        t = start + timedelta(hours=i)
        p = Decimal(str(round(price, 2)))
        candles.append(
            Candle(
                open_time=t,
                close_time=t + timedelta(hours=1),
                open_price=p,
                high_price=p * Decimal("1.002"),
                low_price=p * Decimal("0.998"),
                close_price=p * Decimal(str(1 + trend)),
                volume=Decimal("1000"),
            )
        )
        price *= 1 + trend
    return candles


def _mock_model(up_prob: float) -> MagicMock:
    model = MagicMock()
    model.predict_proba.return_value = [[1 - up_prob, up_prob]]
    return model


def test_raises_when_model_is_none() -> None:
    with pytest.raises(ValueError, match="pre-loaded model"):
        XGBoostSignalStrategy(model=None)


def test_raises_when_buy_threshold_too_low() -> None:
    with pytest.raises(ValueError):
        XGBoostSignalStrategy(model=_mock_model(0.6), buy_threshold=Decimal("0.5"))


def test_raises_when_sell_threshold_too_high() -> None:
    with pytest.raises(ValueError):
        XGBoostSignalStrategy(model=_mock_model(0.4), sell_threshold=Decimal("0.5"))


def test_returns_none_when_too_few_candles() -> None:
    strategy = XGBoostSignalStrategy(model=_mock_model(0.9))
    candles = _make_candles(20)
    assert strategy.evaluate(candles) is None


def test_returns_buy_signal_when_high_up_probability() -> None:
    strategy = XGBoostSignalStrategy(model=_mock_model(0.8))
    candles = _make_candles(60)
    result = strategy.evaluate(candles)
    assert result is not None
    assert result.action == "buy"
    assert "XGBoost" in result.reason


def test_returns_sell_signal_when_low_up_probability() -> None:
    strategy = XGBoostSignalStrategy(model=_mock_model(0.1))
    candles = _make_candles(60)
    result = strategy.evaluate(candles)
    assert result is not None
    assert result.action == "sell"


def test_returns_none_when_probability_in_neutral_zone() -> None:
    strategy = XGBoostSignalStrategy(model=_mock_model(0.5))
    candles = _make_candles(60)
    result = strategy.evaluate(candles)
    assert result is None


def test_handles_model_exception_gracefully() -> None:
    model = MagicMock()
    model.predict_proba.side_effect = RuntimeError("model error")
    strategy = XGBoostSignalStrategy(model=model)
    candles = _make_candles(60)
    # Should return None, not raise
    assert strategy.evaluate(candles) is None


def test_minimum_candles_returns_positive_int() -> None:
    strategy = XGBoostSignalStrategy(model=_mock_model(0.6))
    assert strategy.minimum_candles() > 0
    assert isinstance(strategy.minimum_candles(), int)


def test_unsorted_candles_produce_same_result() -> None:
    model = _mock_model(0.8)
    strategy = XGBoostSignalStrategy(model=model)
    candles = _make_candles(60)
    reversed_candles = list(reversed(candles))
    r1 = strategy.evaluate(candles)
    r2 = strategy.evaluate(reversed_candles)
    # Both calls use the same mock; results should match
    assert (r1 is None) == (r2 is None)
    if r1 and r2:
        assert r1.action == r2.action
