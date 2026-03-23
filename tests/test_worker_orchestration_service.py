from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import func, select

from app.application.services.live_operator_control_service import LiveOperatorControlService
from app.application.services.market_data_service import CandleInput, MarketDataService
from app.application.services.market_data_sync_service import MarketDataSyncResult
from app.application.services.paper_execution_service import (
    PaperExecutionRequest,
    PaperExecutionService,
)
from app.application.services.worker_orchestration_service import WorkerOrchestrationService
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.trade import TradeRecord
from app.infrastructure.database.repositories.order_repository import DuplicateClientOrderIdError
from app.infrastructure.database.repositories.position_repository import PositionRepository
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def build_service(
    tmp_path: Path,
    **setting_overrides: object,
) -> tuple[WorkerOrchestrationService, object, Settings]:
    base_settings: dict[str, object] = {
        "DATABASE_URL": f"sqlite:///{tmp_path / 'worker_orchestration.db'}",
        "EXCHANGE_NAME": "binance",
        "DEFAULT_SYMBOL": "BTC/USDT",
        "DEFAULT_TIMEFRAME": "1h",
        "STRATEGY_FAST_PERIOD": 3,
        "STRATEGY_SLOW_PERIOD": 5,
        "MARKET_DATA_SYNC_ENABLED": False,
        "PAPER_ACCOUNT_EQUITY": 10000.0,
        "RISK_PER_TRADE_PCT": 0.01,
        "MAX_OPEN_POSITIONS": 1,
        "MAX_DAILY_LOSS_PCT": 0.03,
        "STRATEGY_ADX_FILTER_ENABLED": False,
    }
    base_settings.update(setting_overrides)
    settings = Settings(**base_settings)
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    return WorkerOrchestrationService(session, settings), session, settings


def store_closes(
    session: object,
    settings: Settings,
    closes: list[int],
) -> None:
    service = MarketDataService(session)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []
    for index, close in enumerate(closes):
        open_time = start + timedelta(hours=index)
        candles.append(
            CandleInput(
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open_price=Decimal(close),
                high_price=Decimal(close),
                low_price=Decimal(close),
                close_price=Decimal(close),
                volume=Decimal("1"),
            )
        )

    service.store_candles(
        exchange=settings.exchange_name,
        symbol=settings.default_symbol,
        timeframe=settings.default_timeframe,
        candles=candles,
    )


def test_executes_buy_signal_once_and_persists_client_order_id(tmp_path: Path) -> None:
    service, session, settings = build_service(tmp_path)
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

    result = service.run_cycle()

    order_count = session.scalar(select(func.count()).select_from(OrderRecord))
    trade_count = session.scalar(select(func.count()).select_from(TradeRecord))
    order = session.scalar(select(OrderRecord))

    assert result.status == "executed"
    assert result.signal_action == "buy"
    assert result.position_quantity == Decimal("5.00000000")
    assert order_count == 1
    assert trade_count == 1
    assert order is not None
    assert order.client_order_id == result.client_order_id


def test_skips_duplicate_signal_for_same_latest_candle(tmp_path: Path) -> None:
    service, session, settings = build_service(tmp_path)
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

    first = service.run_cycle()
    second = service.run_cycle()

    order_count = session.scalar(select(func.count()).select_from(OrderRecord))

    assert first.status == "executed"
    assert second.status == "duplicate_signal"
    assert order_count == 1


def test_executes_sell_signal_using_full_open_position_size(tmp_path: Path) -> None:
    service, session, settings = build_service(tmp_path)
    execution_service = PaperExecutionService(session)
    execution_service.execute(
        PaperExecutionRequest(
            exchange=settings.exchange_name,
            symbol=settings.default_symbol,
            side="buy",
            quantity=Decimal("0.50000000"),
            price=Decimal("20"),
        )
    )
    store_closes(session, settings, [20, 20, 20, 20, 20, 21, 21, 21, 5])

    result = service.run_cycle()

    latest_sell = session.scalar(select(OrderRecord).where(OrderRecord.side == "sell"))

    assert result.status == "executed"
    assert result.signal_action == "sell"
    assert result.position_quantity == Decimal("0E-8")
    assert latest_sell is not None
    assert latest_sell.quantity == Decimal("0.50000000")


def test_skips_sell_signal_when_no_open_position_exists(tmp_path: Path) -> None:
    service, session, settings = build_service(tmp_path)
    store_closes(session, settings, [20, 20, 20, 20, 20, 21, 21, 21, 5])

    result = service.run_cycle()

    order_count = session.scalar(select(func.count()).select_from(OrderRecord))

    assert result.status == "no_position"
    assert result.signal_action == "sell"
    assert order_count == 0


def test_rejects_buy_signal_after_daily_loss_limit_is_breached(tmp_path: Path) -> None:
    service, session, settings = build_service(tmp_path)
    positions = PositionRepository(session)
    positions.upsert(
        exchange=settings.exchange_name,
        symbol=settings.default_symbol,
        mode="paper",
        side="long",
        quantity=Decimal("0"),
        average_entry_price=None,
        realized_pnl=Decimal("-400"),
        unrealized_pnl=Decimal("0"),
    )
    session.commit()
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

    result = service.run_cycle()

    order_count = session.scalar(select(func.count()).select_from(OrderRecord))

    assert result.status == "risk_rejected"
    assert result.detail == "daily loss limit reached"
    assert result.risk_reason == "daily loss limit reached"
    assert order_count == 0


def test_rejects_live_entry_when_portfolio_concurrent_positions_limit_is_reached(
    tmp_path: Path,
) -> None:
    service, session, settings = build_service(
        tmp_path,
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_MAX_CONCURRENT_POSITIONS=1,
        MAX_OPEN_POSITIONS=5,
    )
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])
    PositionRepository(session).upsert(
        exchange=settings.exchange_name,
        symbol="ETH/USDT",
        mode="live",
        side="long",
        quantity=Decimal("1"),
        average_entry_price=Decimal("100"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
    )
    session.commit()

    with patch(
        "app.application.services.worker_orchestration_service.QualificationService"
    ) as mock_qual:
        mock_qual.return_value.evaluate.return_value = type("Report", (), {"all_passed": True})()
        result = service.run_cycle()

    order_count = session.scalar(select(func.count()).select_from(OrderRecord))

    assert result.status == "auto_halted"
    assert "live max concurrent positions reached" in result.detail
    assert result.risk_reason == "live max concurrent positions reached"
    assert order_count == 0


def test_rejects_live_entry_when_strategy_exposure_limit_is_reached(tmp_path: Path) -> None:
    service, session, settings = build_service(
        tmp_path,
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_MAX_STRATEGY_EXPOSURE_NOTIONAL=Decimal("150"),
        MAX_OPEN_POSITIONS=5,
    )
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])
    PositionRepository(session).upsert(
        exchange=settings.exchange_name,
        symbol="ETH/USDT",
        mode="live",
        side="long",
        quantity=Decimal("1"),
        average_entry_price=Decimal("120"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        strategy_name="ema_crossover",
    )
    session.commit()

    with patch(
        "app.application.services.worker_orchestration_service.QualificationService"
    ) as mock_qual:
        mock_qual.return_value.evaluate.return_value = type("Report", (), {"all_passed": True})()
        result = service.run_cycle()

    order_count = session.scalar(select(func.count()).select_from(OrderRecord))

    assert result.status == "auto_halted"
    assert "live strategy exposure exceeds configured limit" in result.detail
    assert result.risk_reason == "live strategy exposure exceeds configured limit"
    assert order_count == 0


def test_returns_no_signal_without_persisting_orders(tmp_path: Path) -> None:
    service, session, settings = build_service(tmp_path)
    store_closes(session, settings, [10, 11, 12, 13, 14, 15, 16, 17])

    result = service.run_cycle()

    order_count = session.scalar(select(func.count()).select_from(OrderRecord))

    assert result.status == "no_signal"
    assert order_count == 0


def test_returns_duplicate_signal_when_execution_hits_client_order_id_race(
    tmp_path: Path,
) -> None:
    service, session, settings = build_service(tmp_path)
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

    class DuplicateExecutionService:
        def execute(self, _request: PaperExecutionRequest) -> None:
            raise DuplicateClientOrderIdError("duplicate client_order_id")

    service._execution = DuplicateExecutionService()

    result = service.run_cycle()

    order_count = session.scalar(select(func.count()).select_from(OrderRecord))

    assert result.status == "duplicate_signal"
    assert result.signal_action == "buy"
    assert order_count == 0


def test_syncs_market_data_before_strategy_evaluation(tmp_path: Path) -> None:
    service, session, settings = build_service(tmp_path)
    synced = {"called": False}

    class SyncStub:
        def sync_recent_closed_candles(
            self,
            *,
            exchange: str,
            symbol: str,
            timeframe: str,
            limit: int,
        ) -> MarketDataSyncResult:
            synced["called"] = True
            assert exchange == settings.exchange_name
            assert symbol == settings.default_symbol
            assert timeframe == settings.default_timeframe
            assert limit == settings.market_data_sync_limit
            store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])
            return MarketDataSyncResult(
                fetched_count=9,
                stored_count=9,
                latest_open_time=datetime(2026, 1, 1, 8, tzinfo=UTC),
            )

    settings.market_data_sync_enabled = True
    service._market_sync = SyncStub()

    result = service.run_cycle()

    assert synced["called"] is True
    assert result.status == "executed"
    assert result.signal_action == "buy"


def test_skips_worker_cycle_when_market_data_sync_fails(tmp_path: Path) -> None:
    service, _session, settings = build_service(tmp_path)

    class FailingSyncStub:
        def sync_recent_closed_candles(
            self,
            *,
            exchange: str,
            symbol: str,
            timeframe: str,
            limit: int,
        ) -> MarketDataSyncResult:
            raise RuntimeError("boom")

    settings.market_data_sync_enabled = True
    service._market_sync = FailingSyncStub()

    result = service.run_cycle()

    assert result.status == "market_data_sync_failed"
    assert result.detail == "failed to sync market data"


def test_rejects_live_mode_when_no_live_execution_service_exists(tmp_path: Path) -> None:
    service, session, settings = build_service(
        tmp_path,
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    service._execution = type(
        "LiveExecutionStub",
        (),
        {
            "execute": lambda self, request: type(
                "ExecutionResult",
                (),
                {
                    "order": type("Order", (), {"id": 99})(),
                    "trade": None,
                    "position": None,
                },
            )(),
        },
    )()
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

    with patch(
        "app.application.services.worker_orchestration_service.QualificationService"
    ) as mock_svc:
        mock_svc.return_value.evaluate.return_value = MagicMock(all_passed=True)
        result = service.run_cycle()

    order_count = session.scalar(select(func.count()).select_from(OrderRecord))

    assert result.status == "submitted"
    assert result.detail == "signal submitted to live exchange"
    assert result.signal_action == "buy"
    assert result.trade_id is None
    assert order_count == 0


def test_rejects_live_buy_when_live_trading_is_halted(tmp_path: Path) -> None:
    service, session, settings = build_service(
        tmp_path,
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_TRADING_HALTED=True,
    )
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

    with patch(
        "app.application.services.worker_orchestration_service.QualificationService"
    ) as mock_svc:
        mock_svc.return_value.evaluate.return_value = MagicMock(all_passed=True)
        result = service.run_cycle()

    assert result.status == "risk_rejected"
    assert result.detail == "live trading is halted by configuration"


def test_rejects_live_buy_when_active_live_order_exists(tmp_path: Path) -> None:
    service, session, settings = build_service(
        tmp_path,
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    session.add(
        OrderRecord(
            exchange=settings.exchange_name,
            symbol=settings.default_symbol,
            side="buy",
            order_type="market",
            status="submitted",
            mode="live",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="existing-live-order-1",
            exchange_order_id="existing-exchange-1",
        )
    )
    session.commit()
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

    with patch(
        "app.application.services.worker_orchestration_service.QualificationService"
    ) as mock_svc:
        mock_svc.return_value.evaluate.return_value = MagicMock(all_passed=True)
        result = service.run_cycle()

    assert result.status == "duplicate_live_order"
    assert result.detail == "active live order already exists for the same market side"
    assert result.signal_action == "buy"


def test_rejects_live_buy_when_runtime_halt_override_is_enabled(tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'worker_orchestration.db'}",
        EXCHANGE_NAME="binance",
        DEFAULT_SYMBOL="BTC/USDT",
        DEFAULT_TIMEFRAME="1h",
        MARKET_DATA_SYNC_ENABLED=False,
        STRATEGY_FAST_PERIOD=3,
        STRATEGY_SLOW_PERIOD=5,
        PAPER_ACCOUNT_EQUITY=10000.0,
        RISK_PER_TRADE_PCT=0.01,
        MAX_OPEN_POSITIONS=1,
        MAX_DAILY_LOSS_PCT=0.03,
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_TRADING_HALTED=False,
        STRATEGY_ADX_FILTER_ENABLED=False,
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    LiveOperatorControlService(session, settings).set_live_trading_halted(
        halted=True,
        updated_by="test.worker",
    )
    session.commit()
    service = WorkerOrchestrationService(session, settings)
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

    with patch(
        "app.application.services.worker_orchestration_service.QualificationService"
    ) as mock_svc:
        mock_svc.return_value.evaluate.return_value = MagicMock(all_passed=True)
        result = service.run_cycle()

    assert result.status == "risk_rejected"
    assert result.detail == "live trading is halted by configuration"


def test_rejects_live_buy_when_order_notional_exceeds_limit(tmp_path: Path) -> None:
    service, session, settings = build_service(
        tmp_path,
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_MAX_ORDER_NOTIONAL=Decimal("50"),
    )
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

    with patch(
        "app.application.services.worker_orchestration_service.QualificationService"
    ) as mock_svc:
        mock_svc.return_value.evaluate.return_value = MagicMock(all_passed=True)
        result = service.run_cycle()

    assert result.status == "auto_halted"
    assert "critical risk violation" in result.detail
    assert "live order notional exceeds configured limit" in result.detail


def test_rejects_live_buy_when_position_quantity_exceeds_limit(tmp_path: Path) -> None:
    service, session, settings = build_service(
        tmp_path,
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_MAX_POSITION_QUANTITY=Decimal("4.00000000"),
    )
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

    with patch(
        "app.application.services.worker_orchestration_service.QualificationService"
    ) as mock_svc:
        mock_svc.return_value.evaluate.return_value = MagicMock(all_passed=True)
        result = service.run_cycle()

    assert result.status == "auto_halted"
    assert "critical risk violation" in result.detail
    assert "live position quantity exceeds configured limit" in result.detail


def test_rejects_live_mode_when_strategy_not_qualified(tmp_path: Path) -> None:
    service, session, settings = build_service(
        tmp_path,
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

    with patch(
        "app.application.services.worker_orchestration_service.QualificationService"
    ) as mock_svc:
        mock_svc.return_value.evaluate.return_value = MagicMock(all_passed=False)

        result = service.run_cycle()

        assert result.status == "not_qualified"
        assert "not passed all qualification gates" in result.detail


# ---------------------------------------------------------------------------
# Multi-symbol tests
# ---------------------------------------------------------------------------


def store_candles_for_symbol(
    session: object,
    settings: Settings,
    symbol: str,
    closes: list[int],
) -> None:
    svc = MarketDataService(session)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        CandleInput(
            open_time=start + timedelta(hours=i),
            close_time=start + timedelta(hours=i + 1),
            open_price=Decimal(c),
            high_price=Decimal(c),
            low_price=Decimal(c),
            close_price=Decimal(c),
            volume=Decimal("1"),
        )
        for i, c in enumerate(closes)
    ]
    svc.store_candles(
        exchange=settings.exchange_name,
        symbol=symbol,
        timeframe=settings.default_timeframe,
        candles=candles,
    )


def test_multi_symbol_single_entry_falls_through_to_single_cycle(tmp_path: Path) -> None:
    """When TRADING_SYMBOLS has one entry, behaves identically to single-symbol mode."""
    service, session, settings = build_service(
        tmp_path,
        TRADING_SYMBOLS="BTC/USDT",
    )
    store_closes(session, settings, [10, 10, 10, 10, 10, 9, 9, 9, 9])
    result = service.run_cycle()
    # No crossover signal yet; strategy should return no_signal
    assert result.status == "no_signal"


def test_multi_symbol_blocked_in_live_mode(tmp_path: Path) -> None:
    """Multi-symbol cycles must be blocked when execution_mode is live."""
    service, session, settings = build_service(
        tmp_path,
        TRADING_SYMBOLS="BTC/USDT,ETH/USDT",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    result = service.run_cycle()
    assert result.status == "multi_symbol_live_blocked"
    assert "not supported in live mode" in result.detail


def test_multi_symbol_processes_all_symbols(tmp_path: Path) -> None:
    """run_cycle processes every symbol in TRADING_SYMBOLS and returns multi_symbol_cycle."""
    service, session, settings = build_service(
        tmp_path,
        TRADING_SYMBOLS="BTC/USDT,ETH/USDT",
    )
    # Neither symbol has a signal — both cycles return no_signal
    store_candles_for_symbol(session, settings, "BTC/USDT", [10, 10, 10, 10, 10, 9, 9, 9, 9])
    store_candles_for_symbol(session, settings, "ETH/USDT", [10, 10, 10, 10, 10, 9, 9, 9, 9])
    result = service.run_cycle()
    assert result.status == "multi_symbol_cycle"
    assert "2 symbols" in result.detail
    assert "0 executed" in result.detail


def test_multi_symbol_active_symbols_defaults_to_default_symbol(tmp_path: Path) -> None:
    """_active_symbols falls back to [default_symbol] when TRADING_SYMBOLS is empty."""
    service, session, settings = build_service(tmp_path)
    assert service._active_symbols == ["BTC/USDT"]


def test_multi_symbol_active_symbols_returns_configured_list(tmp_path: Path) -> None:
    """_active_symbols returns all entries from TRADING_SYMBOLS."""
    service, session, settings = build_service(tmp_path, TRADING_SYMBOLS="BTC/USDT,ETH/USDT")
    assert service._active_symbols == ["BTC/USDT", "ETH/USDT"]


def test_multi_symbol_each_symbol_independent_no_position_cross_contamination(
    tmp_path: Path,
) -> None:
    """A buy signal on BTC/USDT must not open a position for ETH/USDT."""
    service, session, settings = build_service(
        tmp_path,
        TRADING_SYMBOLS="BTC/USDT,ETH/USDT",
    )
    # BTC crosses up (buy signal): slow EMA catches up then fast surges
    store_candles_for_symbol(session, settings, "BTC/USDT", [10, 10, 10, 10, 10, 9, 9, 9, 20])
    # ETH has no signal
    store_candles_for_symbol(session, settings, "ETH/USDT", [10, 10, 10, 10, 10, 9, 9, 9, 9])
    service.run_cycle()

    pos_repo = PositionRepository(session)
    btc_pos = pos_repo.get(
        exchange=settings.exchange_name,
        symbol="BTC/USDT",
        trading_mode=settings.trading_mode,
        mode="paper",
    )
    eth_pos = pos_repo.get(
        exchange=settings.exchange_name,
        symbol="ETH/USDT",
        trading_mode=settings.trading_mode,
        mode="paper",
    )
    # BTC should have a position; ETH should not
    assert btc_pos is not None and btc_pos.quantity > Decimal("0")
    assert eth_pos is None or eth_pos.quantity == Decimal("0")
