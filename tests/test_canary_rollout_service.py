from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.application.services.audit_service import AuditEventView
from app.application.services.canary_rollout_service import CanaryRolloutService
from app.config import Settings


@pytest.fixture
def session():
    return MagicMock()


@pytest.fixture
def settings():
    return Settings(
        LIVE_TRADING_ENABLED=True,
        PAPER_TRADING=False,
        EXCHANGE_API_KEY="k",
        EXCHANGE_API_SECRET="s",
    )


def test_multiplier_starts_at_low_for_fresh_live_run(session, settings, monkeypatch):
    # Mock AuditService.list_recent to return one recent startup
    now = datetime.now(UTC)
    startup_event = AuditEventView(
        id=1,
        created_at=now - timedelta(minutes=5),
        event_type="system_startup",
        source="system",
        status="completed",
        detail="startup",
        exchange="binance",
        symbol="BTC/USDT",
        timeframe=None,
        channel=None,
        related_event_type=None,
        correlation_id=None,
        payload_json=None,
    )

    mock_audit = MagicMock()
    # First call for incidents (empty), second for risk (empty), third for startup
    mock_audit.list_recent.side_effect = [[], [], [startup_event]]

    monkeypatch.setattr(
        "app.application.services.canary_rollout_service.AuditService", lambda session: mock_audit
    )

    service = CanaryRolloutService(session, settings)
    multiplier = service.get_exposure_multiplier()

    # Very close to 0.1
    assert Decimal("0.1") <= multiplier < Decimal("0.11")


def test_multiplier_reaches_max_after_7_days(session, settings, monkeypatch):
    now = datetime.now(UTC)
    startup_event = AuditEventView(
        id=1,
        created_at=now - timedelta(days=8),
        event_type="system_startup",
        source="system",
        status="completed",
        detail="startup",
        exchange="binance",
        symbol="BTC/USDT",
        timeframe=None,
        channel=None,
        related_event_type=None,
        correlation_id=None,
        payload_json=None,
    )

    mock_audit = MagicMock()
    mock_audit.list_recent.side_effect = [[], [], [startup_event]]

    monkeypatch.setattr(
        "app.application.services.canary_rollout_service.AuditService", lambda session: mock_audit
    )

    service = CanaryRolloutService(session, settings)
    multiplier = service.get_exposure_multiplier()

    assert multiplier == Decimal("1.0000")


def test_multiplier_resets_on_recent_incident(session, settings, monkeypatch):
    now = datetime.now(UTC)
    startup_event = AuditEventView(
        id=1,
        created_at=now - timedelta(days=10),
        event_type="system_startup",
        source="system",
        status="completed",
        detail="startup",
        exchange="binance",
        symbol="BTC/USDT",
        timeframe=None,
        channel=None,
        related_event_type=None,
        correlation_id=None,
        payload_json=None,
    )
    incident_event = AuditEventView(
        id=2,
        created_at=now - timedelta(hours=1),
        event_type="exchange_error",
        source="system",
        status="failed",
        detail="api error",
        exchange="binance",
        symbol="BTC/USDT",
        timeframe=None,
        channel=None,
        related_event_type=None,
        correlation_id=None,
        payload_json=None,
    )

    mock_audit = MagicMock()
    # incidents (has one), risk (empty), startup (old)
    mock_audit.list_recent.side_effect = [[incident_event], [], [startup_event]]

    monkeypatch.setattr(
        "app.application.services.canary_rollout_service.AuditService", lambda session: mock_audit
    )

    service = CanaryRolloutService(session, settings)
    multiplier = service.get_exposure_multiplier()

    # Should be low because of recent incident (1 hour ago out of 168 hours)
    # 0.1 + 0.9 * (1/168) approx 0.1 + 0.005 approx 0.105
    assert Decimal("0.1") < multiplier < Decimal("0.12")
