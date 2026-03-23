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


def build_settings(tmp_path: Path) -> Settings:
    return Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'live_reconcile.db'}")


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
    settings = build_settings(tmp_path)
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
            strategy_name="xgboost_signal",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="live-buy-1",
            exchange_order_id="123",
        )
        session.commit()

        results = LiveFillReconciliationService(
            session,
            build_settings(tmp_path),
            client=FilledOrderClient(),
        ).reconcile_recent_live_orders()

        trade_count = session.scalar(select(func.count()).select_from(TradeRecord))
        position = session.scalar(select(PositionRecord))
        trade = session.scalar(select(TradeRecord))

        assert len(results) == 1
        assert results[0].trade_created is True
        assert results[0].requires_operator_review is False
        assert trade_count == 1
        assert order.status == "filled"
        assert trade is not None
        assert trade.strategy_name == "xgboost_signal"
        assert position is not None
        assert position.mode == "live"
        assert position.strategy_name == "xgboost_signal"
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
        service = LiveFillReconciliationService(
            session,
            build_settings(tmp_path),
            client=FilledOrderClient(),
        )
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
            build_settings(tmp_path),
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
            build_settings(tmp_path),
            client=FilledWithoutDetailsClient(),
        ).reconcile_recent_live_orders()

        trade_count = session.scalar(select(func.count()).select_from(TradeRecord))

        assert results[0].requires_operator_review is True
        assert trade_count == 0
        assert order.status == "review_required"
    finally:
        session.close()


class PartialFillClient:
    def __init__(self, statuses: list[tuple[str, Decimal, Decimal]]) -> None:
        self.statuses = statuses
        self.call_count = 0

    def fetch_order_status(self, **kwargs) -> ExchangeOrderStatus:
        status, qty, price = self.statuses[self.call_count]
        self.call_count += 1
        return ExchangeOrderStatus(
            status=status,
            client_order_id=kwargs.get("client_order_id"),
            exchange_order_id=kwargs.get("exchange_order_id") or "123",
            executed_quantity=qty,
            average_fill_price=price,
            response_payload={},
        )


def test_reconciles_incremental_partial_fills(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    try:
        repo = OrderRepository(session)
        order = repo.create(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            status="submitted",
            mode="live",
            quantity=Decimal("10.0"),
            price=Decimal("50000"),
            client_order_id="partial-1",
        )
        session.commit()

        # Step 1: 4 BTC filled at 50,000
        client = PartialFillClient([("partially_filled", Decimal("4.0"), Decimal("50000"))])
        service = LiveFillReconciliationService(
            session,
            build_settings(tmp_path),
            client=client,
        )
        results1 = service.reconcile_recent_live_orders()

        assert results1[0].status == "partially_filled"
        assert results1[0].trade_created is True
        assert order.executed_quantity == Decimal("4.0")
        assert order.average_fill_price == Decimal("50000")

        trade1 = session.scalar(select(TradeRecord))
        assert trade1.quantity == Decimal("4.0")
        assert trade1.price == Decimal("50000")

        # Step 2: Total 10 BTC filled. New Avg = (4*50000 + 6*60000)/10 = 56000
        client.statuses = [("filled", Decimal("10.0"), Decimal("56000"))]
        client.call_count = 0
        results2 = service.reconcile_recent_live_orders()

        assert results2[0].status == "filled"
        assert results2[0].trade_created is True
        assert order.executed_quantity == Decimal("10.0")
        assert order.average_fill_price == Decimal("56000")

        # Verify second trade has the correct incremental price
        trades = session.scalars(select(TradeRecord).order_by(TradeRecord.id)).all()
        assert len(trades) == 2
        assert trades[1].quantity == Decimal("6.0")
        assert trades[1].price == Decimal("60000")  # (56000*10 - 50000*4)/6 = 60000

        # Verify position
        position = session.scalar(select(PositionRecord))
        assert position.quantity == Decimal("10.0")
        assert position.average_entry_price == Decimal("56000")
    finally:
        session.close()


def test_reconciles_partial_fill_before_cancellation(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    try:
        repo = OrderRepository(session)
        order = repo.create(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            status="submitted",
            mode="live",
            quantity=Decimal("10.0"),
            price=Decimal("50000"),
            client_order_id="cancel-partial-1",
        )
        session.commit()

        # Exchange says Canceled, but 2.0 were filled at 50,000
        client = PartialFillClient([("canceled", Decimal("2.0"), Decimal("50000"))])
        service = LiveFillReconciliationService(
            session,
            build_settings(tmp_path),
            client=client,
        )
        results = service.reconcile_recent_live_orders()

        assert results[0].status == "canceled"
        assert results[0].trade_created is True
        assert order.executed_quantity == Decimal("2.0")

        trade = session.scalar(select(TradeRecord))
        assert trade.quantity == Decimal("2.0")
        assert trade.price == Decimal("50000")
    finally:
        session.close()
