from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.infrastructure.exchanges.base import (
    ExchangeCandle,
    ExchangeOrderRequest,
    ExchangeOrderSubmission,
    LiveOrderExchangeClient,
    MarketDataExchangeClient,
)


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


class BinanceSpotOrderClient(LiveOrderExchangeClient):
    name = "binance"

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        base_url: str = "https://api.binance.com",
        timeout_seconds: int = 10,
        recv_window_ms: int = 5000,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret.encode("utf-8")
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._recv_window_ms = recv_window_ms

    def submit_order(self, request: ExchangeOrderRequest) -> ExchangeOrderSubmission:
        endpoint = "/api/v3/order/test" if request.validate_only else "/api/v3/order"
        payload = self._build_signed_payload(request)
        signature = hmac.new(
            self._api_secret,
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        body = f"{payload}&signature={signature}".encode()
        http_request = Request(
            f"{self._base_url}{endpoint}",
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-MBX-APIKEY": self._api_key,
            },
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=self._timeout_seconds) as response:
                raw = response.read().decode("utf-8") or "{}"
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f"failed to submit Binance order: {exc}") from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("failed to parse Binance order response") from exc
        if not isinstance(parsed, dict):
            raise ValueError("unexpected Binance order response payload")

        exchange_order_id = parsed.get("orderId")
        return ExchangeOrderSubmission(
            status="validated" if request.validate_only else "submitted",
            client_order_id=request.client_order_id,
            exchange_order_id=str(exchange_order_id) if exchange_order_id is not None else None,
            response_payload=parsed,
        )

    def _build_signed_payload(self, request: ExchangeOrderRequest) -> str:
        parameters: dict[str, str | int] = {
            "symbol": request.symbol.replace("/", ""),
            "side": request.side.upper(),
            "type": request.order_type.upper(),
            "quantity": format(request.quantity, "f"),
            "timestamp": int(datetime.now(UTC).timestamp() * 1000),
            "recvWindow": self._recv_window_ms,
        }
        if request.client_order_id:
            parameters["newClientOrderId"] = request.client_order_id
        return urlencode(parameters)
