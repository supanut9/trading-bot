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


@dataclass(frozen=True, slots=True)
class ExchangeOrderRequest:
    symbol: str
    side: str
    quantity: Decimal
    order_type: str = "MARKET"
    validate_only: bool = True
    client_order_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExchangeOrderSubmission:
    status: str
    client_order_id: str | None
    exchange_order_id: str | None
    response_payload: dict[str, object]


class MarketDataExchangeClient(Protocol):
    name: str

    def fetch_closed_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> Sequence[ExchangeCandle]: ...


class LiveOrderExchangeClient(Protocol):
    name: str

    def submit_order(self, request: ExchangeOrderRequest) -> ExchangeOrderSubmission: ...
