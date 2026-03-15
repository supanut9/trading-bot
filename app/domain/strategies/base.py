from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class Candle:
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal


@dataclass(frozen=True, slots=True)
class Signal:
    action: Literal["buy", "sell"]
    reason: str
    fast_value: Decimal
    slow_value: Decimal


class Strategy(Protocol):
    def evaluate(self, candles: Sequence[Candle]) -> Signal | None:
        """Evaluate the strategy and return a signal when conditions are met."""
