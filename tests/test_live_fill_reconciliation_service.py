from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

from app.application.services.live_fill_reconciliation_service import LiveFillReconciliationService
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.position import PositionRecord
from app.infrastructure.database.models.trade import TradeRecord
from app.infrastructure.database.repositories.order_repository import OrderRepository
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory
from app.infrastructure.exchanges.base import ExchangeOrderStatus


class FilledOrderClient:
    def __init__(self, *, side: str = "buy") -> None:
        self.side = side

    def fetch_order_status(
        self,
        *,
        symbol: str,
        client_order_id: str | None = None,
        exchange_order_id: str | None = None,
    ) -> ExchangeOrderStatus:
        del symbol
        return ExchangeOrderStatus(
            status="filled",
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id or "123",
            executed_quantity=Decimal("0.002"),
            average_fill_price=Decimal("50000"),
            response_payload={},
        )


class OpenOrderClient:
    def fetch_order_status(
        self,
        *,
        symbol: str,
        client_order_id: str | None = None,
        exchange_order_id: str | None = None,
    ) -> ExchangeOrderStatus:
        del symbol
        return ExchangeOrderStatus(
            status="new",
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id or "123",
            executed_quantity=Decimal("0"),
            average_fill_price=None,
            response_payload={},
        )


def build_session(tmp_path: Path) -> object:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'live_reconcile.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    return create_session_factory(settings)()


def test_reconciles_filled_live_buy_into_trade_and_position(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    try:
        order = OrderRepository(session).create(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            order_type="market",
            status="submitted",
            mode="live",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="live-buy-1",
            exchange_order_id="123",
        )
        session.commit()

        results = LiveFillReconciliationService(
            session,
            client=FilledOrderClient(),
        ).reconcile_recent_live_orders()

        trade_count = session.scalar(select(func.count()).select_from(TradeRecord))
        position = session.scalar(select(PositionRecord))

        assert len(results) == 1
        assert results[0].trade_created is True
        assert results[0].requires_operator_review is False
        assert trade_count == 1
        assert order.status == "filled"
        assert position is not None
        assert position.mode == "live"
        assert position.quantity == Decimal("0.00200000")
    finally:
        session.close()


def test_reconciliation_is_idempotent_for_already_reconciled_fill(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    try:
        order = OrderRepository(session).create(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            order_type="market",
            status="submitted",
            mode="live",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="live-buy-1",
            exchange_order_id="123",
        )
        service = LiveFillReconciliationService(session, client=FilledOrderClient())
        first = service.reconcile_recent_live_orders()
        second = service.reconcile_recent_live_orders()

        trade_count = session.scalar(select(func.count()).select_from(TradeRecord))

        assert first[0].trade_created is True
        assert second == []
        assert trade_count == 1
        assert order.status == "filled"
    finally:
        session.close()


def test_leaves_open_live_order_without_trade_creation(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    try:
        OrderRepository(session).create(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            order_type="market",
            status="submitted",
            mode="live",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="live-buy-1",
            exchange_order_id="123",
        )
        session.commit()

        results = LiveFillReconciliationService(
            session,
            client=OpenOrderClient(),
        ).reconcile_recent_live_orders()

        trade_count = session.scalar(select(func.count()).select_from(TradeRecord))

        assert results[0].status == "open"
        assert results[0].trade_created is False
        assert results[0].requires_operator_review is False
        assert trade_count == 0
    finally:
        session.close()


class FilledWithoutDetailsClient:
    def fetch_order_status(
        self,
        *,
        symbol: str,
        client_order_id: str | None = None,
        exchange_order_id: str | None = None,
    ) -> ExchangeOrderStatus:
        del symbol
        return ExchangeOrderStatus(
            status="filled",
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id or "123",
            executed_quantity=Decimal("0"),
            average_fill_price=None,
            response_payload={},
        )


def test_marks_order_review_required_when_exchange_fill_details_are_missing(
    tmp_path: Path,
) -> None:
    session = build_session(tmp_path)
    try:
        order = OrderRepository(session).create(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            order_type="market",
            status="submitted",
            mode="live",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="live-buy-review-1",
            exchange_order_id="123",
        )
        session.commit()

        results = LiveFillReconciliationService(
            session,
            client=FilledWithoutDetailsClient(),
        ).reconcile_recent_live_orders()

        trade_count = session.scalar(select(func.count()).select_from(TradeRecord))

        assert results[0].status == "review_required"
        assert results[0].trade_created is False
        assert results[0].requires_operator_review is True
        assert trade_count == 0
        assert order.status == "review_required"
    finally:
        session.close()
