from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.application.services.live_execution_service import LiveExecutionService
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
    return LiveExecutionService(session, client=RecordingLiveClient()), session


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
