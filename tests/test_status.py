from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.application.services.status_service import StatusService
from app.config import Settings, get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.operator_config import OperatorConfigRecord
from app.infrastructure.database.models.runtime_control import RuntimeControlRecord
from app.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
    get_session,
)
from app.main import app


def test_status_endpoint_returns_bootstrap_configuration(tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'status_bootstrap.db'}", PAPER_ACCOUNT_EQUITY=10000.0
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(settings)
    session = session_factory()

    def override_get_session():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = override_get_session

    try:
        client = TestClient(app)
        response = client.get("/status")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["app"] == "trading-bot"
    assert payload["execution_mode"] == "paper"
    assert payload["strategy_name"] == "ema_crossover"
    assert payload["paper_trading"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["live_trading_halted"] is False
    assert payload["live_safety_status"] == "disabled"
    assert payload["live_readiness_status"] == "blocked"
    assert payload["live_readiness_blocking_reasons"]
    assert payload["live_max_order_notional"] is None
    assert payload["live_max_position_quantity"] is None
    assert payload["database_status"] in {"available", "unavailable"}
    assert payload["latest_price_status"] in {"available", "unavailable"}
    assert payload["account_balance_status"] == "simulated"
    assert len(payload["account_balances"]) == 1
    assert payload["account_balances"][0]["asset"] == "USDT"
    assert "10000.0" in payload["account_balances"][0]["free"]


def test_status_endpoint_returns_live_account_balances_when_enabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'status_live.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_TRADING_HALTED=True,
        LIVE_MAX_ORDER_NOTIONAL=Decimal("250"),
        LIVE_MAX_POSITION_QUANTITY=Decimal("0.02000000"),
    )

    class FakeClient:
        def fetch_account_balances(self):
            from app.infrastructure.exchanges.base import ExchangeAssetBalance

            return [
                ExchangeAssetBalance(
                    asset="BTC",
                    free=Decimal("0.005"),
                    locked=Decimal("0.001"),
                ),
                ExchangeAssetBalance(
                    asset="USDT",
                    free=Decimal("250.00"),
                    locked=Decimal("0"),
                ),
                ExchangeAssetBalance(
                    asset="ETH",
                    free=Decimal("1.0"),
                    locked=Decimal("0"),
                ),
            ]

    class FakeMarketDataClient:
        def fetch_latest_price(self, *, symbol: str):
            from app.infrastructure.exchanges.base import ExchangeTickerPrice

            return ExchangeTickerPrice(symbol=symbol, price=Decimal("104321.55"))

    class FakeLiveReadinessService:
        def __init__(self, _session, _settings) -> None:
            pass

        def build_report(self):
            return type("Report", (), {"status": "ready", "blocking_reasons": []})()

    monkeypatch.setattr(
        "app.application.services.status_service.build_live_order_exchange_client",
        lambda _settings, **kwargs: FakeClient(),
    )
    monkeypatch.setattr(
        "app.application.services.status_service.build_market_data_exchange_client",
        lambda _settings: FakeMarketDataClient(),
    )
    monkeypatch.setattr(
        "app.application.services.status_service.LiveReadinessService",
        FakeLiveReadinessService,
    )

    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(settings)
    session = session_factory()

    def override_get_session():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = override_get_session

    try:
        client = TestClient(app)
        response = client.get("/status")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_mode"] == "live"
    assert payload["live_trading_halted"] is True
    assert payload["live_safety_status"] == "halted"
    assert payload["live_readiness_status"] == "ready"
    assert payload["live_readiness_blocking_reasons"] == []
    assert payload["live_max_order_notional"] == "250"
    assert payload["live_max_position_quantity"] == "0.02000000"
    assert payload["latest_price_status"] == "available"
    assert payload["latest_price"] == "104321.55"
    assert payload["account_balance_status"] == "available"
    assert payload["account_balances"] == [
        {"asset": "BTC", "free": "0.005", "locked": "0.001"},
        {"asset": "USDT", "free": "250.00", "locked": "0"},
    ]


def test_status_endpoint_prefers_runtime_halt_control_when_present(tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'status.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_TRADING_HALTED=False,
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(settings)
    session = session_factory()
    session.add(
        RuntimeControlRecord(
            control_name="live_trading_halted",
            bool_value=True,
            updated_by="test.status",
        )
    )
    session.commit()

    def override_get_session():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = override_get_session

    try:
        client = TestClient(app)
        response = client.get("/status")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["live_trading_halted"] is True
    assert payload["live_safety_status"] == "halted"


def test_status_endpoint_prefers_runtime_operator_config_when_present(tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'status_operator_config.db'}",
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(settings)
    session = session_factory()
    session.add(
        OperatorConfigRecord(
            config_name="paper_runtime_defaults",
            strategy_name="ema_crossover",
            symbol="ETH/USDT",
            timeframe="4h",
            fast_period=3,
            slow_period=5,
            updated_by="test.status",
        )
    )
    session.commit()

    def override_get_session():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = override_get_session

    try:
        client = TestClient(app)
        response = client.get("/status")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "ETH/USDT"
    assert payload["timeframe"] == "4h"
    assert payload["fast_period"] == 3
    assert payload["slow_period"] == 5
    assert payload["operator_config_source"] == "runtime_config"


def test_status_service_rolls_back_failed_runtime_control_lookup(monkeypatch) -> None:
    settings = Settings(LIVE_TRADING_HALTED=True)

    class FakeSession:
        def __init__(self) -> None:
            self.rollback_calls = 0

        def rollback(self) -> None:
            self.rollback_calls += 1

    def raise_sqlalchemy_error(self) -> SimpleNamespace:
        raise SQLAlchemyError("runtime control lookup failed")

    monkeypatch.setattr(
        "app.application.services.live_operator_control_service."
        "LiveOperatorControlService.get_live_trading_halt_state",
        raise_sqlalchemy_error,
    )

    session = FakeSession()
    halted = StatusService(settings, session=session)._effective_live_trading_halted()

    assert halted is True
    assert session.rollback_calls == 1
