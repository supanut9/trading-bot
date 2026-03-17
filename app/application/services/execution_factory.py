from sqlalchemy.orm import Session

from app.application.services.live_execution_service import LiveExecutionService
from app.application.services.paper_execution_service import PaperExecutionService
from app.config import Settings
from app.infrastructure.exchanges.factory import build_live_order_exchange_client
from app.infrastructure.executions.base import ExecutionService


def build_execution_service(session: Session, settings: Settings) -> ExecutionService:
    if settings.execution_mode == "paper":
        return PaperExecutionService(session)
    return LiveExecutionService(
        session,
        client=build_live_order_exchange_client(settings),
    )
