from app.config import Settings
from app.infrastructure.exchanges.base import LiveOrderExchangeClient, MarketDataExchangeClient
from app.infrastructure.exchanges.binance import BinanceMarketDataClient, BinanceSpotOrderClient


def build_market_data_exchange_client(settings: Settings) -> MarketDataExchangeClient:
    if settings.exchange_name.lower() == "binance":
        return BinanceMarketDataClient(
            base_url=settings.market_data_api_base_url,
            timeout_seconds=settings.market_data_sync_timeout_seconds,
        )
    raise ValueError(f"unsupported exchange for market data sync: {settings.exchange_name}")


def build_live_order_exchange_client(settings: Settings) -> LiveOrderExchangeClient:
    if settings.exchange_name.lower() == "binance":
        if not settings.exchange_api_key or not settings.exchange_api_secret:
            raise ValueError(
                "EXCHANGE_API_KEY and EXCHANGE_API_SECRET are required for live order routing"
            )
        return BinanceSpotOrderClient(
            api_key=settings.exchange_api_key,
            api_secret=settings.exchange_api_secret,
            base_url=settings.exchange_api_base_url,
            timeout_seconds=settings.exchange_request_timeout_seconds,
        )
    raise ValueError(f"unsupported exchange for live order routing: {settings.exchange_name}")
