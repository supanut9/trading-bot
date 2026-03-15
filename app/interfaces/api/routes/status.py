from fastapi import APIRouter

from app.application.services.status_service import StatusService
from app.config import get_settings

router = APIRouter(tags=["status"])


@router.get("/status")
def status() -> dict[str, str | bool]:
    service = StatusService(get_settings())
    return service.get_status()
