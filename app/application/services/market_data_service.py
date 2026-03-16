from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.infrastructure.database.models.candle import CandleRecord
from app.infrastructure.database.repositories.candle_repository import CandleRepository

logger = get_logger(__name__)


@dataclass(slots=True)
class CandleInput:
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal


class MarketDataService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = CandleRepository(session)

    def store_candles(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        candles: Sequence[CandleInput],
    ) -> list[CandleRecord]:
        logger.info(
            "market_data_store_requested exchange=%s symbol=%s timeframe=%s count=%s",
            exchange,
            symbol,
            timeframe,
            len(candles),
        )
        stored: list[CandleRecord] = []
        for candle in candles:
            stored.append(
                self._repository.upsert(
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=candle.open_time,
                    close_time=candle.close_time,
                    open_price=candle.open_price,
                    high_price=candle.high_price,
                    low_price=candle.low_price,
                    close_price=candle.close_price,
                    volume=candle.volume,
                )
            )
        self._session.commit()
        logger.info(
            "market_data_store_completed exchange=%s symbol=%s timeframe=%s count=%s",
            exchange,
            symbol,
            timeframe,
            len(stored),
        )
        return stored

    def list_recent_candles(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> Sequence[CandleRecord]:
        candles = self._repository.list_recent(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
        logger.info(
            "market_data_list_recent exchange=%s symbol=%s timeframe=%s count=%s",
            exchange,
            symbol,
            timeframe,
            len(candles),
        )
        return candles

    def list_historical_candles(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> Sequence[CandleRecord]:
        candles = self._repository.list_all(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )
        logger.info(
            "market_data_list_historical exchange=%s symbol=%s timeframe=%s count=%s",
            exchange,
            symbol,
            timeframe,
            len(candles),
        )
        return candles
