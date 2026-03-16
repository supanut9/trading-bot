from fastapi import APIRouter, Depends, status

from app.application.services.operational_control_service import OperationalControlService
from app.config import Settings, get_settings
from app.interfaces.api.schemas import BacktestControlResponse, WorkerControlResponse

router = APIRouter(prefix="/controls", tags=["controls"])
settings_dependency = Depends(get_settings)


@router.post(
    "/worker-cycle",
    response_model=WorkerControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_worker_cycle(settings: Settings = settings_dependency) -> WorkerControlResponse:
    result = OperationalControlService(settings).run_worker_cycle()
    return WorkerControlResponse.model_validate(result)


@router.post(
    "/backtest",
    response_model=BacktestControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_backtest(settings: Settings = settings_dependency) -> BacktestControlResponse:
    result = OperationalControlService(settings).run_backtest()
    return BacktestControlResponse.model_validate(result)
