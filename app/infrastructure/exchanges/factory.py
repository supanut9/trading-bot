from app.config import Settings
from app.infrastructure.exchanges.base import MarketDataExchangeClient
from app.infrastructure.exchanges.binance import BinanceMarketDataClient


def build_market_data_exchange_client(settings: Settings) -> MarketDataExchangeClient:
    if settings.exchange_name.lower() == "binance":
        return BinanceMarketDataClient(
            base_url=settings.market_data_api_base_url,
            timeout_seconds=settings.market_data_sync_timeout_seconds,
        )
    raise ValueError(f"unsupported exchange for market data sync: {settings.exchange_name}")
