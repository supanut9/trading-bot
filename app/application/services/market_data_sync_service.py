from dataclasses import dataclass
from datetime import UTC, datetime

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
        backfill: bool = False,
    ) -> MarketDataSyncResult:
        logger.info(
            "market_data_sync_requested exchange=%s symbol=%s timeframe=%s limit=%s "
            "backfill=%s client=%s",
            exchange,
            symbol,
            timeframe,
            limit,
            backfill,
            self._client.name,
        )
        candles = self._client.fetch_closed_candles(symbol=symbol, timeframe=timeframe, limit=limit)
        latest_stored_open_time = self._latest_stored_open_time(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )
        if not candles:
            logger.warning(
                "market_data_sync_completed exchange=%s symbol=%s timeframe=%s fetched=0 stored=0",
                exchange,
                symbol,
                timeframe,
            )
            return MarketDataSyncResult(fetched_count=0, stored_count=0, latest_open_time=None)

        if backfill:
            new_candles = list(candles)
        else:
            new_candles = [
                candle
                for candle in candles
                if latest_stored_open_time is None
                or self._normalize_datetime(candle.open_time) > latest_stored_open_time
            ]
        if not new_candles:
            latest_open_time = max(candle.open_time for candle in candles)
            logger.info(
                "market_data_sync_completed exchange=%s symbol=%s timeframe=%s "
                "fetched=%s stored=0 latest_open_time=%s",
                exchange,
                symbol,
                timeframe,
                len(candles),
                latest_open_time.isoformat(),
            )
            return MarketDataSyncResult(
                fetched_count=len(candles),
                stored_count=0,
                latest_open_time=latest_open_time,
            )

        stored = self._market_data.store_candles(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            candles=[self._to_candle_input(candle) for candle in new_candles],
        )
        latest_open_time = max(candle.open_time for candle in new_candles)
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

    def sync_candles_paginated(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        total_limit: int,
        page_size: int = 1000,
    ) -> MarketDataSyncResult:
        """Fetch up to total_limit candles by paginating backwards in time."""
        all_candles: list[ExchangeCandle] = []
        end_time = None
        remaining = total_limit

        while remaining > 0:
            batch_size = min(remaining, page_size)
            candles = self._client.fetch_closed_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=batch_size,
                end_time=end_time,
            )
            if not candles:
                break
            all_candles.extend(candles)
            remaining -= len(candles)
            if len(candles) < batch_size:
                break  # exchange has no more historical data
            # paginate: next request must end before the oldest candle we have
            end_time = min(c.open_time for c in candles)

        if not all_candles:
            logger.info(
                "market_data_sync_paginated_completed exchange=%s symbol=%s timeframe=%s "
                "fetched=0 stored=0",
                exchange,
                symbol,
                timeframe,
            )
            return MarketDataSyncResult(fetched_count=0, stored_count=0, latest_open_time=None)

        stored = self._market_data.store_candles(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            candles=[self._to_candle_input(c) for c in all_candles],
        )
        latest_open_time = max(c.open_time for c in all_candles)
        logger.info(
            "market_data_sync_paginated_completed exchange=%s symbol=%s timeframe=%s "
            "fetched=%s stored=%s pages=%s latest_open_time=%s",
            exchange,
            symbol,
            timeframe,
            len(all_candles),
            len(stored),
            (total_limit + page_size - 1) // page_size,
            latest_open_time.isoformat(),
        )
        return MarketDataSyncResult(
            fetched_count=len(all_candles),
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

    def _latest_stored_open_time(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> datetime | None:
        latest = self._market_data.list_recent_candles(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            limit=1,
        )
        if not latest:
            return None
        return self._normalize_datetime(latest[0].open_time)

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
