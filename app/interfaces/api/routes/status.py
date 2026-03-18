from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.services.status_service import StatusService
from app.config import Settings, get_settings
from app.infrastructure.database.session import get_session
from app.interfaces.api.schemas import StatusResponse

router = APIRouter(tags=["status"])
settings_dependency = Depends(get_settings)
session_dependency = Depends(get_session)


@router.get("/status", response_model=StatusResponse)
def status(
    settings: Settings = settings_dependency,
    session: Session = session_dependency,
) -> StatusResponse:
    service = StatusService(settings, session=session)
    return StatusResponse.model_validate(service.get_status())
