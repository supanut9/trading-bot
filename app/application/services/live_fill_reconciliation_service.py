from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.repositories.order_repository import OrderRepository
from app.infrastructure.database.repositories.position_repository import PositionRepository
from app.infrastructure.database.repositories.trade_repository import TradeRepository
from app.infrastructure.exchanges.base import LiveOrderExchangeClient


@dataclass(frozen=True, slots=True)
class LiveFillReconciliationResult:
    order_id: int
    client_order_id: str | None
    exchange_order_id: str | None
    status: str
    detail: str
    trade_created: bool
    position_quantity: Decimal | None = None


class LiveFillReconciliationService:
    def __init__(self, session: Session, *, client: LiveOrderExchangeClient) -> None:
        self._session = session
        self._client = client
        self._orders = OrderRepository(session)
        self._trades = TradeRepository(session)
        self._positions = PositionRepository(session)

    def reconcile_recent_live_orders(
        self, *, limit: int = 20
    ) -> list[LiveFillReconciliationResult]:
        orders = self._orders.list_live_orders_by_status(
            statuses=("submitting", "submitted", "new", "partially_filled"),
            limit=limit,
        )
        return [self._reconcile_order(order) for order in orders]

    def _reconcile_order(self, order: OrderRecord) -> LiveFillReconciliationResult:
        remote = self._client.fetch_order_status(
            symbol=order.symbol,
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
        )
        order.status = remote.status
        if remote.exchange_order_id:
            order.exchange_order_id = remote.exchange_order_id

        existing_trades = self._trades.list_by_order_id(order.id)
        if remote.status != "filled":
            self._session.commit()
            return LiveFillReconciliationResult(
                order_id=order.id,
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                status=order.status,
                detail="live order not filled yet",
                trade_created=False,
            )

        if existing_trades:
            position = self._positions.get(
                exchange=order.exchange,
                symbol=order.symbol,
                mode=order.mode,
            )
            self._session.commit()
            return LiveFillReconciliationResult(
                order_id=order.id,
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                status=order.status,
                detail="live order already reconciled",
                trade_created=False,
                position_quantity=position.quantity if position is not None else None,
            )

        if remote.average_fill_price is None or remote.executed_quantity <= Decimal("0"):
            self._session.commit()
            return LiveFillReconciliationResult(
                order_id=order.id,
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                status=order.status,
                detail="live order fill details unavailable",
                trade_created=False,
            )

        self._trades.create(
            exchange=order.exchange,
            symbol=order.symbol,
            side=order.side,
            quantity=remote.executed_quantity,
            price=remote.average_fill_price,
            order_id=order.id,
        )
        position = self._apply_position_update(
            order, remote.executed_quantity, remote.average_fill_price
        )
        self._session.commit()
        return LiveFillReconciliationResult(
            order_id=order.id,
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            status=order.status,
            detail="live order reconciled from filled exchange status",
            trade_created=True,
            position_quantity=position.quantity,
        )

    def _apply_position_update(
        self,
        order: OrderRecord,
        executed_quantity: Decimal,
        average_fill_price: Decimal,
    ):
        current_position = self._positions.get(
            exchange=order.exchange,
            symbol=order.symbol,
            mode=order.mode,
        )
        existing_quantity = current_position.quantity if current_position else Decimal("0")
        existing_average = current_position.average_entry_price if current_position else None
        existing_realized = current_position.realized_pnl if current_position else Decimal("0")

        if order.side == "buy":
            total_cost = (existing_quantity * (existing_average or Decimal("0"))) + (
                executed_quantity * average_fill_price
            )
            new_quantity = existing_quantity + executed_quantity
            new_average = total_cost / new_quantity
            return self._positions.upsert(
                exchange=order.exchange,
                symbol=order.symbol,
                mode=order.mode,
                side="long",
                quantity=new_quantity,
                average_entry_price=new_average,
                realized_pnl=existing_realized,
                unrealized_pnl=Decimal("0"),
            )

        if current_position is None or current_position.average_entry_price is None:
            raise ValueError(
                "live sell fill cannot be reconciled without an existing live position"
            )

        realized_pnl = (
            average_fill_price - current_position.average_entry_price
        ) * executed_quantity
        new_quantity = current_position.quantity - executed_quantity
        new_average = current_position.average_entry_price if new_quantity > Decimal("0") else None
        return self._positions.upsert(
            exchange=order.exchange,
            symbol=order.symbol,
            mode=order.mode,
            side="long",
            quantity=new_quantity,
            average_entry_price=new_average,
            realized_pnl=existing_realized + realized_pnl,
            unrealized_pnl=Decimal("0"),
        )
