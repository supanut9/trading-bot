from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="local", alias="APP_ENV")
    app_name: str = Field(default="trading-bot", alias="APP_NAME")
    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    database_url: str = Field(default="sqlite:///./trading_bot.db", alias="DATABASE_URL")
    paper_trading: bool = Field(default=True, alias="PAPER_TRADING")
    live_trading_enabled: bool = Field(default=False, alias="LIVE_TRADING_ENABLED")
    exchange_name: str = Field(default="binance", alias="EXCHANGE_NAME")
    exchange_api_base_url: str = Field(
        default="https://api.binance.com",
        alias="EXCHANGE_API_BASE_URL",
    )
    exchange_api_key: str | None = Field(default=None, alias="EXCHANGE_API_KEY")
    exchange_api_secret: str | None = Field(default=None, alias="EXCHANGE_API_SECRET")
    exchange_request_timeout_seconds: int = Field(
        default=10,
        alias="EXCHANGE_REQUEST_TIMEOUT_SECONDS",
    )
    default_symbol: str = Field(default="BTC/USDT", alias="DEFAULT_SYMBOL")
    default_timeframe: str = Field(default="1h", alias="DEFAULT_TIMEFRAME")
    strategy_fast_period: int = Field(default=20, alias="STRATEGY_FAST_PERIOD")
    strategy_slow_period: int = Field(default=50, alias="STRATEGY_SLOW_PERIOD")
    paper_account_equity: float = Field(default=10000.0, alias="PAPER_ACCOUNT_EQUITY")
    risk_per_trade_pct: float = Field(default=0.01, alias="RISK_PER_TRADE_PCT")
    max_open_positions: int = Field(default=1, alias="MAX_OPEN_POSITIONS")
    max_daily_loss_pct: float = Field(default=0.03, alias="MAX_DAILY_LOSS_PCT")
    live_trading_halted: bool = Field(default=False, alias="LIVE_TRADING_HALTED")
    live_max_order_notional: Decimal | None = Field(
        default=None,
        alias="LIVE_MAX_ORDER_NOTIONAL",
    )
    live_max_position_quantity: Decimal | None = Field(
        default=None,
        alias="LIVE_MAX_POSITION_QUANTITY",
    )
    worker_poll_interval_seconds: int = Field(default=60, alias="WORKER_POLL_INTERVAL_SECONDS")
    worker_run_once: bool = Field(default=True, alias="WORKER_RUN_ONCE")
    market_data_sync_enabled: bool = Field(default=False, alias="MARKET_DATA_SYNC_ENABLED")
    market_data_sync_limit: int = Field(default=100, alias="MARKET_DATA_SYNC_LIMIT")
    market_data_sync_timeout_seconds: int = Field(
        default=10,
        alias="MARKET_DATA_SYNC_TIMEOUT_SECONDS",
    )
    market_data_api_base_url: str = Field(
        default="https://api.binance.com",
        alias="MARKET_DATA_API_BASE_URL",
    )
    backtest_schedule_enabled: bool = Field(
        default=False,
        alias="BACKTEST_SCHEDULE_ENABLED",
    )
    backtest_schedule_interval_seconds: int = Field(
        default=3600,
        alias="BACKTEST_SCHEDULE_INTERVAL_SECONDS",
    )
    live_reconcile_schedule_enabled: bool = Field(
        default=False,
        alias="LIVE_RECONCILE_SCHEDULE_ENABLED",
    )
    live_reconcile_schedule_interval_seconds: int = Field(
        default=300,
        alias="LIVE_RECONCILE_SCHEDULE_INTERVAL_SECONDS",
    )
    startup_state_sync_enabled: bool = Field(
        default=True,
        alias="STARTUP_STATE_SYNC_ENABLED",
    )
    stale_live_order_threshold_minutes: int = Field(
        default=120,
        alias="STALE_LIVE_ORDER_THRESHOLD_MINUTES",
    )
    notification_channel: Literal["none", "log", "webhook"] = Field(
        default="none",
        alias="NOTIFICATION_CHANNEL",
    )
    notification_webhook_url: str | None = Field(
        default=None,
        alias="NOTIFICATION_WEBHOOK_URL",
    )
    notification_timeout_seconds: int = Field(
        default=5,
        alias="NOTIFICATION_TIMEOUT_SECONDS",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_execution_mode(self) -> "Settings":
        if self.paper_trading and self.live_trading_enabled:
            raise ValueError("PAPER_TRADING and LIVE_TRADING_ENABLED cannot both be true")
        if not self.paper_trading and not self.live_trading_enabled:
            raise ValueError("LIVE_TRADING_ENABLED must be true when PAPER_TRADING is false")
        if self.live_trading_enabled and (
            not self.exchange_api_key or not self.exchange_api_secret
        ):
            raise ValueError(
                "EXCHANGE_API_KEY and EXCHANGE_API_SECRET are required when live trading is enabled"
            )
        if self.live_max_order_notional is not None and self.live_max_order_notional <= Decimal(
            "0"
        ):
            raise ValueError("LIVE_MAX_ORDER_NOTIONAL must be positive when provided")
        if (
            self.live_max_position_quantity is not None
            and self.live_max_position_quantity <= Decimal("0")
        ):
            raise ValueError("LIVE_MAX_POSITION_QUANTITY must be positive when provided")
        return self

    @property
    def execution_mode(self) -> Literal["paper", "live"]:
        return "paper" if self.paper_trading else "live"


@lru_cache
def get_settings() -> Settings:
    return Settings()
