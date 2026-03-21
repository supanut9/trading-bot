from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.position import PositionRecord


class PositionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self,
        *,
        exchange: str,
        symbol: str,
        trading_mode: str = "SPOT",
        mode: str,
    ) -> PositionRecord | None:
        statement: Select[tuple[PositionRecord]] = select(PositionRecord).where(
            PositionRecord.exchange == exchange,
            PositionRecord.symbol == symbol,
            PositionRecord.trading_mode == trading_mode,
            PositionRecord.mode == mode,
        )
        return self._session.execute(statement).scalar_one_or_none()

    def list_all(self) -> list[PositionRecord]:
        statement: Select[tuple[PositionRecord]] = select(PositionRecord).order_by(
            PositionRecord.updated_at.desc(),
            PositionRecord.id.desc(),
        )
        return self._session.execute(statement).scalars().all()

    def upsert(
        self,
        *,
        exchange: str,
        symbol: str,
        trading_mode: str = "SPOT",
        mode: str,
        side: str,
        quantity: Decimal,
        average_entry_price: Decimal | None = None,
        realized_pnl: Decimal = Decimal("0"),
        unrealized_pnl: Decimal = Decimal("0"),
        stop_loss_price: Decimal | None = None,
        highest_price_since_entry: Decimal | None = None,
    ) -> PositionRecord:
        record = self.get(
            exchange=exchange,
            symbol=symbol,
            trading_mode=trading_mode,
            mode=mode,
        )
        if record is None:
            record = PositionRecord(
                exchange=exchange,
                symbol=symbol,
                trading_mode=trading_mode,
                mode=mode,
                side=side,
                quantity=quantity,
                average_entry_price=average_entry_price,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl,
                stop_loss_price=stop_loss_price,
                highest_price_since_entry=highest_price_since_entry,
            )
            self._session.add(record)
        else:
            record.side = side
            record.quantity = quantity
            record.average_entry_price = average_entry_price
            record.realized_pnl = realized_pnl
            record.unrealized_pnl = unrealized_pnl
            record.stop_loss_price = stop_loss_price
            record.highest_price_since_entry = highest_price_since_entry
        self._session.flush()
        return record
