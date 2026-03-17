from __future__ import annotations

from typing import Any

from app.application.services.backtest_service import BacktestResult
from app.application.services.worker_orchestration_service import WorkerCycleResult
from app.config import Settings
from app.core.logger import get_logger
from app.infrastructure.notifications.models import NotificationEvent, NotificationSender
from app.infrastructure.notifications.senders import (
    LogNotificationSender,
    NoOpNotificationSender,
    WebhookNotificationSender,
)

logger = get_logger(__name__)


class NotificationService:
    def __init__(self, *, sender: NotificationSender, channel: str) -> None:
        self._sender = sender
        self._channel = channel
        self._enabled = channel != "none"

    def notify_worker_cycle(self, settings: Settings, result: WorkerCycleResult) -> bool:
        event = self._build_worker_event(settings, result)
        if event is None:
            return False
        return self.publish(event)

    def notify_backtest_completed(self, settings: Settings, result: BacktestResult) -> bool:
        event = NotificationEvent(
            event_type="backtest.completed",
            severity="info",
            title="Backtest completed",
            body=(
                f"Backtest finished for {settings.default_symbol} on "
                f"{settings.default_timeframe} with ending equity {result.ending_equity}."
            ),
            metadata={
                "app": settings.app_name,
                "env": settings.app_env,
                "exchange": settings.exchange_name,
                "symbol": settings.default_symbol,
                "timeframe": settings.default_timeframe,
                "starting_equity": result.starting_equity,
                "ending_equity": result.ending_equity,
                "realized_pnl": result.realized_pnl,
                "total_return_pct": result.total_return_pct,
                "executions": result.total_trades,
                "max_drawdown_pct": result.max_drawdown_pct,
            },
        )
        return self.publish(event)

    def notify_backtest_skipped(
        self,
        settings: Settings,
        *,
        reason: str,
        count: int | None = None,
        required: int | None = None,
    ) -> bool:
        metadata: dict[str, Any] = {
            "app": settings.app_name,
            "env": settings.app_env,
            "exchange": settings.exchange_name,
            "symbol": settings.default_symbol,
            "timeframe": settings.default_timeframe,
            "reason": reason,
        }
        if count is not None:
            metadata["count"] = count
        if required is not None:
            metadata["required"] = required

        event = NotificationEvent(
            event_type="backtest.skipped",
            severity="warning",
            title="Backtest skipped",
            body=(
                f"Backtest skipped for {settings.default_symbol} on "
                f"{settings.default_timeframe}: {reason}."
            ),
            metadata=metadata,
        )
        return self.publish(event)

    def notify_market_sync(self, settings: Settings, result: Any) -> bool:
        severity = "info" if result.status == "completed" else "warning"
        event_type = (
            "market_sync.completed" if result.status == "completed" else "market_sync.failed"
        )
        event = NotificationEvent(
            event_type=event_type,
            severity=severity,
            title="Market sync completed" if result.status == "completed" else "Market sync failed",
            body=(
                f"Market sync {result.status} for {settings.default_symbol} on "
                f"{settings.default_timeframe}: {result.detail}."
            ),
            metadata={
                "app": settings.app_name,
                "env": settings.app_env,
                "exchange": settings.exchange_name,
                "symbol": settings.default_symbol,
                "timeframe": settings.default_timeframe,
                "status": result.status,
                "detail": result.detail,
                "fetched_count": result.fetched_count,
                "stored_count": result.stored_count,
                "latest_open_time": result.latest_open_time,
            },
        )
        return self.publish(event)

    def publish(self, event: NotificationEvent) -> bool:
        if not self._enabled:
            return False
        try:
            self._sender.send(event)
        except Exception:
            logger.exception(
                "notification_delivery_failed channel=%s event_type=%s",
                self._channel,
                event.event_type,
            )
            return False

        logger.info(
            "notification_sent channel=%s event_type=%s severity=%s",
            self._channel,
            event.event_type,
            event.severity,
        )
        return True

    def _build_worker_event(
        self,
        settings: Settings,
        result: WorkerCycleResult,
    ) -> NotificationEvent | None:
        if result.status == "executed":
            return NotificationEvent(
                event_type="worker.executed",
                severity="info",
                title="Worker executed signal",
                body=(
                    f"Worker executed {result.signal_action} for {settings.default_symbol} "
                    f"on {settings.default_timeframe}."
                ),
                metadata={
                    "app": settings.app_name,
                    "env": settings.app_env,
                    "exchange": settings.exchange_name,
                    "symbol": settings.default_symbol,
                    "timeframe": settings.default_timeframe,
                    "status": result.status,
                    "detail": result.detail,
                    "signal_action": result.signal_action,
                    "client_order_id": result.client_order_id,
                    "order_id": result.order_id,
                    "trade_id": result.trade_id,
                    "position_quantity": result.position_quantity,
                },
            )
        if result.status == "risk_rejected":
            return NotificationEvent(
                event_type="worker.risk_rejected",
                severity="warning",
                title="Worker signal rejected",
                body=(
                    f"Worker rejected {result.signal_action} for {settings.default_symbol} "
                    f"on {settings.default_timeframe}: {result.detail}."
                ),
                metadata={
                    "app": settings.app_name,
                    "env": settings.app_env,
                    "exchange": settings.exchange_name,
                    "symbol": settings.default_symbol,
                    "timeframe": settings.default_timeframe,
                    "status": result.status,
                    "detail": result.detail,
                    "signal_action": result.signal_action,
                    "client_order_id": result.client_order_id,
                },
            )
        return None


def build_notification_service(settings: Settings) -> NotificationService:
    if settings.notification_channel == "none":
        sender = NoOpNotificationSender()
    elif settings.notification_channel == "log":
        sender = LogNotificationSender()
    else:
        if not settings.notification_webhook_url:
            raise ValueError(
                "NOTIFICATION_WEBHOOK_URL is required when NOTIFICATION_CHANNEL=webhook"
            )
        sender = WebhookNotificationSender(
            url=settings.notification_webhook_url,
            timeout_seconds=settings.notification_timeout_seconds,
        )

    return NotificationService(sender=sender, channel=settings.notification_channel)
