from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.application.services.paper_execution_service import (
    PaperExecutionRequest,
    PaperExecutionService,
)
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
    get_session,
)
from app.main import app


def build_client(tmp_path: Path) -> tuple[TestClient, object]:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'operations_api.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()

    def override_get_session() -> object:
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    return client, session


def teardown_client(session: object) -> None:
    app.dependency_overrides.clear()
    session.close()


def seed_execution_data(session: object) -> None:
    service = PaperExecutionService(session)
    service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.50000000"),
            price=Decimal("20000"),
            submitted_reason="entry signal",
        )
    )
    service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("0.20000000"),
            price=Decimal("21000"),
            submitted_reason="exit signal",
        )
    )


def seed_multiple_trades(session: object, *, count: int) -> None:
    service = PaperExecutionService(session)
    for index in range(count):
        price = Decimal("20000") + Decimal(index)
        quantity = Decimal("0.01000000")
        service.execute(
            PaperExecutionRequest(
                exchange="binance",
                symbol=f"BTC/USDT-{index}",
                side="buy",
                quantity=quantity,
                price=price,
                submitted_reason=f"entry signal {index}",
            )
        )


def test_positions_endpoint_returns_persisted_positions(tmp_path: Path) -> None:
    client, session = build_client(tmp_path)
    try:
        seed_execution_data(session)

        response = client.get("/positions")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["exchange"] == "binance"
        assert payload[0]["symbol"] == "BTC/USDT"
        assert payload[0]["side"] == "long"
        assert payload[0]["mode"] == "paper"
        assert payload[0]["quantity"] == "0.30000000"
        assert payload[0]["average_entry_price"] == "20000.00000000"
        assert payload[0]["realized_pnl"] == "200.00000000"
    finally:
        teardown_client(session)


def test_trades_endpoint_returns_most_recent_trade_first(tmp_path: Path) -> None:
    client, session = build_client(tmp_path)
    try:
        seed_execution_data(session)

        response = client.get("/trades")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 2
        assert payload[0]["side"] == "sell"
        assert payload[0]["quantity"] == "0.20000000"
        assert payload[0]["price"] == "21000.00000000"
        assert payload[1]["side"] == "buy"
        assert payload[1]["quantity"] == "0.50000000"
    finally:
        teardown_client(session)


def test_trades_endpoint_applies_limit_query_parameter(tmp_path: Path) -> None:
    client, session = build_client(tmp_path)
    try:
        seed_multiple_trades(session, count=3)

        response = client.get("/trades?limit=2")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 2
        assert payload[0]["symbol"] == "BTC/USDT-2"
        assert payload[1]["symbol"] == "BTC/USDT-1"
    finally:
        teardown_client(session)
