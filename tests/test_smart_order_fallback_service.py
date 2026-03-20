from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.application.services.smart_order_fallback_service import SmartOrderFallbackService
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.repositories.order_repository import OrderRepository
from app.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
)
from app.infrastructure.exchanges.base import (
    ExchangeOrderCancellation,
    ExchangeOrderSubmission,
    LiveOrderExchangeClient,
)


@pytest.fixture
def session(tmp_path) -> Session:
    # Use a dummy settings for engine creation
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'fallback.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        _env_file=None,
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(settings)
    session = session_factory()
    yield session
    session.close()


def get_test_settings() -> Settings:
    s = Settings(
        paper_trading=False,
        live_trading_enabled=True,
        live_order_routing_mode="limit",
        live_limit_order_timeout_seconds=60,
        exchange_api_key="key",
        exchange_api_secret="secret",
        _env_file=None,
    )
    # FORCING AGAIN JUST IN CASE
    s.live_trading_enabled = True
    s.live_order_routing_mode = "limit"
    return s


@pytest.fixture
def client() -> MagicMock:
    return MagicMock(spec=LiveOrderExchangeClient)


def test_process_fallbacks_skips_if_disabled(session: Session, client: MagicMock):
    settings = get_test_settings()
    settings.live_trading_enabled = False
    service = SmartOrderFallbackService(session, settings, client=client)
    assert service.process_fallbacks() == 0
    client.cancel_order.assert_not_called()


def test_process_fallbacks_cancels_and_reorders(session: Session, client: MagicMock):
    settings = get_test_settings()
    repo = OrderRepository(session)

    # Create an old limit order
    old_order = repo.create(
        exchange="binance",
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        status="open",
        mode="live",
        quantity=Decimal("1.0"),
        price=Decimal("50000"),
        signal_price=Decimal("50010"),
        client_order_id="old-order",
    )

    # Manually set created_at to be old.
    # Must also set updated_at because list_live_orders_by_status orders by updated_at.
    now = datetime.now(UTC)
    old_time = now - timedelta(seconds=120)
    old_order.created_at = old_time
    old_order.updated_at = old_time
    session.commit()

    # Mock cancellation and re-submission
    client.cancel_order.return_value = ExchangeOrderCancellation(
        status="canceled",
        client_order_id="old-order",
        exchange_order_id="ex-123",
        response_payload={},
    )
    client.submit_order.return_value = ExchangeOrderSubmission(
        status="submitted",
        client_order_id="old-order-fb",
        exchange_order_id="ex-456",
        response_payload={},
    )

    service = SmartOrderFallbackService(session, settings, client=client)
    count = service.process_fallbacks()

    assert count == 1
    assert old_order.status == "canceled"

    # Check if fallback order was created
    fallback_order = repo.get_by_client_order_id("old-order-fb")
    assert fallback_order is not None
    assert fallback_order.order_type == "market"
    assert fallback_order.status == "submitted"
    assert fallback_order.signal_price == Decimal("50010")


def test_process_fallbacks_skips_recent_orders(session: Session, client: MagicMock):
    settings = get_test_settings()
    repo = OrderRepository(session)
    # Create a recent limit order
    repo.create(
        exchange="binance",
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        status="open",
        mode="live",
        quantity=Decimal("1.0"),
        price=Decimal("50000"),
        signal_price=Decimal("50010"),
        client_order_id="recent-order",
    )
    session.commit()

    service = SmartOrderFallbackService(session, settings, client=client)
    count = service.process_fallbacks()

    assert count == 0
    client.cancel_order.assert_not_called()
