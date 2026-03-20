from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.shadow_trade import ShadowTradeRecord


class ShadowTradeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_open(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        side: str,
        signal_reason: str | None,
        entry_price: Decimal,
        simulated_fill_price: Decimal,
        quantity: Decimal,
        entry_fee: Decimal,
        client_order_id: str | None = None,
    ) -> ShadowTradeRecord:
        record = ShadowTradeRecord(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            side=side,
            signal_reason=signal_reason,
            entry_price=entry_price,
            simulated_fill_price=simulated_fill_price,
            quantity=quantity,
            entry_fee=entry_fee,
            status="open",
            client_order_id=client_order_id,
        )
        self._session.add(record)
        self._session.flush()
        return record

    def close_trade(
        self,
        record: ShadowTradeRecord,
        *,
        exit_price: Decimal,
        slippage_pct: Decimal,
        fee_pct: Decimal,
    ) -> ShadowTradeRecord:
        simulated_exit_fill_price = exit_price * (Decimal("1") - slippage_pct)
        exit_fee = simulated_exit_fill_price * record.quantity * fee_pct
        gross_pnl = (simulated_exit_fill_price - record.simulated_fill_price) * record.quantity
        net_pnl = gross_pnl - record.entry_fee - exit_fee
        record.simulated_exit_price = exit_price
        record.simulated_exit_fill_price = simulated_exit_fill_price
        record.exit_fee = exit_fee
        record.gross_pnl = gross_pnl
        record.net_pnl = net_pnl
        record.status = "closed"
        self._session.flush()
        return record

    def get_by_client_order_id(self, client_order_id: str) -> ShadowTradeRecord | None:
        stmt = select(ShadowTradeRecord).where(ShadowTradeRecord.client_order_id == client_order_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_open_trade(self, *, exchange: str, symbol: str) -> ShadowTradeRecord | None:
        stmt = (
            select(ShadowTradeRecord)
            .where(ShadowTradeRecord.exchange == exchange)
            .where(ShadowTradeRecord.symbol == symbol)
            .where(ShadowTradeRecord.status == "open")
            .order_by(ShadowTradeRecord.id.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def list_closed(
        self, *, exchange: str, symbol: str, limit: int = 100
    ) -> list[ShadowTradeRecord]:
        stmt = (
            select(ShadowTradeRecord)
            .where(ShadowTradeRecord.exchange == exchange)
            .where(ShadowTradeRecord.symbol == symbol)
            .where(ShadowTradeRecord.status == "closed")
            .order_by(ShadowTradeRecord.id.asc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars())

    def list_all(self, *, exchange: str, symbol: str, limit: int = 100) -> list[ShadowTradeRecord]:
        stmt = (
            select(ShadowTradeRecord)
            .where(ShadowTradeRecord.exchange == exchange)
            .where(ShadowTradeRecord.symbol == symbol)
            .order_by(ShadowTradeRecord.id.asc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars())
