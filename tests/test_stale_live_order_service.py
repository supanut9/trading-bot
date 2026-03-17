from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.application.services.stale_live_order_service import StaleLiveOrderService
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def build_session(tmp_path: Path):
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'stale_orders.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    return create_session_factory(settings)()


def test_lists_only_live_orders_older_than_threshold(tmp_path: Path) -> None:
    session = build_session(tmp_path)
    try:
        stale_time = datetime(2026, 1, 1, 10, tzinfo=UTC)
        fresh_time = stale_time + timedelta(minutes=90)
        session.add_all(
            [
                OrderRecord(
                    exchange="binance",
                    symbol="BTC/USDT",
                    side="buy",
                    order_type="market",
                    status="submitted",
                    mode="live",
                    quantity=Decimal("0.002"),
                    client_order_id="stale-order",
                    exchange_order_id="111",
                    created_at=stale_time,
                    updated_at=stale_time,
                ),
                OrderRecord(
                    exchange="binance",
                    symbol="BTC/USDT",
                    side="sell",
                    order_type="market",
                    status="submitted",
                    mode="live",
                    quantity=Decimal("0.001"),
                    client_order_id="fresh-order",
                    exchange_order_id="222",
                    created_at=fresh_time,
                    updated_at=fresh_time,
                ),
                OrderRecord(
                    exchange="binance",
                    symbol="BTC/USDT",
                    side="buy",
                    order_type="market",
                    status="filled",
                    mode="live",
                    quantity=Decimal("0.001"),
                    client_order_id="filled-order",
                    exchange_order_id="333",
                    created_at=stale_time,
                    updated_at=stale_time,
                ),
            ]
        )
        session.commit()

        service = StaleLiveOrderService(
            session,
            now_provider=lambda: datetime(2026, 1, 1, 12, tzinfo=UTC),
        )

        stale_orders = service.list_stale_orders(threshold_minutes=60)

        assert len(stale_orders) == 1
        assert stale_orders[0].client_order_id == "stale-order"
        assert stale_orders[0].age_minutes == 120
    finally:
        session.close()
