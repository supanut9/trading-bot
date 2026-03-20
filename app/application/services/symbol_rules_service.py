from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.order_rules import SymbolRules
from app.infrastructure.database.repositories.symbol_rules_repository import (
    SymbolRulesRepository,
)
from app.infrastructure.exchanges.base import MarketDataExchangeClient


@dataclass(frozen=True, slots=True)
class SymbolRulesResult:
    exchange: str
    symbol: str
    min_qty: Decimal
    max_qty: Decimal
    step_size: Decimal
    min_notional: Decimal
    tick_size: Decimal
    fetched_at: str
    source: str


class SymbolRulesService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = SymbolRulesRepository(session)

    def get_rules(self, *, exchange: str, symbol: str) -> SymbolRules | None:
        record = self._repo.get_latest(exchange=exchange, symbol=symbol)
        if record is None:
            return None
        return SymbolRules(
            exchange=record.exchange,
            symbol=record.symbol,
            min_qty=Decimal(str(record.min_qty)),
            max_qty=Decimal(str(record.max_qty)),
            step_size=Decimal(str(record.step_size)),
            min_notional=Decimal(str(record.min_notional)),
            tick_size=Decimal(str(record.tick_size)),
        )

    def refresh_rules(
        self,
        *,
        exchange_client: MarketDataExchangeClient,
        exchange: str,
        symbol: str,
    ) -> SymbolRulesResult:
        fetched = exchange_client.fetch_symbol_rules(symbol=symbol)
        record = self._repo.upsert(
            exchange=exchange,
            symbol=symbol,
            min_qty=fetched.min_qty,
            max_qty=fetched.max_qty,
            step_size=fetched.step_size,
            min_notional=fetched.min_notional,
            tick_size=fetched.tick_size,
        )
        return SymbolRulesResult(
            exchange=record.exchange,
            symbol=record.symbol,
            min_qty=Decimal(str(record.min_qty)),
            max_qty=Decimal(str(record.max_qty)),
            step_size=Decimal(str(record.step_size)),
            min_notional=Decimal(str(record.min_notional)),
            tick_size=Decimal(str(record.tick_size)),
            fetched_at=record.fetched_at.isoformat(),
            source="exchange",
        )

    def get_rules_result(self, *, exchange: str, symbol: str) -> SymbolRulesResult | None:
        record = self._repo.get_latest(exchange=exchange, symbol=symbol)
        if record is None:
            return None
        return SymbolRulesResult(
            exchange=record.exchange,
            symbol=record.symbol,
            min_qty=Decimal(str(record.min_qty)),
            max_qty=Decimal(str(record.max_qty)),
            step_size=Decimal(str(record.step_size)),
            min_notional=Decimal(str(record.min_notional)),
            tick_size=Decimal(str(record.tick_size)),
            fetched_at=record.fetched_at.isoformat(),
            source="database",
        )
