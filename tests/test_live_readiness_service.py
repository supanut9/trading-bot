from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.application.services.live_readiness_service import LiveReadinessService
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.symbol_rules import SymbolRulesRecord
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def build_session(tmp_path: Path, settings: Settings):
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    return create_session_factory(settings)()


def seed_symbol_rules(session, *, exchange: str, symbol: str) -> None:
    session.add(
        SymbolRulesRecord(
            exchange=exchange,
            symbol=symbol,
            min_qty=Decimal("0.001"),
            max_qty=Decimal("100"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("10"),
            tick_size=Decimal("0.01"),
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.commit()


def test_live_readiness_ready_when_all_checks_pass(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'live_readiness_ready.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_TRADING_HALTED=False,
        LIVE_RECONCILE_SCHEDULE_ENABLED=True,
        STARTUP_STATE_SYNC_ENABLED=True,
        LIVE_MAX_ORDER_NOTIONAL=Decimal("100"),
        LIVE_MAX_POSITION_QUANTITY=Decimal("0.01"),
        STALE_LIVE_ORDER_THRESHOLD_MINUTES=60,
    )
    session = build_session(tmp_path, settings)
    try:
        seed_symbol_rules(session, exchange=settings.exchange_name, symbol=settings.default_symbol)

        class FakeQualificationService:
            def __init__(self, _session) -> None:
                pass

            def evaluate(self, *, exchange: str, symbol: str):
                return type("Report", (), {"all_passed": True})()

        monkeypatch.setattr(
            "app.application.services.live_readiness_service.QualificationService",
            FakeQualificationService,
        )

        report = LiveReadinessService(session, settings).build_report()

        assert report.ready is True
        assert report.status == "ready"
        assert report.blocking_reasons == []
        assert all(check.passed for check in report.checks)
        assert any(
            check.name == "live_recovery_posture"
            and check.detail == "live recovery posture is clear"
            for check in report.checks
        )
    finally:
        session.close()


def test_live_readiness_reports_blocking_reasons(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'live_readiness_blocked.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_TRADING_HALTED=False,
        LIVE_RECONCILE_SCHEDULE_ENABLED=False,
        STARTUP_STATE_SYNC_ENABLED=False,
        LIVE_MAX_ORDER_NOTIONAL=None,
        LIVE_MAX_POSITION_QUANTITY=None,
        STALE_LIVE_ORDER_THRESHOLD_MINUTES=60,
    )
    session = build_session(tmp_path, settings)
    try:
        session.add(
            OrderRecord(
                exchange=settings.exchange_name,
                symbol=settings.default_symbol,
                side="buy",
                order_type="market",
                status="review_required",
                mode="live",
                quantity=Decimal("0.001"),
                created_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
                updated_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
            )
        )
        session.add(
            OrderRecord(
                exchange=settings.exchange_name,
                symbol=settings.default_symbol,
                side="sell",
                order_type="market",
                status="submitted",
                mode="live",
                quantity=Decimal("0.001"),
                client_order_id="stale-live-order",
                created_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
                updated_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
            )
        )
        session.commit()

        class FakeQualificationService:
            def __init__(self, _session) -> None:
                pass

            def evaluate(self, *, exchange: str, symbol: str):
                return type("Report", (), {"all_passed": False})()

        monkeypatch.setattr(
            "app.application.services.live_readiness_service.QualificationService",
            FakeQualificationService,
        )
        report = LiveReadinessService(session, settings).build_report()

        assert report.ready is False
        assert report.status == "blocked"
        assert any("qualification gates" in reason for reason in report.blocking_reasons)
        assert any("symbol rules" in reason for reason in report.blocking_reasons)
        assert any(
            "live recovery posture is blocked" in reason for reason in report.blocking_reasons
        )
        assert any("manual exchange-state review" in reason for reason in report.blocking_reasons)
        assert any("max order notional" in reason for reason in report.blocking_reasons)
    finally:
        session.close()
