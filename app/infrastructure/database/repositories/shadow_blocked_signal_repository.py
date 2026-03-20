from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.shadow_blocked_signal import ShadowBlockedSignalRecord


class ShadowBlockedSignalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        signal_action: str,
        signal_reason: str | None,
        block_reason: str,
        block_source: str,
        price: Decimal | None = None,
        client_order_id: str | None = None,
    ) -> ShadowBlockedSignalRecord:
        record = ShadowBlockedSignalRecord(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            signal_action=signal_action,
            signal_reason=signal_reason,
            block_reason=block_reason,
            block_source=block_source,
            price=price,
            client_order_id=client_order_id,
        )
        self._session.add(record)
        self._session.flush()
        return record

    def list_recent(
        self,
        *,
        exchange: str,
        symbol: str,
        limit: int = 50,
        block_source: str | None = None,
    ) -> list[ShadowBlockedSignalRecord]:
        stmt = (
            select(ShadowBlockedSignalRecord)
            .where(ShadowBlockedSignalRecord.exchange == exchange)
            .where(ShadowBlockedSignalRecord.symbol == symbol)
        )
        if block_source is not None:
            stmt = stmt.where(ShadowBlockedSignalRecord.block_source == block_source)
        stmt = stmt.order_by(ShadowBlockedSignalRecord.id.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars())
