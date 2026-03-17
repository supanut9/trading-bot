from sqlalchemy.orm import Session

from app.application.services.paper_execution_service import PaperExecutionService
from app.config import Settings
from app.infrastructure.executions.base import ExecutionService
from app.infrastructure.executions.live_unavailable import UnsupportedLiveExecutionService


def build_execution_service(session: Session, settings: Settings) -> ExecutionService:
    if settings.execution_mode == "paper":
        return PaperExecutionService(session)
    return UnsupportedLiveExecutionService()
