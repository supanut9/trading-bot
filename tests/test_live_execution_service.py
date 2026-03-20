from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.application.services.live_execution_service import (
    DuplicateLiveOrderError,
    InsufficientExpectedProfitError,
    LiveExecutionService,
)
from app.application.services.paper_execution_service import (
    PaperExecutionRequest,
)
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.trade import TradeRecord
from app.infrastructure.database.repositories.position_repository import PositionRepository
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory
from app.infrastructure.exchanges.base import ExchangeOrderSubmission


class RecordingLiveClient:
    def __init__(
        self,
        *,
        status: str = "submitted",
        exchange_order_id: str | None = "abc123",
    ) -> None:
        self.calls = []
        self._status = status
        self._exchange_order_id = exchange_order_id

    def submit_order(self, request) -> ExchangeOrderSubmission:
        self.calls.append(request)
        return ExchangeOrderSubmission(
            status=self._status,
            client_order_id=request.client_order_id,
            exchange_order_id=self._exchange_order_id,
            response_payload={"orderId": self._exchange_order_id}
            if self._exchange_order_id
            else {},
        )


def build_service(tmp_path: Path) -> tuple[LiveExecutionService, object]:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'live_execution.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    return LiveExecutionService(session, settings, client=RecordingLiveClient()), session


def test_submits_live_buy_and_persists_order_without_trade(tmp_path: Path) -> None:
    service, session = build_service(tmp_path)

    result = service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            mode="live",
            client_order_id="live-binance-btc-usdt-buy-1",
        )
    )

    trade_count = session.scalar(select(func.count()).select_from(TradeRecord))

    assert result.order.status == "submitted"
    assert result.order.exchange_order_id == "abc123"
    assert result.trade is None
    assert trade_count == 0


def test_submits_live_sell_against_existing_local_position(tmp_path: Path) -> None:
    service, session = build_service(tmp_path)
    PositionRepository(session).upsert(
        exchange="binance",
        symbol="BTC/USDT",
        mode="live",
        side="long",
        quantity=Decimal("0.003"),
        average_entry_price=Decimal("50000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
    )
    session.commit()

    result = service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("0.002"),
            price=Decimal("51000"),
            mode="live",
            client_order_id="live-binance-btc-usdt-sell-1",
        )
    )

    assert result.order.status == "submitted"
    assert result.position is not None
    assert result.position.quantity == Decimal("0.00300000")


def test_rejects_live_sell_without_existing_position(tmp_path: Path) -> None:
    service, session = build_service(tmp_path)

    with pytest.raises(ValueError, match="cannot execute sell without an existing position"):
        service.execute(
            PaperExecutionRequest(
                exchange="binance",
                symbol="BTC/USDT",
                side="sell",
                quantity=Decimal("0.001"),
                price=Decimal("51000"),
                mode="live",
            )
        )

    orders_count = session.scalar(select(func.count()).select_from(OrderRecord))
    assert orders_count == 0


def test_maps_exchange_new_submission_to_open_status(tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'live_execution_open.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    try:
        service = LiveExecutionService(
            session,
            settings,
            client=RecordingLiveClient(status="new"),
        )

        result = service.execute(
            PaperExecutionRequest(
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                quantity=Decimal("0.002"),
                price=Decimal("50000"),
                mode="live",
                client_order_id="live-binance-btc-usdt-buy-open",
            )
        )

        assert result.order.status == "open"
    finally:
        session.close()


def test_rejects_duplicate_live_buy_when_active_order_exists(tmp_path: Path) -> None:
    service, session = build_service(tmp_path)
    existing_order = OrderRecord(
        exchange="binance",
        symbol="BTC/USDT",
        side="buy",
        order_type="market",
        status="submitted",
        mode="live",
        quantity=Decimal("0.002"),
        price=Decimal("50000"),
        client_order_id="live-binance-btc-usdt-buy-existing",
        exchange_order_id="existing-1",
    )
    session.add(existing_order)
    session.commit()

    with pytest.raises(
        DuplicateLiveOrderError,
        match="active live order already exists for the same market side",
    ):
        service.execute(
            PaperExecutionRequest(
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                quantity=Decimal("0.002"),
                price=Decimal("50000"),
                mode="live",
                client_order_id="live-binance-btc-usdt-buy-duplicate",
            )
        )

    orders = session.scalars(select(OrderRecord).order_by(OrderRecord.id.asc())).all()
    assert len(orders) == 1
    assert orders[0].client_order_id == "live-binance-btc-usdt-buy-existing"


def test_blocks_order_with_insufficient_expected_profit(tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'live_fee_block.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_FEE_PCT=0.01,  # 1% fee (2% round trip)
        LIVE_EXPECTED_PROFIT_BPS=100,  # 1% expected profit
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    service = LiveExecutionService(session, settings, client=RecordingLiveClient())

    with pytest.raises(
        InsufficientExpectedProfitError, match="does not cover estimated round-trip fees"
    ):
        service.execute(
            PaperExecutionRequest(
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                quantity=Decimal("1.0"),
                price=Decimal("50000"),
                mode="live",
                client_order_id="insufficient-profit",
            )
        )


def test_converts_market_to_limit_with_offset(tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'live_limit_routing.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_ORDER_ROUTING_MODE="limit",
        LIVE_LIMIT_ORDER_OFFSET_BPS=20,  # 0.2%
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    client = RecordingLiveClient()
    service = LiveExecutionService(session, settings, client=client)

    service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("1.0"),
            price=Decimal("50000"),  # This will be signal_price
            mode="live",
            client_order_id="limit-conversion",
        )
    )

    # Signal price was 50000, 0.2% offset = 100
    # For buy, limit price = 50000 - 100 = 49900
    assert len(client.calls) == 1
    request = client.calls[0]
    assert request.order_type == "limit"
    assert request.price == Decimal("49900")
