from pathlib import Path
from unittest.mock import MagicMock

from app.application.services.live_incident_auto_halt_service import LiveIncidentAutoHaltService
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def build_settings(tmp_path: Path, threshold: int | None = None) -> Settings:
    return Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'halt_test.db'}",
        LIVE_TRADING_ENABLED=True,
        PAPER_TRADING=False,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_CONSECUTIVE_EXCHANGE_ERROR_AUTO_HALT_THRESHOLD=threshold,
    )


def make_session(tmp_path: Path, settings: Settings):
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    return create_session_factory(settings)()


def test_no_halt_when_threshold_not_configured(tmp_path: Path) -> None:
    settings = build_settings(tmp_path, threshold=None)
    session = make_session(tmp_path, settings)
    service = LiveIncidentAutoHaltService(session, settings)
    result = service.evaluate_and_halt_if_needed()
    assert result is False


def test_no_halt_when_below_threshold(tmp_path: Path, monkeypatch) -> None:
    settings = build_settings(tmp_path, threshold=3)
    session = make_session(tmp_path, settings)

    # Mock audit to return 2 failed events (below threshold of 3)
    mock_audit = MagicMock()
    failed_event = MagicMock()
    failed_event.status = "failed"
    mock_audit.list_recent.return_value = [failed_event, failed_event]

    monkeypatch.setattr(
        "app.application.services.live_incident_auto_halt_service.AuditService",
        lambda session: mock_audit,
    )

    # Create service AFTER patching so self._audit picks up the mock
    service = LiveIncidentAutoHaltService(session, settings)
    result = service.evaluate_and_halt_if_needed()
    assert result is False


def test_halts_when_threshold_reached(tmp_path: Path, monkeypatch) -> None:
    settings = build_settings(tmp_path, threshold=3)
    session = make_session(tmp_path, settings)

    # Mock audit to return exactly 3 consecutive failed events
    mock_audit = MagicMock()
    failed_event = MagicMock()
    failed_event.status = "failed"
    mock_audit.list_recent.return_value = [failed_event, failed_event, failed_event]

    mock_control = MagicMock()
    mock_control_instance = MagicMock()
    mock_control.return_value = mock_control_instance

    monkeypatch.setattr(
        "app.application.services.live_incident_auto_halt_service.AuditService",
        lambda session: mock_audit,
    )
    monkeypatch.setattr(
        "app.application.services.live_incident_auto_halt_service.LiveOperatorControlService",
        mock_control,
    )

    # Create service AFTER patching
    service = LiveIncidentAutoHaltService(session, settings)
    result = service.evaluate_and_halt_if_needed()
    assert result is True
    mock_control_instance.set_live_trading_halted.assert_called_once()
    call_kwargs = mock_control_instance.set_live_trading_halted.call_args.kwargs
    assert call_kwargs["halted"] is True
    assert "consecutive_exchange_error_auto_halt" in call_kwargs["reason"]


def test_no_halt_when_live_trading_disabled(tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'halt_test.db'}",
        LIVE_TRADING_ENABLED=False,
        PAPER_TRADING=True,
        LIVE_CONSECUTIVE_EXCHANGE_ERROR_AUTO_HALT_THRESHOLD=3,
    )
    session = make_session(tmp_path, settings)
    service = LiveIncidentAutoHaltService(session, settings)
    result = service.evaluate_and_halt_if_needed()
    assert result is False
