from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.strategies.base import Candle
from app.domain.strategies.breakout_atr import BreakoutAtrStrategy
from app.domain.strategies.macd_crossover import MacdCrossoverStrategy
from app.domain.strategies.mean_reversion_bollinger import MeanReversionBollingerStrategy
from app.domain.strategies.rsi_momentum import RsiMomentumStrategy


def build_candles(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for index, close in enumerate(closes):
        open_time = start + timedelta(hours=index)
        high = highs[index] if highs else close
        low = lows[index] if lows else close
        v = volumes[index] if volumes else 1.0
        candles.append(
            Candle(
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open_price=Decimal(str(close)),
                high_price=Decimal(str(high)),
                low_price=Decimal(str(low)),
                close_price=Decimal(str(close)),
                volume=Decimal(str(v)),
            )
        )
    return candles


# --- MeanReversionBollingerStrategy Tests ---


def test_bollinger_buy_signal() -> None:
    strategy = MeanReversionBollingerStrategy(
        bb_period=10, rsi_period=10, rsi_oversold=Decimal("40")
    )
    # Price drop decisively below BB lower band while RSI is oversold
    # Warm up with flat prices to consolidate bands
    closes = [100] * 20 + [70]  # Instant crash
    candles = build_candles(closes)

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "buy"
    assert "touched lower BB" in signal.reason


def test_bollinger_sell_signal_at_upper_band() -> None:
    strategy = MeanReversionBollingerStrategy(
        bb_period=10, rsi_period=10, rsi_overbought=Decimal("100")
    )
    # Price surge decisively above BB upper band
    closes = [100] * 20 + [130]  # Instant moon
    candles = build_candles(closes)

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "sell"
    assert "reached upper BB" in signal.reason


def test_bollinger_sell_signal_rsi_overbought() -> None:
    strategy = MeanReversionBollingerStrategy(
        bb_period=20, rsi_period=10, rsi_overbought=Decimal("60")
    )
    # Prices rising steadily → RSI becomes overbought
    # RSI for [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110] is high
    closes = [100] * 20 + [101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
    candles = build_candles(closes)

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "sell"
    assert "RSI" in signal.reason


# --- MacdCrossoverStrategy Tests ---


def test_macd_buy_signal() -> None:
    strategy = MacdCrossoverStrategy(fast_period=5, slow_period=10, signal_period=5)
    # Warm up: constant prices. Trend down to establish state. Reverse sharply to cause cross.
    # Data generated via crossover-search script.
    closes = [
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        99.0,
        98.0,
        97.0,
        96.0,
        95.0,
        94.0,
        93.0,
        92.0,
        91.0,
        90.0,
        89.0,
        88.0,
        87.0,
        86.0,
        85.0,
        90.0,
    ]
    candles = build_candles(closes)

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "buy"
    assert "MACD" in signal.reason


def test_macd_sell_signal() -> None:
    strategy = MacdCrossoverStrategy(fast_period=5, slow_period=10, signal_period=5)
    # Data generated via crossover-search script.
    closes = [
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        101.0,
        102.0,
        103.0,
        104.0,
        105.0,
        106.0,
        107.0,
        108.0,
        109.0,
        110.0,
        111.0,
        112.0,
        113.0,
        114.0,
        115.0,
        110.0,
    ]
    candles = build_candles(closes)

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "sell"
    assert "MACD" in signal.reason


# --- RsiMomentumStrategy Tests ---


def test_rsi_momentum_buy_signal() -> None:
    strategy = RsiMomentumStrategy(rsi_period=10, midline=Decimal("50"))
    # Data generated via crossover-search script.
    closes = [
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        95.0,
        90.0,
        85.0,
        80.0,
        75.0,
        70.0,
        65.0,
        60.0,
        55.0,
        50.0,
        60.0,
        70.0,
        80.0,
        90.0,
    ]
    candles = build_candles(closes)

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "buy"
    assert "RSI crossed above midline" in signal.reason


def test_rsi_momentum_sell_signal() -> None:
    strategy = RsiMomentumStrategy(rsi_period=10, midline=Decimal("50"))
    # Data generated via crossover-search script.
    closes = [
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        110.0,
        120.0,
        130.0,
        140.0,
        150.0,
        160.0,
        170.0,
        180.0,
        190.0,
        200.0,
        185.0,
        170.0,
        155.0,
        140.0,
    ]
    candles = build_candles(closes)

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "sell"
    assert "RSI crossed below midline" in signal.reason


# --- BreakoutAtrStrategy Tests ---


def test_breakout_atr_buy_signal() -> None:
    strategy = BreakoutAtrStrategy(
        breakout_period=5, atr_period=5, atr_breakout_multiplier=Decimal("0.1")
    )
    # Quiet period then big breakout
    closes = [100, 100, 100, 100, 100, 100, 110]
    highs = [101, 101, 101, 101, 101, 101, 111]
    lows = [99, 99, 99, 99, 99, 99, 109]
    candles = build_candles(closes, highs=highs, lows=lows)

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "buy"
    assert "broke above" in signal.reason


def test_breakout_atr_sell_signal_stop_loss() -> None:
    strategy = BreakoutAtrStrategy(
        breakout_period=5, atr_period=5, atr_stop_multiplier=Decimal("0.1")
    )
    # Trend reversal hitting stop loss
    closes = [100, 105, 110, 115, 120, 125, 100]
    highs = [101, 106, 111, 116, 121, 126, 101]
    lows = [99, 104, 109, 114, 119, 124, 99]
    candles = build_candles(closes, highs=highs, lows=lows)

    signal = strategy.evaluate(candles)

    assert signal is not None
    assert signal.action == "sell"
    assert "fell below" in signal.reason
