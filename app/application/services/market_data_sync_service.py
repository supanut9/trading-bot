from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.application.services.market_data_service import CandleInput, MarketDataService
from app.core.logger import get_logger
from app.infrastructure.exchanges.base import ExchangeCandle, MarketDataExchangeClient

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MarketDataSyncResult:
    fetched_count: int
    stored_count: int
    latest_open_time: datetime | None


class MarketDataSyncService:
    def __init__(self, session: Session, client: MarketDataExchangeClient) -> None:
        self._market_data = MarketDataService(session)
        self._client = client

    def sync_recent_closed_candles(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> MarketDataSyncResult:
        logger.info(
            "market_data_sync_requested exchange=%s symbol=%s timeframe=%s limit=%s client=%s",
            exchange,
            symbol,
            timeframe,
            limit,
            self._client.name,
        )
        candles = self._client.fetch_closed_candles(symbol=symbol, timeframe=timeframe, limit=limit)
        if not candles:
            logger.warning(
                "market_data_sync_completed exchange=%s symbol=%s timeframe=%s fetched=0 stored=0",
                exchange,
                symbol,
                timeframe,
            )
            return MarketDataSyncResult(fetched_count=0, stored_count=0, latest_open_time=None)

        stored = self._market_data.store_candles(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            candles=[self._to_candle_input(candle) for candle in candles],
        )
        latest_open_time = max(candle.open_time for candle in candles)
        logger.info(
            "market_data_sync_completed exchange=%s symbol=%s timeframe=%s "
            "fetched=%s stored=%s latest_open_time=%s",
            exchange,
            symbol,
            timeframe,
            len(candles),
            len(stored),
            latest_open_time.isoformat(),
        )
        return MarketDataSyncResult(
            fetched_count=len(candles),
            stored_count=len(stored),
            latest_open_time=latest_open_time,
        )

    @staticmethod
    def _to_candle_input(candle: ExchangeCandle) -> CandleInput:
        return CandleInput(
            open_time=candle.open_time,
            close_time=candle.close_time,
            open_price=candle.open_price,
            high_price=candle.high_price,
            low_price=candle.low_price,
            close_price=candle.close_price,
            volume=candle.volume,
        )
