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
    frontend_origins: str = Field(
        default="http://127.0.0.1:3000,http://localhost:3000",
        alias="FRONTEND_ORIGINS",
    )
    database_url: str = Field(default="sqlite:///./trading_bot.db", alias="DATABASE_URL")
    paper_trading: bool = Field(default=True, alias="PAPER_TRADING")
    live_trading_enabled: bool = Field(default=False, alias="LIVE_TRADING_ENABLED")
    exchange_name: str = Field(default="binance", alias="EXCHANGE_NAME")
    trading_mode: Literal["SPOT", "FUTURES"] = Field(default="SPOT", alias="TRADING_MODE")
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
    stop_loss_atr_multiplier: float = Field(default=2.0, alias="STOP_LOSS_ATR_MULTIPLIER")
    stop_loss_atr_period: int = Field(default=14, alias="STOP_LOSS_ATR_PERIOD")
    trailing_stop_enabled: bool = Field(default=True, alias="TRAILING_STOP_ENABLED")
    live_trading_halted: bool = Field(default=False, alias="LIVE_TRADING_HALTED")
    live_max_order_notional: Decimal | None = Field(
        default=None,
        alias="LIVE_MAX_ORDER_NOTIONAL",
    )
    live_max_position_quantity: Decimal | None = Field(
        default=None,
        alias="LIVE_MAX_POSITION_QUANTITY",
    )
    live_max_daily_loss_notional: Decimal | None = Field(
        default=None,
        alias="LIVE_MAX_DAILY_LOSS_NOTIONAL",
    )
    live_max_weekly_loss_notional: Decimal | None = Field(
        default=None,
        alias="LIVE_MAX_WEEKLY_LOSS_NOTIONAL",
    )
    live_max_concurrent_exposure_notional: Decimal | None = Field(
        default=None,
        alias="LIVE_MAX_CONCURRENT_EXPOSURE_NOTIONAL",
    )
    live_consecutive_loss_auto_halt_threshold: int | None = Field(
        default=None,
        alias="LIVE_CONSECUTIVE_LOSS_AUTO_HALT_THRESHOLD",
    )
    live_repeated_reject_auto_halt_threshold: int | None = Field(
        default=None,
        alias="LIVE_REPEATED_REJECT_AUTO_HALT_THRESHOLD",
    )
    live_fee_pct: float = Field(default=0.001, alias="LIVE_FEE_PCT")
    live_expected_profit_bps: int = Field(default=30, alias="LIVE_EXPECTED_PROFIT_BPS")
    live_order_routing_mode: Literal["market", "limit"] = Field(
        default="market", alias="LIVE_ORDER_ROUTING_MODE"
    )
    live_limit_order_offset_bps: int = Field(default=1, alias="LIVE_LIMIT_ORDER_OFFSET_BPS")
    live_limit_order_timeout_seconds: int = Field(
        default=10, alias="LIVE_LIMIT_ORDER_TIMEOUT_SECONDS"
    )
    live_order_validate_only: bool = Field(default=False, alias="LIVE_ORDER_VALIDATE_ONLY")

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
    strategy_rsi_filter_enabled: bool = Field(default=False, alias="STRATEGY_RSI_FILTER_ENABLED")
    strategy_rsi_period: int = Field(default=14, alias="STRATEGY_RSI_PERIOD")
    strategy_rsi_overbought: float = Field(default=70.0, alias="STRATEGY_RSI_OVERBOUGHT")
    strategy_rsi_oversold: float = Field(default=30.0, alias="STRATEGY_RSI_OVERSOLD")
    strategy_volume_filter_enabled: bool = Field(
        default=False, alias="STRATEGY_VOLUME_FILTER_ENABLED"
    )
    strategy_volume_ma_period: int = Field(default=20, alias="STRATEGY_VOLUME_MA_PERIOD")
    strategy_adx_filter_enabled: bool = Field(default=False, alias="STRATEGY_ADX_FILTER_ENABLED")
    strategy_adx_period: int = Field(default=14, alias="STRATEGY_ADX_PERIOD")
    strategy_adx_threshold: float = Field(default=25.0, alias="STRATEGY_ADX_THRESHOLD")
    volatility_sizing_enabled: bool = Field(default=False, alias="VOLATILITY_SIZING_ENABLED")
    volatility_sizing_atr_period: int = Field(default=14, alias="VOLATILITY_SIZING_ATR_PERIOD")
    backtest_slippage_pct: float = Field(default=0.0005, alias="BACKTEST_SLIPPAGE_PCT")
    backtest_fee_pct: float = Field(default=0.001, alias="BACKTEST_FEE_PCT")
    backtest_overfitting_threshold_pct: float = Field(
        default=35.0, alias="BACKTEST_OVERFITTING_THRESHOLD_PCT"
    )
    shadow_trading_enabled: bool = Field(default=False, alias="SHADOW_TRADING_ENABLED")
    shadow_slippage_pct: float = Field(default=0.0005, alias="SHADOW_SLIPPAGE_PCT")
    shadow_fee_pct: float = Field(default=0.001, alias="SHADOW_FEE_PCT")
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
    live_consecutive_exchange_error_auto_halt_threshold: int | None = Field(
        default=None,
        alias="LIVE_CONSECUTIVE_EXCHANGE_ERROR_AUTO_HALT_THRESHOLD",
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
        if self.shadow_trading_enabled and self.live_trading_enabled:
            raise ValueError("SHADOW_TRADING_ENABLED and LIVE_TRADING_ENABLED cannot both be true")
        if self.paper_trading and self.live_trading_enabled:
            raise ValueError("PAPER_TRADING and LIVE_TRADING_ENABLED cannot both be true")
        if (
            not self.paper_trading
            and not self.live_trading_enabled
            and not self.shadow_trading_enabled
        ):
            raise ValueError("LIVE_TRADING_ENABLED must be true when PAPER_TRADING is false")
        if self.live_trading_enabled and (
            not self.exchange_api_key or not self.exchange_api_secret
        ):
            raise ValueError(
                "EXCHANGE_API_KEY and EXCHANGE_API_SECRET are required when live trading is enabled"
            )

        if self.app_env.lower() not in {"local", "production", "staging", "test"}:
            raise ValueError(f"invalid APP_ENV: {self.app_env}")

        if not (0 < self.api_port < 65536):
            raise ValueError(f"invalid API_PORT: {self.api_port}")

        if self.log_level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"invalid LOG_LEVEL: {self.log_level}")

        if self.app_env.lower() != "local" and self.database_url.startswith("sqlite"):
            raise ValueError("non-local environment requires PostgreSQL-compatible DATABASE_URL")

        limit_order_notional = self.live_max_order_notional
        if limit_order_notional is not None and limit_order_notional <= Decimal("0"):
            raise ValueError("LIVE_MAX_ORDER_NOTIONAL must be positive when provided")

        limit_pos_qty = self.live_max_position_quantity
        if limit_pos_qty is not None and limit_pos_qty <= Decimal("0"):
            raise ValueError("LIVE_MAX_POSITION_QUANTITY must be positive when provided")

        limit_daily_notional = self.live_max_daily_loss_notional
        if limit_daily_notional is not None and limit_daily_notional <= Decimal("0"):
            raise ValueError("LIVE_MAX_DAILY_LOSS_NOTIONAL must be positive when provided")

        limit_weekly_notional = self.live_max_weekly_loss_notional
        if limit_weekly_notional is not None and limit_weekly_notional <= Decimal("0"):
            raise ValueError("LIVE_MAX_WEEKLY_LOSS_NOTIONAL must be positive when provided")

        limit_exposure = self.live_max_concurrent_exposure_notional
        if limit_exposure is not None and limit_exposure <= Decimal("0"):
            raise ValueError("LIVE_MAX_CONCURRENT_EXPOSURE_NOTIONAL must be positive when provided")

        limit_consec_loss = self.live_consecutive_loss_auto_halt_threshold
        if limit_consec_loss is not None and limit_consec_loss <= 0:
            raise ValueError(
                "LIVE_CONSECUTIVE_LOSS_AUTO_HALT_THRESHOLD must be positive when provided"
            )

        limit_rejects = self.live_repeated_reject_auto_halt_threshold
        if limit_rejects is not None and limit_rejects <= 0:
            raise ValueError(
                "LIVE_REPEATED_REJECT_AUTO_HALT_THRESHOLD must be positive when provided"
            )
        if self.live_limit_order_offset_bps < 0:
            raise ValueError("LIVE_LIMIT_ORDER_OFFSET_BPS must be non-negative")
        if self.live_limit_order_timeout_seconds <= 0:
            raise ValueError("LIVE_LIMIT_ORDER_TIMEOUT_SECONDS must be positive")
        if self.live_fee_pct < 0:
            raise ValueError("LIVE_FEE_PCT must be non-negative")
        if self.live_expected_profit_bps < 0:
            raise ValueError("LIVE_EXPECTED_PROFIT_BPS must be non-negative")

        return self

    @property
    def execution_mode(self) -> Literal["paper", "live", "shadow"]:
        if self.shadow_trading_enabled:
            return "shadow"
        return "paper" if self.paper_trading else "live"

    @property
    def allowed_frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
