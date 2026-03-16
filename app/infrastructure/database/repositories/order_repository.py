from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
        average_fill_price: Decimal | None = None,
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
            average_fill_price=average_fill_price,
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
