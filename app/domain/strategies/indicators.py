from collections.abc import Sequence
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
