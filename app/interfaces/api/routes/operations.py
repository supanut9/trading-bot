from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.services.operations_service import OperationsService
from app.infrastructure.database.session import get_session
from app.interfaces.api.schemas import PositionResponse, TradeResponse

router = APIRouter(tags=["operations"])
session_dependency = Depends(get_session)


@router.get("/positions", response_model=list[PositionResponse])
def list_positions(session: Session = session_dependency) -> list[PositionResponse]:
    service = OperationsService(session)
    return [PositionResponse.model_validate(position) for position in service.list_positions()]


@router.get("/trades", response_model=list[TradeResponse])
def list_trades(session: Session = session_dependency) -> list[TradeResponse]:
    service = OperationsService(session)
    return [TradeResponse.model_validate(trade) for trade in service.list_trades()]
