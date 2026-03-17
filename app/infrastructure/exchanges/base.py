from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExchangeCandle:
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal


class MarketDataExchangeClient(Protocol):
    name: str

    def fetch_closed_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> Sequence[ExchangeCandle]: ...
