from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.application.services.market_data_service import CandleInput, MarketDataService
from app.config import get_settings
from app.infrastructure.database.session import get_session
from app.interfaces.api.schemas import (
    CandleBatchIngestionRequest,
    CandleBatchIngestionResponse,
)

router = APIRouter(tags=["market-data"])
session_dependency = Depends(get_session)


@router.post(
    "/market-data/candles",
    response_model=CandleBatchIngestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_candles(
    payload: CandleBatchIngestionRequest,
    session: Session = session_dependency,
) -> CandleBatchIngestionResponse:
    settings = get_settings()
    exchange = payload.exchange or settings.exchange_name
    symbol = payload.symbol or settings.default_symbol
    timeframe = payload.timeframe or settings.default_timeframe
    service = MarketDataService(session)
    stored = service.store_candles(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        candles=[
            CandleInput(
                open_time=candle.open_time,
                close_time=candle.close_time,
                open_price=candle.open_price,
                high_price=candle.high_price,
                low_price=candle.low_price,
                close_price=candle.close_price,
                volume=candle.volume,
            )
            for candle in payload.candles
        ],
    )
    latest_open_time = max(candle.open_time for candle in stored)
    return CandleBatchIngestionResponse(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        stored_count=len(stored),
        latest_open_time=latest_open_time,
    )
