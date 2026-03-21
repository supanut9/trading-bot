from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.trade import TradeRecord


@dataclass(frozen=True, slots=True)
class TradeAnalyticsRow:
    id: int
    created_at: datetime
    exchange: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee_amount: Decimal | None
    mode: str


class TradeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self, *, limit: int = 100) -> list[TradeRecord]:
        statement: Select[tuple[TradeRecord]] = (
            select(TradeRecord)
            .order_by(
                TradeRecord.created_at.desc(),
                TradeRecord.id.desc(),
            )
            .limit(limit)
        )
        return self._session.execute(statement).scalars().all()

    def list_by_order_id(self, order_id: int) -> list[TradeRecord]:
        statement: Select[tuple[TradeRecord]] = select(TradeRecord).where(
            TradeRecord.order_id == order_id
        )
        return self._session.execute(statement).scalars().all()

    def list_analytics_rows(self) -> list[TradeAnalyticsRow]:
        statement = (
            select(TradeRecord, OrderRecord.mode)
            .join(OrderRecord, OrderRecord.id == TradeRecord.order_id, isouter=True)
            .order_by(TradeRecord.created_at.asc(), TradeRecord.id.asc())
        )
        return [
            TradeAnalyticsRow(
                id=trade.id,
                created_at=trade.created_at,
                exchange=trade.exchange,
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
                price=trade.price,
                fee_amount=trade.fee_amount,
                mode=mode or "paper",
            )
            for trade, mode in self._session.execute(statement).all()
        ]

    def create(
        self,
        *,
        exchange: str,
        symbol: str,
        trading_mode: str = "SPOT",
        side: str,
        quantity: Decimal,
        price: Decimal,
        order_id: int | None = None,
        realized_pnl: Decimal | None = None,
        fee_amount: Decimal | None = None,
        fee_asset: str | None = None,
    ) -> TradeRecord:
        record = TradeRecord(
            order_id=order_id,
            exchange=exchange,
            symbol=symbol,
            trading_mode=trading_mode,
            side=side,
            quantity=quantity,
            price=price,
            realized_pnl=realized_pnl,
            fee_amount=fee_amount,
            fee_asset=fee_asset,
        )

        self._session.add(record)
        self._session.flush()
        return record

    def get_realized_pnl_sum(
        self,
        *,
        exchange: str,
        symbol: str,
        mode: str,
        since: datetime,
    ) -> Decimal:
        statement = (
            select(TradeRecord.realized_pnl)
            .join(OrderRecord, OrderRecord.id == TradeRecord.order_id)
            .where(
                TradeRecord.exchange == exchange,
                TradeRecord.symbol == symbol,
                OrderRecord.mode == mode,
                TradeRecord.realized_pnl.isnot(None),
                TradeRecord.created_at >= since,
            )
        )
        pnl_values = self._session.execute(statement).scalars().all()
        return sum(pnl_values, Decimal("0"))

    def get_consecutive_losses(
        self,
        *,
        exchange: str,
        symbol: str,
        mode: str,
    ) -> int:
        statement = (
            select(TradeRecord.realized_pnl)
            .join(OrderRecord, OrderRecord.id == TradeRecord.order_id)
            .where(
                TradeRecord.exchange == exchange,
                TradeRecord.symbol == symbol,
                OrderRecord.mode == mode,
                TradeRecord.realized_pnl.isnot(None),
            )
            .order_by(TradeRecord.created_at.desc(), TradeRecord.id.desc())
            .limit(20)
        )
        pnl_values = self._session.execute(statement).scalars().all()
        count: int = 0
        for pnl in pnl_values:
            if pnl is not None:
                val: Decimal = pnl
                if val < Decimal("0"):
                    count += 1
                elif val >= Decimal("0"):
                    break
        return count
