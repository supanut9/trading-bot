from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.candle import CandleRecord


class CandleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        open_time: datetime,
        close_time: datetime,
        open_price: Decimal,
        high_price: Decimal,
        low_price: Decimal,
        close_price: Decimal,
        volume: Decimal,
    ) -> CandleRecord:
        statement: Select[tuple[CandleRecord]] = select(CandleRecord).where(
            CandleRecord.exchange == exchange,
            CandleRecord.symbol == symbol,
            CandleRecord.timeframe == timeframe,
            CandleRecord.open_time == open_time,
        )
        record = self._session.execute(statement).scalar_one_or_none()
        if record is None:
            record = CandleRecord(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                open_time=open_time,
                close_time=close_time,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume,
            )
            self._session.add(record)
        else:
            record.close_time = close_time
            record.open_price = open_price
            record.high_price = high_price
            record.low_price = low_price
            record.close_price = close_price
            record.volume = volume
        self._session.flush()
        return record

    def list_recent(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> Sequence[CandleRecord]:
        statement: Select[tuple[CandleRecord]] = (
            select(CandleRecord)
            .where(
                CandleRecord.exchange == exchange,
                CandleRecord.symbol == symbol,
                CandleRecord.timeframe == timeframe,
            )
            .order_by(CandleRecord.open_time.desc())
            .limit(limit)
        )
        return self._session.execute(statement).scalars().all()
