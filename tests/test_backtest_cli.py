from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from app.application.services.market_data_service import CandleInput, MarketDataService
from app.application.services.market_data_sync_service import MarketDataSyncResult
from app.application.services.runtime_startup_service import build_runtime_startup_context
from app.backtest import main
from app.config import Settings, get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory

_SYNC_PATCH = (
    "app.application.services.market_data_sync_service.MarketDataSyncService.sync_candles_paginated"
)


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
    monkeypatch.setattr(
        "app.backtest.validate_runtime_startup",
        lambda _settings, component: build_runtime_startup_context(settings, component),
    )

    try:
        with patch(_SYNC_PATCH, return_value=MarketDataSyncResult(0, 0, None)):
            main()
    finally:
        get_settings.cache_clear()

    captured = capsys.readouterr()
    assert "backtest_skipped reason=not_enough_candles" in captured.err


def test_backtest_exits_early_when_runtime_startup_validation_fails(
    monkeypatch,
    capsys,
) -> None:
    settings = Settings()
    get_settings.cache_clear()
    monkeypatch.setattr("app.backtest.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.backtest.validate_runtime_startup",
        lambda _settings, _component: (_ for _ in ()).throw(
            RuntimeError("database connectivity check failed")
        ),
    )

    try:
        main()
    finally:
        get_settings.cache_clear()

    captured = capsys.readouterr()
    assert "runtime_startup_failed component=backtest" in captured.err
