from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.application.services.market_data_service import MarketDataService
from app.application.services.market_data_sync_service import MarketDataSyncService
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory
from app.infrastructure.exchanges.base import ExchangeCandle


class FakeExchangeClient:
    name = "fake"

    def __init__(self, candles: list[ExchangeCandle]) -> None:
        self._candles = candles

    def fetch_closed_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[ExchangeCandle]:
        assert symbol == "BTC/USDT"
        assert timeframe == "1h"
        assert limit == 10
        return self._candles


def test_market_data_sync_service_fetches_and_stores_candles(tmp_path: Path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'market_sync.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        ExchangeCandle(
            open_time=start,
            close_time=start + timedelta(hours=1),
            open_price=Decimal("100"),
            high_price=Decimal("110"),
            low_price=Decimal("90"),
            close_price=Decimal("105"),
            volume=Decimal("12"),
        ),
        ExchangeCandle(
            open_time=start + timedelta(hours=1),
            close_time=start + timedelta(hours=2),
            open_price=Decimal("105"),
            high_price=Decimal("112"),
            low_price=Decimal("103"),
            close_price=Decimal("111"),
            volume=Decimal("15"),
        ),
    ]

    result = MarketDataSyncService(session, FakeExchangeClient(candles)).sync_recent_closed_candles(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        limit=10,
    )
    stored = MarketDataService(session).list_recent_candles(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
    )

    assert result.fetched_count == 2
    assert result.stored_count == 2
    assert result.latest_open_time == start + timedelta(hours=1)
    assert len(stored) == 2
    assert stored[0].close_price == Decimal("111")

    session.close()
