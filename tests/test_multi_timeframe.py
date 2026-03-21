"""Unit tests for the multi-timeframe trend alignment filter."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.multi_timeframe import is_htf_trend_aligned


def _make_signal(action: str) -> Signal:
    return Signal(
        action=action,
        reason="test",
        fast_value=Decimal("1"),
        slow_value=Decimal("0"),
    )


def _make_htf_candles(closes: list[float]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []
    for i, close in enumerate(closes):
        t = start + timedelta(hours=i * 4)
        price = Decimal(str(close))
        candles.append(
            Candle(
                open_time=t,
                close_time=t + timedelta(hours=4),
                open_price=price,
                high_price=price,
                low_price=price,
                close_price=price,
                volume=Decimal("1"),
            )
        )
    return candles


# ── Fail-open cases ───────────────────────────────────────────────────────────


def test_returns_true_when_no_htf_candles() -> None:
    assert is_htf_trend_aligned([], _make_signal("buy"), period=21) is True


def test_returns_true_when_fewer_candles_than_period() -> None:
    candles = _make_htf_candles([100.0] * 10)
    assert is_htf_trend_aligned(candles, _make_signal("buy"), period=21) is True


# ── Buy signal alignment ──────────────────────────────────────────────────────


def test_buy_allowed_when_price_above_htf_ema() -> None:
    # Strongly trending up: price well above any EMA
    candles = _make_htf_candles([100.0] * 20 + [200.0])
    assert is_htf_trend_aligned(candles, _make_signal("buy"), period=21) is True


def test_buy_blocked_when_price_below_htf_ema() -> None:
    # Strongly trending down: price well below any EMA
    candles = _make_htf_candles([200.0] * 20 + [50.0])
    assert is_htf_trend_aligned(candles, _make_signal("buy"), period=21) is False


# ── Sell signal alignment ─────────────────────────────────────────────────────


def test_sell_allowed_when_price_below_htf_ema() -> None:
    # Price collapses below EMA — bearish trend
    candles = _make_htf_candles([200.0] * 20 + [50.0])
    assert is_htf_trend_aligned(candles, _make_signal("sell"), period=21) is True


def test_sell_blocked_when_price_above_htf_ema() -> None:
    # Price surges above EMA — bullish trend, short is misaligned
    candles = _make_htf_candles([100.0] * 20 + [200.0])
    assert is_htf_trend_aligned(candles, _make_signal("sell"), period=21) is False


# ── Exact period boundary ─────────────────────────────────────────────────────


def test_exactly_period_candles_uses_filter() -> None:
    # Exactly period=5 candles available — filter should apply (not fail-open)
    candles = _make_htf_candles([100.0] * 4 + [200.0])
    # Price 200 is above EMA ~105 → buy should be allowed
    assert is_htf_trend_aligned(candles, _make_signal("buy"), period=5) is True


def test_one_fewer_than_period_fails_open() -> None:
    # 4 candles, period=5 → len < period → fail-open even though the last price is bearish
    candles = _make_htf_candles([200.0] * 3 + [50.0])
    assert is_htf_trend_aligned(candles, _make_signal("buy"), period=5) is True


# ── Unordered input ───────────────────────────────────────────────────────────


def test_handles_unsorted_input() -> None:
    candles = _make_htf_candles([100.0] * 20 + [200.0])
    # Reverse the list — should still produce the same result
    reversed_candles = list(reversed(candles))
    assert is_htf_trend_aligned(reversed_candles, _make_signal("buy"), period=21) is True
