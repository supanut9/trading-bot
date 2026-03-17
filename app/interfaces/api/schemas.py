from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AccountBalanceResponse(BaseModel):
    asset: str
    free: Decimal
    locked: Decimal


class StatusResponse(BaseModel):
    app: str
    environment: str
    execution_mode: str
    paper_trading: bool
    live_trading_enabled: bool
    exchange: str
    symbol: str
    timeframe: str
    database_url: str
    database_status: str
    account_balance_status: str
    account_balances: list[AccountBalanceResponse] = Field(default_factory=list)


class PositionResponse(BaseModel):
    exchange: str
    symbol: str
    side: str
    mode: str
    quantity: Decimal
    average_entry_price: Decimal | None
    realized_pnl: Decimal
    unrealized_pnl: Decimal

    model_config = ConfigDict(from_attributes=True)


class TradeResponse(BaseModel):
    id: int
    order_id: int | None
    exchange: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee_amount: Decimal | None
    fee_asset: str | None

    model_config = ConfigDict(from_attributes=True)


class CandleWriteRequest(BaseModel):
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal

    @field_validator("open_time", "close_time")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class CandleBatchIngestionRequest(BaseModel):
    exchange: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    candles: list[CandleWriteRequest] = Field(min_length=1)


class CandleBatchIngestionResponse(BaseModel):
    exchange: str
    symbol: str
    timeframe: str
    stored_count: int
    latest_open_time: datetime


class WorkerControlResponse(BaseModel):
    status: str
    detail: str
    signal_action: str | None = None
    client_order_id: str | None = None
    order_id: int | None = None
    trade_id: int | None = None
    position_quantity: Decimal | None = None
    notified: bool

    model_config = ConfigDict(from_attributes=True)


class BacktestControlResponse(BaseModel):
    status: str
    detail: str
    notified: bool
    candle_count: int
    required_candles: int
    starting_equity: Decimal | None = None
    ending_equity: Decimal | None = None
    realized_pnl: Decimal | None = None
    total_return_pct: Decimal | None = None
    max_drawdown_pct: Decimal | None = None
    total_trades: int | None = None
    winning_trades: int | None = None
    losing_trades: int | None = None

    model_config = ConfigDict(from_attributes=True)


class MarketSyncControlResponse(BaseModel):
    status: str
    detail: str
    fetched_count: int
    stored_count: int
    latest_open_time: datetime | None = None
    notified: bool

    model_config = ConfigDict(from_attributes=True)


class LiveReconcileControlResponse(BaseModel):
    status: str
    detail: str
    reconciled_count: int
    filled_count: int
    notified: bool

    model_config = ConfigDict(from_attributes=True)


class LiveCancelControlRequest(BaseModel):
    order_id: int | None = None
    client_order_id: str | None = None
    exchange_order_id: str | None = None


class LiveCancelControlResponse(BaseModel):
    status: str
    detail: str
    order_id: int | None
    client_order_id: str | None
    exchange_order_id: str | None
    order_status: str | None
    notified: bool

    model_config = ConfigDict(from_attributes=True)
