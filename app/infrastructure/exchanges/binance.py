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
    ExchangeAssetBalance,
    ExchangeCandle,
    ExchangeOrderCancellation,
    ExchangeOrderRequest,
    ExchangeOrderStatus,
    ExchangeOrderSubmission,
    ExchangeTickerPrice,
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

    def fetch_latest_price(self, *, symbol: str) -> ExchangeTickerPrice:
        query = urlencode({"symbol": symbol.replace("/", "")})
        url = f"{self._base_url}/api/v3/ticker/price?{query}"
        try:
            with urlopen(url, timeout=self._timeout_seconds) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"failed to fetch Binance latest price: {exc}") from exc

        if not isinstance(payload, dict):
            raise ValueError("unexpected Binance latest price payload")

        raw_symbol = payload.get("symbol")
        raw_price = payload.get("price")
        if raw_symbol is None or raw_price is None:
            raise ValueError("unexpected Binance latest price payload")

        normalized_symbol = str(raw_symbol)
        if normalized_symbol.endswith("USDT") and "/" not in normalized_symbol:
            normalized_symbol = f"{normalized_symbol[:-4]}/USDT"

        return ExchangeTickerPrice(
            symbol=normalized_symbol,
            price=Decimal(str(raw_price)),
        )


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
        self._api_secret = api_secret.encode()
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._recv_window_ms = recv_window_ms

    def submit_order(self, request: ExchangeOrderRequest) -> ExchangeOrderSubmission:
        endpoint = "/api/v3/order/test" if request.validate_only else "/api/v3/order"
        parsed = self._signed_request(
            method="POST",
            endpoint=endpoint,
            parameters={
                "symbol": request.symbol.replace("/", ""),
                "side": request.side.upper(),
                "type": request.order_type.upper(),
                "quantity": format(request.quantity, "f"),
                "newClientOrderId": request.client_order_id,
            },
            error_action="submit Binance order",
        )

        exchange_order_id = parsed.get("orderId")
        return ExchangeOrderSubmission(
            status="validated" if request.validate_only else "submitted",
            client_order_id=request.client_order_id,
            exchange_order_id=str(exchange_order_id) if exchange_order_id is not None else None,
            response_payload=parsed,
        )

    def fetch_account_balances(self) -> Sequence[ExchangeAssetBalance]:
        parsed = self._signed_request(
            method="GET",
            endpoint="/api/v3/account",
            parameters={},
            error_action="fetch Binance account balances",
        )
        raw_balances = parsed.get("balances")
        if not isinstance(raw_balances, list):
            raise ValueError("unexpected Binance account balance payload")

        balances: list[ExchangeAssetBalance] = []
        for item in raw_balances:
            if not isinstance(item, dict):
                raise ValueError("unexpected Binance account balance row")
            balances.append(
                ExchangeAssetBalance(
                    asset=str(item.get("asset", "")).upper(),
                    free=Decimal(str(item.get("free", "0"))),
                    locked=Decimal(str(item.get("locked", "0"))),
                )
            )
        return balances

    def cancel_order(
        self,
        *,
        symbol: str,
        client_order_id: str | None = None,
        exchange_order_id: str | None = None,
    ) -> ExchangeOrderCancellation:
        if client_order_id is None and exchange_order_id is None:
            raise ValueError("client_order_id or exchange_order_id is required")

        parsed = self._signed_request(
            method="DELETE",
            endpoint="/api/v3/order",
            parameters={
                "symbol": symbol.replace("/", ""),
                "origClientOrderId": client_order_id,
                "orderId": exchange_order_id,
            },
            error_action="cancel Binance order",
        )
        return ExchangeOrderCancellation(
            status=str(parsed.get("status", "")).lower(),
            client_order_id=(
                str(parsed.get("clientOrderId")) if parsed.get("clientOrderId") else client_order_id
            ),
            exchange_order_id=(
                str(parsed.get("orderId")) if parsed.get("orderId") else exchange_order_id
            ),
            response_payload=parsed,
        )

    def fetch_order_status(
        self,
        *,
        symbol: str,
        client_order_id: str | None = None,
        exchange_order_id: str | None = None,
    ) -> ExchangeOrderStatus:
        if client_order_id is None and exchange_order_id is None:
            raise ValueError("client_order_id or exchange_order_id is required")

        parsed = self._signed_request(
            method="GET",
            endpoint="/api/v3/order",
            parameters={
                "symbol": symbol.replace("/", ""),
                "origClientOrderId": client_order_id,
                "orderId": exchange_order_id,
            },
            error_action="fetch Binance order status",
        )
        executed_quantity = Decimal(str(parsed.get("executedQty", "0")))
        average_fill_price = None
        if executed_quantity > Decimal("0"):
            cumulative_quote = Decimal(str(parsed.get("cummulativeQuoteQty", "0")))
            average_fill_price = cumulative_quote / executed_quantity
        return ExchangeOrderStatus(
            status=str(parsed.get("status", "")).lower(),
            client_order_id=(
                str(parsed.get("clientOrderId")) if parsed.get("clientOrderId") else client_order_id
            ),
            exchange_order_id=(
                str(parsed.get("orderId")) if parsed.get("orderId") else exchange_order_id
            ),
            executed_quantity=executed_quantity,
            average_fill_price=average_fill_price,
            response_payload=parsed,
        )

    def _signed_request(
        self,
        *,
        method: str,
        endpoint: str,
        parameters: dict[str, str | int | None],
        error_action: str,
    ) -> dict[str, object]:
        filtered_parameters = {key: value for key, value in parameters.items() if value is not None}
        filtered_parameters.update(
            {
                "timestamp": int(datetime.now(UTC).timestamp() * 1000),
                "recvWindow": self._recv_window_ms,
            }
        )
        payload = urlencode(filtered_parameters)
        signature = hmac.new(
            self._api_secret,
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if method == "GET":
            url = f"{self._base_url}{endpoint}?{payload}&signature={signature}"
            body = None
        else:
            url = f"{self._base_url}{endpoint}"
            body = f"{payload}&signature={signature}".encode()
        http_request = Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-MBX-APIKEY": self._api_key,
            },
            method=method,
        )
        try:
            with urlopen(http_request, timeout=self._timeout_seconds) as response:
                raw = response.read().decode("utf-8") or "{}"
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f"failed to {error_action}: {exc}") from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("failed to parse Binance order response") from exc
        if not isinstance(parsed, dict):
            raise ValueError("unexpected Binance order response payload")
        return parsed

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
