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


def test_market_data_sync_service_stores_only_newer_candles(tmp_path: Path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'market_sync_overlap.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    start = datetime(2026, 1, 1, tzinfo=UTC)

    MarketDataService(session).store_candles(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        candles=[
            MarketDataSyncService._to_candle_input(
                ExchangeCandle(
                    open_time=start,
                    close_time=start + timedelta(hours=1),
                    open_price=Decimal("100"),
                    high_price=Decimal("110"),
                    low_price=Decimal("90"),
                    close_price=Decimal("105"),
                    volume=Decimal("12"),
                )
            ),
            MarketDataSyncService._to_candle_input(
                ExchangeCandle(
                    open_time=start + timedelta(hours=1),
                    close_time=start + timedelta(hours=2),
                    open_price=Decimal("105"),
                    high_price=Decimal("112"),
                    low_price=Decimal("103"),
                    close_price=Decimal("111"),
                    volume=Decimal("15"),
                )
            ),
        ],
    )

    result = MarketDataSyncService(
        session,
        FakeExchangeClient(
            [
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
                ExchangeCandle(
                    open_time=start + timedelta(hours=2),
                    close_time=start + timedelta(hours=3),
                    open_price=Decimal("111"),
                    high_price=Decimal("113"),
                    low_price=Decimal("109"),
                    close_price=Decimal("112"),
                    volume=Decimal("8"),
                ),
            ]
        ),
    ).sync_recent_closed_candles(
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

    assert result.fetched_count == 3
    assert result.stored_count == 1
    assert result.latest_open_time == start + timedelta(hours=2)
    assert len(stored) == 3
    assert stored[0].close_price == Decimal("112")

    session.close()


def test_market_data_sync_service_backfills_older_candles(tmp_path: Path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'market_sync_backfill.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    start = datetime(2026, 1, 1, tzinfo=UTC)

    MarketDataService(session).store_candles(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        candles=[
            MarketDataSyncService._to_candle_input(
                ExchangeCandle(
                    open_time=start + timedelta(hours=2),
                    close_time=start + timedelta(hours=3),
                    open_price=Decimal("111"),
                    high_price=Decimal("113"),
                    low_price=Decimal("109"),
                    close_price=Decimal("112"),
                    volume=Decimal("8"),
                )
            ),
        ],
    )

    result = MarketDataSyncService(
        session,
        FakeExchangeClient(
            [
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
                ExchangeCandle(
                    open_time=start + timedelta(hours=2),
                    close_time=start + timedelta(hours=3),
                    open_price=Decimal("111"),
                    high_price=Decimal("113"),
                    low_price=Decimal("109"),
                    close_price=Decimal("112"),
                    volume=Decimal("8"),
                ),
            ]
        ),
    ).sync_recent_closed_candles(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        limit=10,
        backfill=True,
    )
    stored = MarketDataService(session).list_historical_candles(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
    )

    assert result.fetched_count == 3
    assert result.stored_count == 3
    assert result.latest_open_time == start + timedelta(hours=2)
    assert len(stored) == 3
    assert stored[0].close_price == Decimal("105")

    session.close()


# ---------------------------------------------------------------------------
# sync_candles_paginated tests
# ---------------------------------------------------------------------------


class PaginatingFakeClient:
    """Returns candles in pages when end_time is provided."""

    name = "fake"

    def __init__(self, all_candles: list[ExchangeCandle], page_size: int = 3) -> None:
        self._all = sorted(all_candles, key=lambda c: c.open_time)
        self._page_size = page_size

    def fetch_closed_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
        end_time: datetime | None = None,
    ) -> list[ExchangeCandle]:
        eligible = (
            [c for c in self._all if end_time is None or c.open_time < end_time]
            if end_time is not None
            else list(self._all)
        )
        # Return the most-recent `limit` candles from eligible set
        return eligible[-limit:]


def _make_candles(n: int) -> list[ExchangeCandle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        ExchangeCandle(
            open_time=start + timedelta(hours=i),
            close_time=start + timedelta(hours=i + 1),
            open_price=Decimal("100"),
            high_price=Decimal("100"),
            low_price=Decimal("100"),
            close_price=Decimal("100"),
            volume=Decimal("1"),
        )
        for i in range(n)
    ]


def test_sync_candles_paginated_single_page(tmp_path: Path) -> None:
    """When total_limit <= page_size, fetches in one request."""
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'paginated.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()

    candles = _make_candles(5)
    client = PaginatingFakeClient(candles, page_size=10)
    result = MarketDataSyncService(session, client).sync_candles_paginated(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        total_limit=5,
    )

    assert result.fetched_count == 5
    assert result.stored_count == 5
    session.close()


def test_sync_candles_paginated_multiple_pages(tmp_path: Path) -> None:
    """When total_limit > page_size, paginates backwards and stores all candles."""
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'paginated_multi.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()

    candles = _make_candles(7)
    client = PaginatingFakeClient(candles, page_size=3)
    result = MarketDataSyncService(session, client).sync_candles_paginated(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        total_limit=7,
        page_size=3,
    )

    assert result.fetched_count == 7
    assert result.stored_count == 7
    session.close()


def test_sync_candles_paginated_stops_when_exchange_exhausted(tmp_path: Path) -> None:
    """Stops paginating when exchange returns fewer candles than requested."""
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'paginated_exhaust.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()

    candles = _make_candles(4)
    client = PaginatingFakeClient(candles)
    # Request 100 but only 4 exist
    result = MarketDataSyncService(session, client).sync_candles_paginated(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        total_limit=100,
        page_size=10,
    )

    assert result.fetched_count == 4
    assert result.stored_count == 4
    session.close()


def test_compute_backtest_sync_limit_small_timeframe() -> None:
    """Small timeframe sync limit is driven by 7-day window, not strategy warm-up."""
    from app.application.services.operational_control_service import _compute_backtest_sync_limit

    # 1m: 7 days = 10080 candles, required_candles + 100 = 151
    assert _compute_backtest_sync_limit("1m", 51) == 10080
    # 5m: 7 days = 2016 candles
    assert _compute_backtest_sync_limit("5m", 51) == 2016


def test_compute_backtest_sync_limit_large_timeframe() -> None:
    """For large timeframes the strategy warm-up + 100 can exceed 7 days."""
    from app.application.services.operational_control_service import _compute_backtest_sync_limit

    # 4h: 7 days = 42 candles, required_candles + 100 = 151 → strategy wins
    assert _compute_backtest_sync_limit("4h", 51) == 151
    # 1h: 7 days = 168 candles, required + 100 = 151 → 7-day window wins
    assert _compute_backtest_sync_limit("1h", 51) == 168
