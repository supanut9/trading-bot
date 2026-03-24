from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.application.services.market_data_coverage_service import MarketDataCoverageService
from app.application.services.market_data_service import CandleInput, MarketDataService
from app.application.services.operational_control_service import BacktestRunOptions
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


def test_market_data_coverage_service_reports_readiness_and_staleness(tmp_path: Path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'market_data_coverage.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(settings)
    session = session_factory()

    first_open = datetime(2026, 1, 1, tzinfo=UTC)
    MarketDataService(session).store_candles(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        candles=[
            CandleInput(
                open_time=first_open + timedelta(hours=index),
                close_time=first_open + timedelta(hours=index + 1),
                open_price=Decimal("100000.0"),
                high_price=Decimal("100100.0"),
                low_price=Decimal("99900.0"),
                close_price=Decimal("100050.0"),
                volume=Decimal("12.5"),
            )
            for index in range(6)
        ],
    )

    result = MarketDataCoverageService(session).get_coverage(
        options=BacktestRunOptions(
            strategy_name="ema_crossover",
            exchange="binance",
            symbol="BTC/USDT",
            timeframe="1h",
            fast_period=3,
            slow_period=5,
        ),
        now=datetime(2026, 1, 1, 7, tzinfo=UTC),
    )

    assert result.candle_count == 6
    assert result.required_candles == 6
    assert result.additional_candles_needed == 0
    assert result.satisfies_required_candles is True
    assert result.freshness_status == "fresh"
    assert result.readiness_status == "ready"

    stale_result = MarketDataCoverageService(session).get_coverage(
        options=BacktestRunOptions(
            strategy_name="ema_crossover",
            exchange="binance",
            symbol="BTC/USDT",
            timeframe="1h",
            fast_period=3,
            slow_period=5,
        ),
        now=datetime(2026, 1, 1, 12, tzinfo=UTC),
    )

    assert stale_result.freshness_status == "stale"
    assert stale_result.readiness_status == "warning"

    session.close()


def test_market_data_coverage_service_uses_history_target_as_floor(tmp_path: Path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'market_data_coverage_target.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(settings)
    session = session_factory()

    first_open = datetime(2026, 1, 1, tzinfo=UTC)
    MarketDataService(session).store_candles(
        exchange="binance",
        symbol="ETH/USDT",
        timeframe="1h",
        candles=[
            CandleInput(
                open_time=first_open + timedelta(hours=index),
                close_time=first_open + timedelta(hours=index + 1),
                open_price=Decimal("2500.0"),
                high_price=Decimal("2510.0"),
                low_price=Decimal("2490.0"),
                close_price=Decimal("2505.0"),
                volume=Decimal("50"),
            )
            for index in range(200)
        ],
    )

    result = MarketDataCoverageService(session).get_coverage(
        options=BacktestRunOptions(
            strategy_name="ema_crossover",
            exchange="binance",
            symbol="ETH/USDT",
            timeframe="1h",
            fast_period=20,
            slow_period=50,
            history_candle_target=5000,
        ),
        now=datetime(2026, 1, 9, 10, tzinfo=UTC),
    )

    assert result.candle_count == 200
    assert result.required_candles == 5000
    assert result.additional_candles_needed == 4800
    assert result.satisfies_required_candles is False

    session.close()
