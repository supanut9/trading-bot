from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.services.live_order_state import ACTIVE_LIVE_ORDER_STATUSES
from app.infrastructure.database.models.order import OrderRecord


class DuplicateClientOrderIdError(ValueError):
    """Raised when an order attempts to reuse an existing client_order_id."""


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        exchange: str,
        symbol: str,
        side: str,
        order_type: str,
        status: str,
        mode: str,
        quantity: Decimal,
        price: Decimal | None = None,
        signal_price: Decimal | None = None,
        average_fill_price: Decimal | None = None,
        executed_quantity: Decimal = Decimal("0"),
        client_order_id: str | None = None,
        exchange_order_id: str | None = None,
        submitted_reason: str | None = None,
    ) -> OrderRecord:
        record = OrderRecord(
            exchange=exchange,
            symbol=symbol,
            side=side,
            order_type=order_type,
            status=status,
            mode=mode,
            quantity=quantity,
            price=price,
            signal_price=signal_price,
            average_fill_price=average_fill_price,
            executed_quantity=executed_quantity,
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            submitted_reason=submitted_reason,
        )

        self._session.add(record)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            if client_order_id and "client_order_id" in str(exc).lower():
                raise DuplicateClientOrderIdError(
                    f"duplicate client_order_id: {client_order_id}"
                ) from exc
            raise
        return record

    def get_by_id(self, order_id: int) -> OrderRecord | None:
        statement: Select[tuple[OrderRecord]] = select(OrderRecord).where(
            OrderRecord.id == order_id
        )
        return self._session.execute(statement).scalar_one_or_none()

    def get_by_client_order_id(self, client_order_id: str) -> OrderRecord | None:
        statement: Select[tuple[OrderRecord]] = select(OrderRecord).where(
            OrderRecord.client_order_id == client_order_id
        )
        return self._session.execute(statement).scalar_one_or_none()

    def get_by_exchange_order_id(self, exchange_order_id: str) -> OrderRecord | None:
        statement: Select[tuple[OrderRecord]] = select(OrderRecord).where(
            OrderRecord.exchange_order_id == exchange_order_id
        )
        return self._session.execute(statement).scalar_one_or_none()

    def list_live_orders_by_status(
        self,
        *,
        statuses: tuple[str, ...],
        limit: int = 20,
    ) -> list[OrderRecord]:
        statement: Select[tuple[OrderRecord]] = (
            select(OrderRecord)
            .where(
                OrderRecord.mode == "live",
                OrderRecord.status.in_(statuses),
            )
            .order_by(OrderRecord.updated_at.desc(), OrderRecord.id.desc())
            .limit(limit)
        )
        return self._session.execute(statement).scalars().all()

    def has_active_live_order(
        self,
        *,
        exchange: str,
        symbol: str,
        side: str,
    ) -> bool:
        statement: Select[tuple[OrderRecord]] = (
            select(OrderRecord)
            .where(
                OrderRecord.exchange == exchange,
                OrderRecord.symbol == symbol,
                OrderRecord.side == side,
                OrderRecord.mode == "live",
                OrderRecord.status.in_(ACTIVE_LIVE_ORDER_STATUSES),
            )
            .limit(1)
        )
        return self._session.execute(statement).scalar_one_or_none() is not None
