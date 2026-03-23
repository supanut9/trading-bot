from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.application.services.live_order_state import (
    RECONCILABLE_LIVE_ORDER_STATUSES,
    requires_operator_review,
    resolve_reconcile_state,
    transition_live_order,
)
from app.application.services.live_recovery_state import classify_recovery_state
from app.config import Settings
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
    requires_operator_review: bool
    recovery_state: str
    position_quantity: Decimal | None = None


class LiveFillReconciliationService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        client: LiveOrderExchangeClient,
    ) -> None:
        self._session = session
        self._settings = settings
        self._client = client
        self._orders = OrderRepository(session)
        self._trades = TradeRepository(session)
        self._positions = PositionRepository(session)

    def reconcile_recent_live_orders(
        self, *, limit: int = 20
    ) -> list[LiveFillReconciliationResult]:
        orders = self._orders.list_live_orders_by_status(
            statuses=RECONCILABLE_LIVE_ORDER_STATUSES,
            limit=limit,
        )
        return [self._reconcile_order(order) for order in orders]

    def _reconcile_order(self, order: OrderRecord) -> LiveFillReconciliationResult:
        remote = self._client.fetch_order_status(
            symbol=order.symbol,
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
        )
        resolution = resolve_reconcile_state(
            remote.status,
            has_fill_details=(
                remote.average_fill_price is not None and remote.executed_quantity > Decimal("0")
            ),
        )

        transition_live_order(order, next_status=resolution.status)
        if remote.exchange_order_id:
            order.exchange_order_id = remote.exchange_order_id

        # Hardening: reconcile any NEW executed quantity found on the exchange
        to_reconcile_qty = remote.executed_quantity - order.executed_quantity
        trade_created = False

        if to_reconcile_qty > Decimal("0") and remote.average_fill_price is not None:
            # Calculate the effective price for this incremental fill portion
            # Cumulative Cost = Remote Qty * Remote Avg
            # Previous Cost = Local Executed Qty * Local Avg
            cumulative_cost = remote.executed_quantity * remote.average_fill_price
            previous_cost = order.executed_quantity * (order.average_fill_price or Decimal("0"))
            incremental_cost = cumulative_cost - previous_cost
            incremental_price = incremental_cost / to_reconcile_qty

            if order.signal_price:
                from app.core.logger import get_logger

                logger = get_logger(__name__)
                slippage_bps = (
                    (remote.average_fill_price - order.signal_price)
                    / order.signal_price
                    * Decimal("10000")
                )
                if order.side == "sell":
                    slippage_bps = -slippage_bps

                logger.info(
                    "live_order_partial_fill_slippage exchange=%s symbol=%s order_id=%s "
                    "side=%s signal_price=%.4f cumulative_fill_price=%.4f slippage_bps=%.1f "
                    "incremental_qty=%s",
                    order.exchange,
                    order.symbol,
                    order.id,
                    order.side,
                    order.signal_price,
                    remote.average_fill_price,
                    slippage_bps,
                    to_reconcile_qty,
                )

            self._trades.create(
                exchange=order.exchange,
                symbol=order.symbol,
                side=order.side,
                strategy_name=order.strategy_name,
                quantity=to_reconcile_qty,
                price=incremental_price,
                order_id=order.id,
            )
            self._apply_position_update(order, to_reconcile_qty, incremental_price)

            # Update order tracking fields
            order.executed_quantity = remote.executed_quantity
            order.average_fill_price = remote.average_fill_price
            trade_created = True

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
            detail=resolution.detail,
            trade_created=trade_created,
            requires_operator_review=requires_operator_review(order.status),
            recovery_state=classify_recovery_state(
                status=order.status,
                updated_at=order.updated_at,
                stale_threshold_minutes=self._settings.stale_live_order_threshold_minutes,
            ),
            position_quantity=position.quantity if position is not None else None,
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
                strategy_name=order.strategy_name
                or (current_position.strategy_name if current_position is not None else None),
                quantity=new_quantity,
                average_entry_price=new_average,
                realized_pnl=existing_realized,
                unrealized_pnl=Decimal("0"),
            ), Decimal("0")

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
            strategy_name=(
                order.strategy_name
                or (current_position.strategy_name if current_position is not None else None)
            )
            if new_quantity > Decimal("0")
            else None,
            quantity=new_quantity,
            average_entry_price=new_average,
            realized_pnl=existing_realized + realized_pnl,
            unrealized_pnl=Decimal("0"),
        ), realized_pnl
