from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.application.services.live_order_state import ACTIVE_LIVE_ORDER_STATUSES
from app.infrastructure.database.repositories.order_repository import OrderRepository


@dataclass(frozen=True, slots=True)
class StaleLiveOrderView:
    id: int
    symbol: str
    side: str
    status: str
    client_order_id: str | None
    exchange_order_id: str | None
    updated_at: datetime
    age_minutes: int


class StaleLiveOrderService:
    def __init__(
        self,
        session: Session,
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._orders = OrderRepository(session)
        self._now = now_provider or (lambda: datetime.now(UTC))

    def list_stale_orders(
        self,
        *,
        threshold_minutes: int,
        limit: int = 20,
    ) -> list[StaleLiveOrderView]:
        cutoff = self._now() - timedelta(minutes=threshold_minutes)
        candidates = self._orders.list_live_orders_by_status(
            statuses=ACTIVE_LIVE_ORDER_STATUSES,
            limit=limit,
        )
        views: list[StaleLiveOrderView] = []
        for order in candidates:
            updated_at = self._normalize_datetime(order.updated_at)
            if updated_at > cutoff:
                continue
            age_minutes = max(0, int((self._now() - updated_at).total_seconds() // 60))
            views.append(
                StaleLiveOrderView(
                    id=order.id,
                    symbol=order.symbol,
                    side=order.side,
                    status=order.status,
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    updated_at=updated_at,
                    age_minutes=age_minutes,
                )
            )
        return views

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
