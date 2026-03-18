import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.position import PositionRecord
from app.infrastructure.database.models.trade import TradeRecord
from app.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
    get_session,
)
from app.main import app


def build_client(tmp_path: Path):
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'performance_api.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()

    def override_get_session():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app), session


def teardown_client(session) -> None:
    app.dependency_overrides.clear()
    session.close()


def seed_trade(
    session,
    *,
    created_at: datetime,
    side: str,
    quantity: str,
    price: str,
    mode: str = "paper",
) -> None:
    order = OrderRecord(
        exchange="binance",
        symbol="BTC/USDT",
        side=side,
        order_type="market",
        status="filled",
        mode=mode,
        quantity=Decimal(quantity),
        price=Decimal(price),
        average_fill_price=Decimal(price),
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(order)
    session.flush()
    session.add(
        TradeRecord(
            order_id=order.id,
            exchange="binance",
            symbol="BTC/USDT",
            side=side,
            quantity=Decimal(quantity),
            price=Decimal(price),
            created_at=created_at,
            updated_at=created_at,
        )
    )


def test_performance_summary_endpoint_returns_mode_analytics(tmp_path: Path) -> None:
    client, session = build_client(tmp_path)
    try:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        seed_trade(session, created_at=start, side="buy", quantity="1.0", price="100")
        seed_trade(
            session,
            created_at=start + timedelta(hours=1),
            side="sell",
            quantity="1.0",
            price="110",
        )
        session.add(
            PositionRecord(
                exchange="binance",
                symbol="BTC/USDT",
                mode="paper",
                side="flat",
                quantity=Decimal("0"),
                average_entry_price=None,
                realized_pnl=Decimal("10"),
                unrealized_pnl=Decimal("0"),
                created_at=start,
                updated_at=start,
            )
        )
        session.commit()

        response = client.get("/performance/summary")

        assert response.status_code == 200
        payload = response.json()
        assert payload["summaries"][0]["mode"] == "paper"
        assert payload["summaries"][0]["trade_count"] == 2
        assert payload["summaries"][0]["closed_trade_count"] == 1
        assert payload["daily_rows"][0]["trade_count"] == 2
        assert len(payload["equity_curve"]) == 2
    finally:
        teardown_client(session)


def test_performance_daily_csv_exports_rows(tmp_path: Path) -> None:
    client, session = build_client(tmp_path)
    try:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        seed_trade(session, created_at=start, side="buy", quantity="1.0", price="100")
        seed_trade(
            session,
            created_at=start + timedelta(hours=1),
            side="sell",
            quantity="1.0",
            price="110",
        )
        session.commit()

        response = client.get("/performance/daily.csv")

        assert response.status_code == 200
        assert response.headers["content-disposition"] == (
            'attachment; filename="performance-daily.csv"'
        )
        rows = list(csv.DictReader(StringIO(response.text)))
        assert len(rows) == 1
        assert rows[0]["mode"] == "paper"
        assert rows[0]["trade_count"] == "2"
    finally:
        teardown_client(session)


def test_performance_equity_csv_exports_curve_points(tmp_path: Path) -> None:
    client, session = build_client(tmp_path)
    try:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        seed_trade(session, created_at=start, side="buy", quantity="1.0", price="100")
        seed_trade(
            session,
            created_at=start + timedelta(hours=1),
            side="sell",
            quantity="1.0",
            price="110",
        )
        session.commit()

        response = client.get("/performance/equity.csv")

        assert response.status_code == 200
        assert response.headers["content-disposition"] == (
            'attachment; filename="performance-equity.csv"'
        )
        rows = list(csv.DictReader(StringIO(response.text)))
        assert len(rows) == 2
        assert rows[0]["mode"] == "paper"
        assert Decimal(rows[-1]["net_pnl"]) == Decimal("10")
    finally:
        teardown_client(session)
