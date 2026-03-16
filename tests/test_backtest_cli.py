from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.application.services.market_data_service import CandleInput, MarketDataService
from app.backtest import main
from app.config import Settings, get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def test_backtest_cli_logs_not_enough_candles_and_exits(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'backtest_cli.db'}",
        STRATEGY_FAST_PERIOD=3,
        STRATEGY_SLOW_PERIOD=5,
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()

    start = datetime(2026, 1, 1, tzinfo=UTC)
    MarketDataService(session).store_candles(
        exchange=settings.exchange_name,
        symbol=settings.default_symbol,
        timeframe=settings.default_timeframe,
        candles=[
            CandleInput(
                open_time=start,
                close_time=start + timedelta(hours=1),
                open_price=Decimal("100000"),
                high_price=Decimal("100100"),
                low_price=Decimal("99900"),
                close_price=Decimal("100050"),
                volume=Decimal("12.5"),
            )
        ],
    )
    session.close()

    get_settings.cache_clear()
    monkeypatch.setattr("app.backtest.get_settings", lambda: settings)

    try:
        main()
    finally:
        get_settings.cache_clear()

    captured = capsys.readouterr()
    assert "backtest_skipped reason=not_enough_candles" in captured.err
