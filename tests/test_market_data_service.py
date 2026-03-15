from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.application.services.market_data_service import CandleInput, MarketDataService
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def test_market_data_service_stores_and_lists_recent_candles(tmp_path: Path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'market_data.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(settings)
    session = session_factory()

    service = MarketDataService(session)
    first_open = datetime(2026, 1, 1, tzinfo=UTC)

    stored = service.store_candles(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        candles=[
            CandleInput(
                open_time=first_open,
                close_time=first_open + timedelta(hours=1),
                open_price=Decimal("100000.0"),
                high_price=Decimal("100100.0"),
                low_price=Decimal("99900.0"),
                close_price=Decimal("100050.0"),
                volume=Decimal("12.5"),
            ),
            CandleInput(
                open_time=first_open + timedelta(hours=1),
                close_time=first_open + timedelta(hours=2),
                open_price=Decimal("100050.0"),
                high_price=Decimal("100300.0"),
                low_price=Decimal("100000.0"),
                close_price=Decimal("100250.0"),
                volume=Decimal("9.3"),
            ),
        ],
    )

    recent = service.list_recent_candles(exchange="binance", symbol="BTC/USDT", timeframe="1h")

    assert len(stored) == 2
    assert len(recent) == 2
    assert recent[0].open_time > recent[1].open_time
    assert recent[0].close_price == Decimal("100250.0")

    session.close()
