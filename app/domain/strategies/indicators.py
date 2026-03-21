from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal


def calculate_ema(prices: Sequence[Decimal], period: int) -> list[Decimal]:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(prices) < period:
        raise ValueError("not enough prices to calculate EMA")

    smoothing = Decimal("2") / Decimal(period + 1)
    seed = sum(prices[:period], start=Decimal("0")) / Decimal(period)
    values: list[Decimal] = [seed]
    previous = seed

    for price in prices[period:]:
        previous = (price - previous) * smoothing + previous
        values.append(previous)

    return values


def latest_ema(prices: Sequence[Decimal], period: int) -> Decimal:
    return calculate_ema(prices, period)[-1]


def calculate_sma(prices: Sequence[Decimal], period: int) -> list[Decimal]:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(prices) < period:
        raise ValueError("not enough prices to calculate SMA")
    result: list[Decimal] = []
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1 : i + 1]
        result.append(sum(window, start=Decimal("0")) / Decimal(period))
    return result


def calculate_rsi(prices: Sequence[Decimal], period: int) -> Decimal:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(prices) < period + 1:
        raise ValueError("not enough prices to calculate RSI")

    gains = Decimal("0")
    losses = Decimal("0")
    for previous, current in zip(prices[:-1], prices[1:], strict=False):
        change = current - previous
        if change > Decimal("0"):
            gains += change
        elif change < Decimal("0"):
            losses += abs(change)

    average_gain = gains / Decimal(period)
    average_loss = losses / Decimal(period)
    if average_loss == Decimal("0"):
        return Decimal("100")

    relative_strength = average_gain / average_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))


def calculate_volume_sma(volumes: Sequence[Decimal], period: int) -> Decimal:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(volumes) < period:
        raise ValueError("not enough volumes to calculate SMA")
    return sum(volumes[-period:], start=Decimal("0")) / Decimal(period)


def calculate_std_dev(prices: Sequence[Decimal], period: int) -> Decimal:
    """Population standard deviation of the last `period` prices."""
    if period <= 0:
        raise ValueError("period must be positive")
    if len(prices) < period:
        raise ValueError("not enough prices to calculate std dev")
    window = list(prices[-period:])
    mean = sum(window, start=Decimal("0")) / Decimal(period)
    variance = sum((p - mean) ** 2 for p in window) / Decimal(period)
    # integer square root via Newton–Raphson in Decimal
    return variance.sqrt()


@dataclass(frozen=True, slots=True)
class BollingerBands:
    upper: Decimal
    middle: Decimal
    lower: Decimal
    bandwidth: Decimal


def calculate_bollinger_bands(
    prices: Sequence[Decimal],
    period: int = 20,
    num_std_dev: Decimal = Decimal("2"),
) -> BollingerBands:
    """Compute Bollinger Bands using the last `period` closes."""
    if len(prices) < period:
        raise ValueError("not enough prices to calculate Bollinger Bands")
    sma_val = calculate_sma(prices, period)[-1]
    std = calculate_std_dev(prices, period)
    upper = sma_val + num_std_dev * std
    lower = sma_val - num_std_dev * std
    bandwidth = (upper - lower) / sma_val if sma_val != Decimal("0") else Decimal("0")
    return BollingerBands(upper=upper, middle=sma_val, lower=lower, bandwidth=bandwidth)


@dataclass(frozen=True, slots=True)
class MacdResult:
    macd_line: Decimal
    signal_line: Decimal
    histogram: Decimal


def calculate_macd(
    prices: Sequence[Decimal],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> list[MacdResult]:
    """Compute full MACD history. Returns one MacdResult per bar available
    after both EMAs are warmed up."""
    if fast_period <= 0 or slow_period <= 0 or signal_period <= 0:
        raise ValueError("all periods must be positive")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be smaller than slow_period")

    fast_emas = calculate_ema(prices, fast_period)
    slow_emas = calculate_ema(prices, slow_period)

    # Align: slow EMA is shorter by (slow_period - fast_period) bars
    offset = slow_period - fast_period
    macd_lines: list[Decimal] = [f - s for f, s in zip(fast_emas[offset:], slow_emas, strict=False)]

    if len(macd_lines) < signal_period:
        raise ValueError("not enough data to compute MACD signal line")

    signal_emas = calculate_ema(macd_lines, signal_period)
    # signal_emas has len = len(macd_lines) - signal_period + 1
    macd_offset = len(macd_lines) - len(signal_emas)

    results: list[MacdResult] = []
    for i, sig in enumerate(signal_emas):
        macd_val = macd_lines[macd_offset + i]
        results.append(
            MacdResult(
                macd_line=macd_val,
                signal_line=sig,
                histogram=macd_val - sig,
            )
        )
    return results


def calculate_atr(
    highs: Sequence[Decimal],
    lows: Sequence[Decimal],
    closes: Sequence[Decimal],
    period: int = 14,
) -> Decimal:
    """Wilder's Average True Range (simple average over `period` bars)."""
    if period <= 0:
        raise ValueError("period must be positive")
    if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
        raise ValueError("not enough bars to calculate ATR")

    true_ranges: list[Decimal] = []
    h_list = list(highs)
    l_list = list(lows)
    c_list = list(closes)
    for i in range(1, len(c_list)):
        hl = h_list[i] - l_list[i]
        hc = abs(h_list[i] - c_list[i - 1])
        lc = abs(l_list[i] - c_list[i - 1])
        true_ranges.append(max(hl, hc, lc))

    return sum(true_ranges[-period:], start=Decimal("0")) / Decimal(period)


def calculate_adx(
    highs: Sequence[Decimal],
    lows: Sequence[Decimal],
    closes: Sequence[Decimal],
    period: int = 14,
) -> Decimal:
    """Wilder's Average Directional Index (ADX).

    Returns the ADX value in the range [0, 100].
    Requires at least 2 * period + 1 bars.
    ADX > 25 generally indicates a trending market; < 20 indicates ranging.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    min_bars = 2 * period + 1
    if len(highs) < min_bars or len(lows) < min_bars or len(closes) < min_bars:
        raise ValueError(f"not enough bars to calculate ADX (need {min_bars})")

    h = list(highs)
    lo = list(lows)
    c = list(closes)
    n = len(c)

    # Compute raw +DM, -DM, TR for each bar
    plus_dm: list[Decimal] = []
    minus_dm: list[Decimal] = []
    true_ranges: list[Decimal] = []
    for i in range(1, n):
        up_move = h[i] - h[i - 1]
        down_move = lo[i - 1] - lo[i]
        plus_dm.append(up_move if up_move > down_move and up_move > Decimal("0") else Decimal("0"))
        minus_dm.append(
            down_move if down_move > up_move and down_move > Decimal("0") else Decimal("0")
        )
        hl = h[i] - lo[i]
        hc = abs(h[i] - c[i - 1])
        lc = abs(lo[i] - c[i - 1])
        true_ranges.append(max(hl, hc, lc))

    # Wilder smoothing: seed = sum of first `period` values
    smoothed_tr = sum(true_ranges[:period], start=Decimal("0"))
    smoothed_plus = sum(plus_dm[:period], start=Decimal("0"))
    smoothed_minus = sum(minus_dm[:period], start=Decimal("0"))

    dx_values: list[Decimal] = []
    period_d = Decimal(period)

    def _di(smoothed_dm: Decimal, smoothed_tr_val: Decimal) -> Decimal:
        if smoothed_tr_val == Decimal("0"):
            return Decimal("0")
        return (smoothed_dm / smoothed_tr_val) * Decimal("100")

    # Compute first DX from initial smoothed values
    plus_di = _di(smoothed_plus, smoothed_tr)
    minus_di = _di(smoothed_minus, smoothed_tr)
    di_sum = plus_di + minus_di
    dx_values.append(
        abs(plus_di - minus_di) / di_sum * Decimal("100")
        if di_sum != Decimal("0")
        else Decimal("0")
    )

    # Roll forward for remaining bars using Wilder smoothing
    for i in range(period, len(true_ranges)):
        smoothed_tr = smoothed_tr - smoothed_tr / period_d + true_ranges[i]
        smoothed_plus = smoothed_plus - smoothed_plus / period_d + plus_dm[i]
        smoothed_minus = smoothed_minus - smoothed_minus / period_d + minus_dm[i]
        plus_di = _di(smoothed_plus, smoothed_tr)
        minus_di = _di(smoothed_minus, smoothed_tr)
        di_sum = plus_di + minus_di
        dx_values.append(
            abs(plus_di - minus_di) / di_sum * Decimal("100")
            if di_sum != Decimal("0")
            else Decimal("0")
        )

    # ADX = Wilder smoothed average of DX over `period` values
    adx = sum(dx_values[:period], start=Decimal("0")) / period_d
    for dx in dx_values[period:]:
        adx = (adx * (period_d - Decimal("1")) + dx) / period_d
    return adx
