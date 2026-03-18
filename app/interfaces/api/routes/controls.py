from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session, sessionmaker

from app.application.services.operational_control_service import OperationalControlService
from app.config import Settings, get_settings
from app.infrastructure.database.session import get_session_factory_dependency
from app.interfaces.api.schemas import (
    BacktestControlResponse,
    LiveCancelControlRequest,
    LiveCancelControlResponse,
    LiveHaltControlRequest,
    LiveHaltControlResponse,
    LiveReconcileControlResponse,
    MarketSyncControlResponse,
    WorkerControlResponse,
)

router = APIRouter(prefix="/controls", tags=["controls"])
settings_dependency = Depends(get_settings)
session_factory_dependency = Depends(get_session_factory_dependency)


@router.post(
    "/worker-cycle",
    response_model=WorkerControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_worker_cycle(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> WorkerControlResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_worker_cycle(source="api.control")
    return WorkerControlResponse.model_validate(result)


@router.post(
    "/backtest",
    response_model=BacktestControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_backtest(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> BacktestControlResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_backtest(source="api.control")
    return BacktestControlResponse.model_validate(result)


@router.post(
    "/market-sync",
    response_model=MarketSyncControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_market_sync(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> MarketSyncControlResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_market_sync(source="api.control")
    return MarketSyncControlResponse.model_validate(result)


@router.post(
    "/live-reconcile",
    response_model=LiveReconcileControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_live_reconcile(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> LiveReconcileControlResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_live_reconcile(source="api.control")
    return LiveReconcileControlResponse.model_validate(result)


@router.post(
    "/live-halt",
    response_model=LiveHaltControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_live_halt(
    request: LiveHaltControlRequest,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> LiveHaltControlResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_live_halt(
        halted=request.halted,
        source="api.control",
    )
    return LiveHaltControlResponse.model_validate(result)


@router.post(
    "/live-cancel",
    response_model=LiveCancelControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_live_cancel(
    request: LiveCancelControlRequest,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> LiveCancelControlResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_live_cancel(
        order_id=request.order_id,
        client_order_id=request.client_order_id,
        exchange_order_id=request.exchange_order_id,
        source="api.control",
    )
    return LiveCancelControlResponse.model_validate(result)
