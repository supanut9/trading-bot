from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.trade import TradeRecord


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

    def create(
        self,
        *,
        exchange: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        order_id: int | None = None,
        fee_amount: Decimal | None = None,
        fee_asset: str | None = None,
    ) -> TradeRecord:
        record = TradeRecord(
            order_id=order_id,
            exchange=exchange,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            fee_amount=fee_amount,
            fee_asset=fee_asset,
        )
        self._session.add(record)
        self._session.flush()
        return record
