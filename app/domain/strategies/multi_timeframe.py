from collections.abc import Sequence

from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.indicators import latest_ema


def is_htf_trend_aligned(
    htf_candles: Sequence[Candle],
    signal: Signal,
    period: int,
) -> bool:
    """Return True if the HTF EMA trend aligns with the signal direction.

    Bullish (buy allowed): latest HTF close > slow EMA(period) on HTF.
    Bearish (sell allowed): latest HTF close < slow EMA(period) on HTF.

    Fails open (returns True) when there are not enough HTF candles to
    compute the EMA — consistent with how other indicator filters behave.
    """
    if len(htf_candles) < period:
        return True

    sorted_candles = sorted(htf_candles, key=lambda c: c.open_time)
    closes = [c.close_price for c in sorted_candles]
    htf_ema = latest_ema(closes, period)
    latest_close = sorted_candles[-1].close_price

    if signal.action == "buy":
        return latest_close > htf_ema
    if signal.action == "sell":
        return latest_close < htf_ema
    return True
