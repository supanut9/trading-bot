from __future__ import annotations

import io
import json
from decimal import Decimal

import pytest

from app.infrastructure.exchanges.base import ExchangeOrderRequest
from app.infrastructure.exchanges.binance import BinanceSpotOrderClient


class FakeOrderResponse:
    def __init__(self, payload: object) -> None:
        self._buffer = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self) -> io.BytesIO:
        return self._buffer

    def __exit__(self, exc_type, exc, tb) -> None:
        self._buffer.close()


def test_binance_order_client_submits_validate_only_order(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: int) -> FakeOrderResponse:
        captured["url"] = request.full_url
        captured["body"] = request.data.decode("utf-8")
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return FakeOrderResponse({})

    monkeypatch.setattr("app.infrastructure.exchanges.binance.urlopen", fake_urlopen)
    monkeypatch.setattr(
        "app.infrastructure.exchanges.binance.datetime",
        type(
            "FixedDatetime",
            (),
            {"now": staticmethod(BinanceDateTime.now)},
        ),
    )

    submission = BinanceSpotOrderClient(
        api_key="key",
        api_secret="secret",
    ).submit_order(
        ExchangeOrderRequest(
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.1"),
            client_order_id="live-btc-1",
            validate_only=True,
        )
    )

    assert submission.status == "validated"
    assert submission.exchange_order_id is None
    assert captured["url"] == "https://api.binance.com/api/v3/order/test"
    assert "signature=" in captured["body"]
    assert "newClientOrderId=live-btc-1" in captured["body"]
    assert captured["headers"]["X-mbx-apikey"] == "key"
    assert captured["timeout"] == 10


def test_binance_order_client_parses_submitted_order_id(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.exchanges.binance.urlopen",
        lambda request, timeout: FakeOrderResponse({"orderId": 12345}),
    )
    monkeypatch.setattr(
        "app.infrastructure.exchanges.binance.datetime",
        type(
            "FixedDatetime",
            (),
            {"now": staticmethod(BinanceDateTime.now)},
        ),
    )

    submission = BinanceSpotOrderClient(
        api_key="key",
        api_secret="secret",
    ).submit_order(
        ExchangeOrderRequest(
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("0.2"),
            validate_only=False,
        )
    )

    assert submission.status == "submitted"
    assert submission.exchange_order_id == "12345"


def test_binance_order_client_fetches_account_balances(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.exchanges.binance.urlopen",
        lambda request, timeout: FakeOrderResponse(
            {
                "balances": [
                    {"asset": "BTC", "free": "0.00200000", "locked": "0.00100000"},
                    {"asset": "USDT", "free": "125.50", "locked": "0.00"},
                ]
            }
        ),
    )
    monkeypatch.setattr(
        "app.infrastructure.exchanges.binance.datetime",
        type(
            "FixedDatetime",
            (),
            {"now": staticmethod(BinanceDateTime.now)},
        ),
    )

    balances = BinanceSpotOrderClient(
        api_key="key",
        api_secret="secret",
    ).fetch_account_balances()

    assert balances[0].asset == "BTC"
    assert balances[0].free == Decimal("0.00200000")
    assert balances[0].locked == Decimal("0.00100000")
    assert balances[1].asset == "USDT"
    assert balances[1].free == Decimal("125.50")


def test_binance_order_client_cancels_order(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: int) -> FakeOrderResponse:
        captured["method"] = request.get_method()
        captured["url"] = request.full_url
        captured["body"] = request.data.decode("utf-8")
        return FakeOrderResponse({"status": "CANCELED", "orderId": 12345})

    monkeypatch.setattr("app.infrastructure.exchanges.binance.urlopen", fake_urlopen)
    monkeypatch.setattr(
        "app.infrastructure.exchanges.binance.datetime",
        type(
            "FixedDatetime",
            (),
            {"now": staticmethod(BinanceDateTime.now)},
        ),
    )

    cancellation = BinanceSpotOrderClient(
        api_key="key",
        api_secret="secret",
    ).cancel_order(symbol="BTC/USDT", exchange_order_id="12345")

    assert captured["method"] == "DELETE"
    assert captured["url"] == "https://api.binance.com/api/v3/order"
    assert "orderId=12345" in str(captured["body"])
    assert "signature=" in str(captured["body"])
    assert cancellation.status == "canceled"
    assert cancellation.exchange_order_id == "12345"


def test_binance_order_client_raises_runtime_error_on_transport_failure(monkeypatch) -> None:
    def raise_timeout(request, timeout: int) -> FakeOrderResponse:
        raise TimeoutError("slow")

    monkeypatch.setattr("app.infrastructure.exchanges.binance.urlopen", raise_timeout)
    monkeypatch.setattr(
        "app.infrastructure.exchanges.binance.datetime",
        type(
            "FixedDatetime",
            (),
            {"now": staticmethod(BinanceDateTime.now)},
        ),
    )

    with pytest.raises(RuntimeError, match="failed to submit Binance order"):
        BinanceSpotOrderClient(
            api_key="key",
            api_secret="secret",
        ).submit_order(
            ExchangeOrderRequest(
                symbol="BTC/USDT",
                side="buy",
                quantity=Decimal("0.1"),
            )
        )


class BinanceDateTime:
    @staticmethod
    def now(_tz) -> object:
        from datetime import UTC, datetime

        return datetime(2026, 1, 1, 2, tzinfo=UTC)
