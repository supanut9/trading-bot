from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.order_rules import SymbolRules
from app.infrastructure.database.models.symbol_rules import SymbolRulesRecord


class SymbolRulesRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_latest(self, *, exchange: str, symbol: str) -> SymbolRulesRecord | None:
        stmt = (
            select(SymbolRulesRecord)
            .where(SymbolRulesRecord.exchange == exchange)
            .where(SymbolRulesRecord.symbol == symbol)
            .order_by(SymbolRulesRecord.fetched_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        *,
        exchange: str,
        symbol: str,
        min_qty: Decimal,
        max_qty: Decimal,
        step_size: Decimal,
        min_notional: Decimal,
        tick_size: Decimal,
    ) -> SymbolRulesRecord:
        existing = self.get_latest(exchange=exchange, symbol=symbol)
        if existing is not None:
            existing.min_qty = min_qty
            existing.max_qty = max_qty
            existing.step_size = step_size
            existing.min_notional = min_notional
            existing.tick_size = tick_size
            existing.fetched_at = datetime.now(UTC)
            self._session.flush()
            return existing
        record = SymbolRulesRecord(
            exchange=exchange,
            symbol=symbol,
            min_qty=min_qty,
            max_qty=max_qty,
            step_size=step_size,
            min_notional=min_notional,
            tick_size=tick_size,
            fetched_at=datetime.now(UTC),
        )
        self._session.add(record)
        self._session.flush()
        return record

    def to_domain(self, record: SymbolRulesRecord) -> SymbolRules:
        return SymbolRules(
            exchange=record.exchange,
            symbol=record.symbol,
            min_qty=Decimal(str(record.min_qty)),
            max_qty=Decimal(str(record.max_qty)),
            step_size=Decimal(str(record.step_size)),
            min_notional=Decimal(str(record.min_notional)),
            tick_size=Decimal(str(record.tick_size)),
        )
