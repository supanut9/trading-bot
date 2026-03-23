from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.application.services.live_order_state import (
    resolve_submission_state,
    transition_live_order,
)
from app.config import Settings
from app.core.logger import get_logger
from app.infrastructure.database.repositories.order_repository import OrderRepository
from app.infrastructure.exchanges.base import ExchangeOrderRequest, LiveOrderExchangeClient

logger = get_logger(__name__)


class SmartOrderFallbackService:
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

    def process_fallbacks(self) -> int:
        if (
            not self._settings.live_trading_enabled
            or self._settings.live_order_routing_mode != "limit"
        ):
            return 0

        limit_timeout = self._settings.live_limit_order_timeout_seconds
        now = datetime.now(UTC)

        open_orders = self._orders.list_live_orders_by_status(statuses=("open",), limit=100)
        fallback_count = 0

        for order in open_orders:
            if order.order_type.lower() != "limit":
                continue

            created_at = order.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            else:
                created_at = created_at.astimezone(UTC)

            elapsed_seconds = (now - created_at).total_seconds()
            if elapsed_seconds > limit_timeout:
                logger.info(
                    "limit_order_timeout exchange=%s symbol=%s order_id=%s "
                    "client_order_id=%s elapsed_seconds=%.1f",
                    order.exchange,
                    order.symbol,
                    order.id,
                    order.client_order_id,
                    elapsed_seconds,
                )

                try:
                    cancellation = self._client.cancel_order(
                        symbol=order.symbol,
                        client_order_id=order.client_order_id,
                        exchange_order_id=order.exchange_order_id,
                    )

                    if cancellation.status in ("canceled", "cancelled", "filled"):
                        # Ensure we mark it as canceled
                        order.status = "canceled"
                        self._session.commit()

                        if cancellation.status != "filled":
                            market_client_order_id = f"{order.client_order_id}-fb"
                            logger.info(
                                "executing_fallback_market_order exchange=%s symbol=%s "
                                "side=%s quantity=%s original_client_order_id=%s "
                                "new_client_order_id=%s",
                                order.exchange,
                                order.symbol,
                                order.side,
                                order.quantity,
                                order.client_order_id,
                                market_client_order_id,
                            )

                            fallback_order = self._orders.create(
                                exchange=order.exchange,
                                symbol=order.symbol,
                                side=order.side,
                                order_type="market",
                                status="submitting",
                                mode="live",
                                strategy_name=order.strategy_name,
                                quantity=order.quantity,
                                price=None,
                                signal_price=order.signal_price,
                                client_order_id=market_client_order_id,
                                submitted_reason=f"fallback for timed-out limit order {order.id}",
                            )
                            submission = self._client.submit_order(
                                ExchangeOrderRequest(
                                    symbol=order.symbol,
                                    side=order.side,
                                    quantity=order.quantity,
                                    order_type="market",
                                    validate_only=False,
                                    client_order_id=market_client_order_id,
                                )
                            )

                            resolution = resolve_submission_state(submission.status)
                            transition_live_order(fallback_order, next_status=resolution.status)
                            fallback_order.exchange_order_id = submission.exchange_order_id
                            self._session.commit()

                        fallback_count += 1
                except Exception as exc:
                    self._session.rollback()
                    logger.error(
                        "limit_order_fallback_failed exchange=%s symbol=%s order_id=%s error=%s",
                        order.exchange,
                        order.symbol,
                        order.id,
                        exc,
                    )

        return fallback_count
