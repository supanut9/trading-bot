from pathlib import Path

from app.application.services.execution_factory import build_execution_service
from app.application.services.paper_execution_service import PaperExecutionService
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory
from app.infrastructure.executions.live_unavailable import UnsupportedLiveExecutionService


def build_session(tmp_path: Path, **setting_overrides: object) -> tuple[object, Settings]:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'execution_factory.db'}",
        **setting_overrides,
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    return create_session_factory(settings)(), settings


def test_builds_paper_execution_service_for_paper_mode(tmp_path: Path) -> None:
    session, settings = build_session(tmp_path)
    try:
        service = build_execution_service(session, settings)

        assert isinstance(service, PaperExecutionService)
    finally:
        session.close()


def test_builds_unsupported_live_execution_service_for_live_mode(tmp_path: Path) -> None:
    session, settings = build_session(
        tmp_path,
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
    )
    try:
        service = build_execution_service(session, settings)

        assert isinstance(service, UnsupportedLiveExecutionService)
    finally:
        session.close()
