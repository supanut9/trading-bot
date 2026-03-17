from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from app.infrastructure.exchanges.base import ExchangeCandle, MarketDataExchangeClient


class BinanceMarketDataClient(MarketDataExchangeClient):
    name = "binance"

    def __init__(
        self,
        *,
        base_url: str = "https://api.binance.com",
        timeout_seconds: int = 10,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def fetch_closed_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> Sequence[ExchangeCandle]:
        request_limit = max(1, min(limit + 1, 1000))
        query = urlencode(
            {
                "symbol": symbol.replace("/", ""),
                "interval": timeframe,
                "limit": request_limit,
            }
        )
        url = f"{self._base_url}/api/v3/klines?{query}"
        try:
            with urlopen(url, timeout=self._timeout_seconds) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"failed to fetch Binance candles: {exc}") from exc

        if not isinstance(payload, list):
            raise ValueError("unexpected Binance candle payload")

        now = datetime.now(UTC)
        candles: list[ExchangeCandle] = []
        for item in payload:
            if not isinstance(item, list) or len(item) < 7:
                raise ValueError("unexpected Binance candle row")

            candle = ExchangeCandle(
                open_time=datetime.fromtimestamp(item[0] / 1000, tz=UTC),
                close_time=datetime.fromtimestamp(item[6] / 1000, tz=UTC),
                open_price=Decimal(str(item[1])),
                high_price=Decimal(str(item[2])),
                low_price=Decimal(str(item[3])),
                close_price=Decimal(str(item[4])),
                volume=Decimal(str(item[5])),
            )
            if candle.close_time <= now:
                candles.append(candle)

        return candles[-limit:]
