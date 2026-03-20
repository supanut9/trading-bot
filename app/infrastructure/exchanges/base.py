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
class ExchangeTickerPrice:
    symbol: str
    price: Decimal


@dataclass(frozen=True, slots=True)
class ExchangeOrderRequest:
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal | None = None
    order_type: str = "MARKET"
    validate_only: bool = True
    client_order_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExchangeOrderSubmission:
    status: str
    client_order_id: str | None
    exchange_order_id: str | None
    response_payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class ExchangeOrderStatus:
    status: str
    client_order_id: str | None
    exchange_order_id: str | None
    executed_quantity: Decimal
    average_fill_price: Decimal | None
    response_payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class ExchangeOrderCancellation:
    status: str
    client_order_id: str | None
    exchange_order_id: str | None
    response_payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class ExchangeAssetBalance:
    asset: str
    free: Decimal
    locked: Decimal


@dataclass(frozen=True, slots=True)
class ExchangeSymbolRules:
    exchange: str
    symbol: str
    min_qty: Decimal
    max_qty: Decimal
    step_size: Decimal
    min_notional: Decimal
    tick_size: Decimal


class MarketDataExchangeClient(Protocol):
    name: str

    def fetch_closed_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> Sequence[ExchangeCandle]: ...

    def fetch_latest_price(self, *, symbol: str) -> ExchangeTickerPrice: ...

    def fetch_symbol_rules(self, *, symbol: str) -> ExchangeSymbolRules: ...


class LiveOrderExchangeClient(Protocol):
    name: str

    def submit_order(self, request: ExchangeOrderRequest) -> ExchangeOrderSubmission: ...

    def fetch_account_balances(self) -> Sequence[ExchangeAssetBalance]: ...

    def cancel_order(
        self,
        *,
        symbol: str,
        client_order_id: str | None = None,
        exchange_order_id: str | None = None,
    ) -> ExchangeOrderCancellation: ...

    def fetch_order_status(
        self,
        *,
        symbol: str,
        client_order_id: str | None = None,
        exchange_order_id: str | None = None,
    ) -> ExchangeOrderStatus: ...
