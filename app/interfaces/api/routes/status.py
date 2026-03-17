from fastapi import APIRouter, Depends

from app.application.services.status_service import StatusService
from app.config import Settings, get_settings
from app.interfaces.api.schemas import StatusResponse

router = APIRouter(tags=["status"])
settings_dependency = Depends(get_settings)


@router.get("/status", response_model=StatusResponse)
def status(settings: Settings = settings_dependency) -> StatusResponse:
    service = StatusService(settings)
    return StatusResponse.model_validate(service.get_status())
