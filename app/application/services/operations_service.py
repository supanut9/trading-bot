from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.infrastructure.database.repositories.position_repository import PositionRepository
from app.infrastructure.database.repositories.trade_repository import TradeRepository


@dataclass(frozen=True, slots=True)
class PositionView:
    exchange: str
    symbol: str
    side: str
    mode: str
    quantity: Decimal
    average_entry_price: Decimal | None
    realized_pnl: Decimal
    unrealized_pnl: Decimal


@dataclass(frozen=True, slots=True)
class TradeView:
    id: int
    order_id: int | None
    exchange: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee_amount: Decimal | None
    fee_asset: str | None
    created_at: datetime


class OperationsService:
    def __init__(self, session: Session) -> None:
        self._positions = PositionRepository(session)
        self._trades = TradeRepository(session)

    def list_positions(self) -> list[PositionView]:
        return [
            PositionView(
                exchange=position.exchange,
                symbol=position.symbol,
                side=position.side,
                mode=position.mode,
                quantity=position.quantity,
                average_entry_price=position.average_entry_price,
                realized_pnl=position.realized_pnl,
                unrealized_pnl=position.unrealized_pnl,
            )
            for position in self._positions.list_all()
        ]

    def list_trades(self, *, limit: int = 100) -> list[TradeView]:
        return [
            TradeView(
                id=trade.id,
                order_id=trade.order_id,
                exchange=trade.exchange,
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
                price=trade.price,
                fee_amount=trade.fee_amount,
                fee_asset=trade.fee_asset,
                created_at=trade.created_at,
            )
            for trade in self._trades.list_all(limit=limit)
        ]
