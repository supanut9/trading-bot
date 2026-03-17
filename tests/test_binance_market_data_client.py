from __future__ import annotations

import io
import json
from urllib.error import URLError

import pytest

from app.infrastructure.exchanges.binance import BinanceMarketDataClient


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._buffer = io.StringIO(json.dumps(payload))

    def __enter__(self) -> io.StringIO:
        return self._buffer

    def __exit__(self, exc_type, exc, tb) -> None:
        self._buffer.close()


def test_binance_client_parses_closed_candles_and_drops_open_one(monkeypatch) -> None:
    payload = [
        [1735689600000, "100", "110", "90", "105", "12", 1735693200000],
        [1735693200000, "105", "112", "103", "111", "15", 4735696800000],
    ]

    monkeypatch.setattr(
        "app.infrastructure.exchanges.binance.urlopen",
        lambda url, timeout: FakeResponse(payload),
    )
    monkeypatch.setattr(
        "app.infrastructure.exchanges.binance.datetime",
        type(
            "FixedDatetime",
            (),
            {
                "now": staticmethod(BinanceDateTime.now),
                "fromtimestamp": staticmethod(BinanceDateTime.fromtimestamp),
            },
        ),
    )

    candles = BinanceMarketDataClient().fetch_closed_candles(
        symbol="BTC/USDT",
        timeframe="1h",
        limit=5,
    )

    assert len(candles) == 1
    assert str(candles[0].close_price) == "105"


def test_binance_client_raises_runtime_error_on_transport_failure(monkeypatch) -> None:
    def raise_url_error(url: str, timeout: int) -> FakeResponse:
        raise URLError("offline")

    monkeypatch.setattr("app.infrastructure.exchanges.binance.urlopen", raise_url_error)

    with pytest.raises(RuntimeError, match="failed to fetch Binance candles"):
        BinanceMarketDataClient().fetch_closed_candles(
            symbol="BTC/USDT",
            timeframe="1h",
            limit=5,
        )


class BinanceDateTime:
    @staticmethod
    def now(_tz) -> object:
        from datetime import UTC, datetime

        return datetime(2026, 1, 1, 2, tzinfo=UTC)

    @staticmethod
    def fromtimestamp(value: float, tz) -> object:
        from datetime import datetime

        return datetime.fromtimestamp(value, tz=tz)
