from functools import lru_cache

from pydantic import Field
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
    default_symbol: str = Field(default="BTC/USDT", alias="DEFAULT_SYMBOL")
    default_timeframe: str = Field(default="1h", alias="DEFAULT_TIMEFRAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
