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
    ExchangeAPIError,
    ExchangeAssetBalance,
    ExchangeCandle,
    ExchangeConnectionError,
    ExchangeOrderCancellation,
    ExchangeOrderRequest,
    ExchangeOrderStatus,
    ExchangeOrderSubmission,
    ExchangeSymbolRules,
    ExchangeTickerPrice,
    FuturesOrderExchangeClient,
    LiveOrderExchangeClient,
    MarketDataExchangeClient,
)


class BinanceMarketDataClient(MarketDataExchangeClient):
    name = "binance"

    def __init__(
        self,
        *,
        base_url: str = "https://api.binance.com",
        trading_mode: str = "SPOT",
        timeout_seconds: int = 10,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._trading_mode = trading_mode
        self._timeout_seconds = timeout_seconds

    def fetch_closed_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
        end_time: datetime | None = None,
    ) -> Sequence[ExchangeCandle]:
        request_limit = max(1, min(limit + 1, 1000))
        params: dict[str, object] = {
            "symbol": symbol.replace("/", ""),
            "interval": timeframe,
            "limit": request_limit,
        }
        if end_time is not None:
            params["endTime"] = int(end_time.timestamp() * 1000) - 1
        query = urlencode(params)
        base_path = "/fapi/v1" if self._trading_mode == "FUTURES" else "/api/v3"
        url = f"{self._base_url}{base_path}/klines?{query}"
        try:
            with urlopen(url, timeout=self._timeout_seconds) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ExchangeConnectionError(f"failed to fetch Binance candles: {exc}") from exc

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
        base_path = "/fapi/v1" if self._trading_mode == "FUTURES" else "/api/v3"
        url = f"{self._base_url}{base_path}/ticker/price?{query}"
        try:
            with urlopen(url, timeout=self._timeout_seconds) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ExchangeConnectionError(f"failed to fetch Binance latest price: {exc}") from exc

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

    def fetch_symbol_rules(self, *, symbol: str) -> ExchangeSymbolRules:
        raw_symbol = symbol.replace("/", "")
        query = urlencode({"symbol": raw_symbol})
        url = f"{self._base_url}/api/v3/exchangeInfo?{query}"
        try:
            with urlopen(url, timeout=self._timeout_seconds) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ExchangeConnectionError(f"failed to fetch Binance exchange info: {exc}") from exc

        if not isinstance(payload, dict):
            raise ValueError("unexpected Binance exchange info payload")

        symbols_list = payload.get("symbols", [])
        if not isinstance(symbols_list, list) or not symbols_list:
            raise ValueError(f"symbol {raw_symbol} not found in Binance exchange info")

        symbol_info = symbols_list[0]
        filters = {f["filterType"]: f for f in symbol_info.get("filters", [])}

        lot_size = filters.get("LOT_SIZE", {})
        min_notional_filter = filters.get("MIN_NOTIONAL", filters.get("NOTIONAL", {}))
        price_filter = filters.get("PRICE_FILTER", {})

        return ExchangeSymbolRules(
            exchange="binance",
            symbol=symbol,
            min_qty=Decimal(str(lot_size.get("minQty", "0.00000001"))),
            max_qty=Decimal(str(lot_size.get("maxQty", "0"))),
            step_size=Decimal(str(lot_size.get("stepSize", "0.00000001"))),
            min_notional=Decimal(str(min_notional_filter.get("minNotional", "0"))),
            tick_size=Decimal(str(price_filter.get("tickSize", "0.00000001"))),
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
        parameters: dict[str, str | int | None] = {
            "symbol": request.symbol.replace("/", ""),
            "side": request.side.upper(),
            "type": request.order_type.upper(),
            "quantity": format(request.quantity, "f"),
            "newClientOrderId": request.client_order_id,
        }
        if request.order_type.upper() == "LIMIT":
            if request.price is None:
                raise ValueError("price is required for limit orders")
            parameters["price"] = format(request.price, "f")
            parameters["timeInForce"] = "GTC"

        parsed = self._signed_request(
            method="POST",
            endpoint=endpoint,
            parameters=parameters,
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
        except HTTPError as exc:
            try:
                error_raw = exc.read().decode("utf-8") or "{}"
                error_payload = json.loads(error_raw)
            except json.JSONDecodeError:
                raise ExchangeConnectionError(f"failed to {error_action}: {exc}") from exc
            if isinstance(error_payload, dict):
                code = error_payload.get("code")
                message = error_payload.get("msg")
                raise ExchangeAPIError(
                    f"failed to {error_action}: code={code} msg={message}"
                ) from exc
            raise ExchangeConnectionError(f"failed to {error_action}: {exc}") from exc
        except (URLError, TimeoutError) as exc:
            raise ExchangeConnectionError(f"failed to {error_action}: {exc}") from exc
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
        if request.order_type.upper() == "LIMIT":
            if request.price is None:
                raise ValueError("price is required for limit orders")
            parameters["price"] = format(request.price, "f")
            parameters["timeInForce"] = "GTC"
        return urlencode(parameters)


class BinanceFuturesOrderClient(BinanceSpotOrderClient, FuturesOrderExchangeClient):
    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        base_url: str = "https://fapi.binance.com",
        timeout_seconds: int = 10,
        recv_window_ms: int = 5000,
    ) -> None:
        super().__init__(
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            recv_window_ms=recv_window_ms,
        )

    def submit_order(self, request: ExchangeOrderRequest) -> ExchangeOrderSubmission:
        if request.validate_only:
            return ExchangeOrderSubmission(
                status="validated",
                client_order_id=request.client_order_id,
                exchange_order_id=None,
                response_payload={"detail": "futures validation-only bypass"},
            )

        endpoint = "/fapi/v1/order"
        parameters: dict[str, str | int | None] = {
            "symbol": request.symbol.replace("/", ""),
            "side": request.side.upper(),
            "type": request.order_type.upper(),
            "quantity": format(request.quantity, "f"),
            "newClientOrderId": request.client_order_id,
        }
        if request.order_type.upper() == "LIMIT":
            if request.price is None:
                raise ValueError("price is required for limit orders")
            parameters["price"] = format(request.price, "f")
            parameters["timeInForce"] = "GTC"

        parsed = self._signed_request(
            method="POST",
            endpoint=endpoint,
            parameters=parameters,
            error_action="submit Binance futures order",
        )

        exchange_order_id = parsed.get("orderId")
        return ExchangeOrderSubmission(
            status="submitted",
            client_order_id=request.client_order_id,
            exchange_order_id=str(exchange_order_id) if exchange_order_id is not None else None,
            response_payload=parsed,
        )

    def fetch_account_balances(self) -> Sequence[ExchangeAssetBalance]:
        parsed = self._signed_request(
            method="GET",
            endpoint="/fapi/v2/account",
            parameters={},
            error_action="fetch Binance futures account balances",
        )
        assets = parsed.get("assets", [])
        balances: list[ExchangeAssetBalance] = []
        for item in assets:
            balances.append(
                ExchangeAssetBalance(
                    asset=str(item.get("asset", "")).upper(),
                    free=Decimal(str(item.get("walletBalance", "0"))),
                    locked=Decimal("0"),
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
        parsed = self._signed_request(
            method="DELETE",
            endpoint="/fapi/v1/order",
            parameters={
                "symbol": symbol.replace("/", ""),
                "origClientOrderId": client_order_id,
                "orderId": exchange_order_id,
            },
            error_action="cancel Binance futures order",
        )
        return ExchangeOrderCancellation(
            status=str(parsed.get("status", "")).lower(),
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            response_payload=parsed,
        )

    def fetch_order_status(
        self,
        *,
        symbol: str,
        client_order_id: str | None = None,
        exchange_order_id: str | None = None,
    ) -> ExchangeOrderStatus:
        parsed = self._signed_request(
            method="GET",
            endpoint="/fapi/v1/order",
            parameters={
                "symbol": symbol.replace("/", ""),
                "origClientOrderId": client_order_id,
                "orderId": exchange_order_id,
            },
            error_action="fetch Binance futures order status",
        )
        executed_quantity = Decimal(str(parsed.get("executedQty", "0")))
        average_fill_price = Decimal(str(parsed.get("avgPrice", "0")))
        return ExchangeOrderStatus(
            status=str(parsed.get("status", "")).lower(),
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            executed_quantity=executed_quantity,
            average_fill_price=average_fill_price if average_fill_price > 0 else None,
            response_payload=parsed,
        )

    def set_leverage(self, *, symbol: str, leverage: int) -> dict[str, object]:
        return self._signed_request(
            method="POST",
            endpoint="/fapi/v1/leverage",
            parameters={
                "symbol": symbol.replace("/", ""),
                "leverage": leverage,
            },
            error_action="set Binance leverage",
        )

    def set_margin_mode(self, *, symbol: str, margin_mode: str) -> dict[str, object]:
        try:
            return self._signed_request(
                method="POST",
                endpoint="/fapi/v1/marginType",
                parameters={
                    "symbol": symbol.replace("/", ""),
                    "marginType": margin_mode.upper(),
                },
                error_action="set Binance margin mode",
            )
        except ExchangeAPIError as exc:
            if "code=-4046" in str(exc) or "No need to change margin type" in str(exc):
                return {"code": -4046, "msg": "No need to change margin type."}
            raise

    def fetch_position_risk(self, *, symbol: str) -> dict[str, object]:
        return self._signed_request(
            method="GET",
            endpoint="/fapi/v2/positionRisk",
            parameters={"symbol": symbol.replace("/", "")},
            error_action="fetch Binance position risk",
        )

    def fetch_mark_price(self, *, symbol: str) -> Decimal:
        parsed = self._signed_request(
            method="GET",
            endpoint="/fapi/v1/premiumIndex",
            parameters={"symbol": symbol.replace("/", "")},
            error_action="fetch Binance mark price",
        )
        if isinstance(parsed, dict):
            return Decimal(str(parsed.get("markPrice", "0")))
        return Decimal("0")
