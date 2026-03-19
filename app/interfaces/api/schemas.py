from datetime import UTC, date, datetime
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
    live_trading_halted: bool
    live_safety_status: str
    live_max_order_notional: Decimal | None = None
    live_max_position_quantity: Decimal | None = None
    exchange: str
    strategy_name: str
    symbol: str
    timeframe: str
    fast_period: int
    slow_period: int
    operator_config_source: str
    database_url: str
    database_status: str
    latest_price_status: str
    latest_price: Decimal | None = None
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


class PerformanceSummaryResponse(BaseModel):
    mode: str
    total_realized_pnl: Decimal
    total_unrealized_pnl: Decimal
    total_fees: Decimal
    net_pnl: Decimal
    trade_count: int
    closed_trade_count: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal | None = None
    average_win: Decimal | None = None
    average_loss: Decimal | None = None
    profit_factor: Decimal | None = None
    expectancy: Decimal | None = None
    max_drawdown: Decimal
    open_position_count: int

    model_config = ConfigDict(from_attributes=True)


class PerformanceEquityCurvePointResponse(BaseModel):
    mode: str
    recorded_at: datetime
    net_pnl: Decimal
    drawdown: Decimal

    model_config = ConfigDict(from_attributes=True)


class PerformanceDailyRowResponse(BaseModel):
    mode: str
    trade_date: date
    trade_count: int
    closed_trade_count: int
    winning_trades: int
    losing_trades: int
    realized_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal

    model_config = ConfigDict(from_attributes=True)


class PerformanceAnalyticsResponse(BaseModel):
    summaries: list[PerformanceSummaryResponse]
    equity_curve: list[PerformanceEquityCurvePointResponse]
    daily_rows: list[PerformanceDailyRowResponse]

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


class DemoScenarioLoadResponse(BaseModel):
    scenario: str
    detail: str
    exchange: str
    symbol: str
    timeframe: str
    candle_count: int
    stored_count: int
    latest_open_time: datetime
    expected_signal_action: str | None = None


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
    strategy_name: str
    exchange: str
    symbol: str
    timeframe: str
    fast_period: int
    slow_period: int
    starting_equity_input: Decimal
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
    executions: list["BacktestExecutionResponse"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class BacktestExecutionResponse(BaseModel):
    action: str
    price: Decimal
    quantity: Decimal
    realized_pnl: Decimal
    reason: str

    model_config = ConfigDict(from_attributes=True)


class BacktestControlRequest(BaseModel):
    strategy_name: str = "ema_crossover"
    exchange: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    fast_period: int | None = None
    slow_period: int | None = None
    starting_equity: Decimal | None = None


class OperatorConfigResponse(BaseModel):
    status: str
    detail: str
    strategy_name: str
    exchange: str
    symbol: str
    timeframe: str
    fast_period: int
    slow_period: int
    source: str
    changed: bool = False
    notified: bool = False

    model_config = ConfigDict(from_attributes=True)


class OperatorConfigRequest(BaseModel):
    strategy_name: str = "ema_crossover"
    symbol: str
    timeframe: str
    fast_period: int
    slow_period: int


class MarketSyncControlResponse(BaseModel):
    status: str
    detail: str
    symbol: str
    timeframe: str
    limit: int
    backfill: bool = False
    fetched_count: int
    stored_count: int
    latest_open_time: datetime | None = None
    notified: bool

    model_config = ConfigDict(from_attributes=True)


class MarketSyncControlRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=1000)
    backfill: bool = False


class LiveReconcileControlResponse(BaseModel):
    status: str
    detail: str
    reconciled_count: int
    filled_count: int
    review_required_count: int
    notified: bool

    model_config = ConfigDict(from_attributes=True)


class LiveHaltControlRequest(BaseModel):
    halted: bool


class LiveHaltControlResponse(BaseModel):
    status: str
    detail: str
    live_trading_halted: bool
    changed: bool
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
