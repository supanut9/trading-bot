from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


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
