from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.application.services.demo_scenario_service import (
    DemoScenarioService,
    UnknownDemoScenarioError,
)
from app.application.services.market_data_service import CandleInput, MarketDataService
from app.config import get_settings
from app.infrastructure.database.session import get_session
from app.interfaces.api.schemas import (
    CandleBatchIngestionRequest,
    CandleBatchIngestionResponse,
    DemoScenarioLoadResponse,
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
    candle_inputs = [
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
    ]
    latest_open_time = max(candle.open_time for candle in candle_inputs)
    stored = service.store_candles(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        candles=candle_inputs,
    )
    return CandleBatchIngestionResponse(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        stored_count=len(stored),
        latest_open_time=latest_open_time,
    )


@router.post(
    "/market-data/demo-scenarios/{scenario_name}",
    response_model=DemoScenarioLoadResponse,
    status_code=status.HTTP_201_CREATED,
)
def load_demo_scenario(
    scenario_name: str,
    session: Session = session_dependency,
) -> DemoScenarioLoadResponse:
    settings = get_settings()
    try:
        result = DemoScenarioService(MarketDataService(session)).load(
            scenario_name=scenario_name,
            exchange=settings.exchange_name,
            symbol=settings.default_symbol,
            timeframe=settings.default_timeframe,
        )
    except UnknownDemoScenarioError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return DemoScenarioLoadResponse(
        scenario=result.scenario,
        detail=result.detail,
        exchange=result.exchange,
        symbol=result.symbol,
        timeframe=result.timeframe,
        candle_count=result.candle_count,
        stored_count=result.stored_count,
        latest_open_time=result.latest_open_time,
        expected_signal_action=result.expected_signal_action,
    )
