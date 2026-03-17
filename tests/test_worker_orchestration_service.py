from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

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


def build_service(tmp_path: Path) -> tuple[WorkerOrchestrationService, object, Settings]:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'worker_orchestration.db'}",
        EXCHANGE_NAME="binance",
        DEFAULT_SYMBOL="BTC/USDT",
        DEFAULT_TIMEFRAME="1h",
        STRATEGY_FAST_PERIOD=3,
        STRATEGY_SLOW_PERIOD=5,
        PAPER_ACCOUNT_EQUITY=10000.0,
        RISK_PER_TRADE_PCT=0.01,
        MAX_OPEN_POSITIONS=1,
        MAX_DAILY_LOSS_PCT=0.03,
    )
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
            assert limit == 100
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
