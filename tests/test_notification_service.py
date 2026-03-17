import json
import logging
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.services.backtest_service import BacktestResult
from app.application.services.notification_service import (
    NotificationService,
    build_notification_service,
)
from app.application.services.operational_control_service import MarketSyncControlResult
from app.application.services.stale_live_order_service import StaleLiveOrderView
from app.application.services.worker_orchestration_service import WorkerCycleResult
from app.config import Settings
from app.infrastructure.notifications.senders import WebhookNotificationSender


class RecordingSender:
    def __init__(self) -> None:
        self.events = []

    def send(self, event) -> None:
        self.events.append(event)


class FailingSender:
    def send(self, _event) -> None:
        raise RuntimeError("sender failed")


class RecordingAudit:
    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []

    def record_notification_delivery(self, **kwargs: object) -> None:
        self.entries.append(kwargs)


def build_settings(**overrides: object) -> Settings:
    return Settings(
        APP_NAME="trading-bot",
        APP_ENV="test",
        EXCHANGE_NAME="binance",
        DEFAULT_SYMBOL="BTC/USDT",
        DEFAULT_TIMEFRAME="1h",
        **overrides,
    )


def test_notifies_worker_execution_event() -> None:
    sender = RecordingSender()
    service = NotificationService(sender=sender, channel="log")
    settings = build_settings()

    sent = service.notify_worker_cycle(
        settings,
        WorkerCycleResult(
            status="executed",
            detail="signal executed in paper mode",
            signal_action="buy",
            client_order_id="worker-btc-usdt-buy-20260101010000",
            order_id=10,
            trade_id=20,
            position_quantity=Decimal("0.50000000"),
        ),
    )

    assert sent is True
    assert len(sender.events) == 1
    event = sender.events[0]
    assert event.event_type == "worker.executed"
    assert event.metadata["order_id"] == 10
    assert event.metadata["position_quantity"] == Decimal("0.50000000")


def test_notifies_worker_risk_rejection_event() -> None:
    sender = RecordingSender()
    service = NotificationService(sender=sender, channel="log")
    settings = build_settings()

    sent = service.notify_worker_cycle(
        settings,
        WorkerCycleResult(
            status="risk_rejected",
            detail="daily loss limit reached",
            signal_action="buy",
            client_order_id="worker-btc-usdt-buy-20260101010000",
        ),
    )

    assert sent is True
    assert len(sender.events) == 1
    event = sender.events[0]
    assert event.event_type == "worker.risk_rejected"
    assert event.severity == "warning"
    assert event.metadata["detail"] == "daily loss limit reached"


def test_notifies_backtest_completion_event() -> None:
    sender = RecordingSender()
    service = NotificationService(sender=sender, channel="log")
    settings = build_settings()

    sent = service.notify_backtest_completed(
        settings,
        BacktestResult(
            starting_equity=Decimal("10000"),
            ending_equity=Decimal("10150"),
            total_return_pct=Decimal("1.5"),
            realized_pnl=Decimal("150"),
            max_drawdown_pct=Decimal("2.3"),
            total_trades=2,
            winning_trades=1,
            losing_trades=0,
            executions=tuple(),
        ),
    )

    assert sent is True
    assert len(sender.events) == 1
    event = sender.events[0]
    assert event.event_type == "backtest.completed"
    assert event.metadata["ending_equity"] == Decimal("10150")
    assert event.metadata["executions"] == 2


def test_notifies_backtest_skip_event() -> None:
    sender = RecordingSender()
    service = NotificationService(sender=sender, channel="log")
    settings = build_settings()

    sent = service.notify_backtest_skipped(
        settings,
        reason="not_enough_candles",
        count=1,
        required=6,
    )

    assert sent is True
    assert len(sender.events) == 1
    event = sender.events[0]
    assert event.event_type == "backtest.skipped"
    assert event.metadata["count"] == 1
    assert event.metadata["required"] == 6


def test_notifies_market_sync_completion_event() -> None:
    sender = RecordingSender()
    service = NotificationService(sender=sender, channel="log")
    settings = build_settings()

    sent = service.notify_market_sync(
        settings,
        MarketSyncControlResult(
            status="completed",
            detail="market data sync completed",
            fetched_count=4,
            stored_count=2,
        ),
    )

    assert sent is True
    assert len(sender.events) == 1
    event = sender.events[0]
    assert event.event_type == "market_sync.completed"
    assert event.metadata["stored_count"] == 2


def test_notifies_market_sync_failure_event() -> None:
    sender = RecordingSender()
    service = NotificationService(sender=sender, channel="log")
    settings = build_settings()

    sent = service.notify_market_sync(
        settings,
        MarketSyncControlResult(
            status="failed",
            detail="market data sync failed",
            fetched_count=0,
            stored_count=0,
        ),
    )

    assert sent is True
    assert len(sender.events) == 1
    event = sender.events[0]
    assert event.event_type == "market_sync.failed"
    assert event.severity == "warning"


def test_notifies_startup_state_sync_failure_event() -> None:
    sender = RecordingSender()
    service = NotificationService(sender=sender, channel="log")
    settings = build_settings()

    sent = service.notify_live_reconcile_failure(
        settings,
        source="job.startup_state_sync",
        detail="live reconciliation failed",
    )

    assert sent is True
    event = sender.events[0]
    assert event.event_type == "startup_state_sync.failed"
    assert event.severity == "warning"


def test_notifies_stale_live_orders_event() -> None:
    sender = RecordingSender()
    service = NotificationService(sender=sender, channel="log")
    settings = build_settings()

    sent = service.notify_stale_live_orders(
        settings,
        stale_orders=[
            StaleLiveOrderView(
                id=5,
                symbol="BTC/USDT",
                side="buy",
                status="submitted",
                client_order_id="stale-5",
                exchange_order_id="555",
                updated_at=datetime(2026, 1, 1, tzinfo=UTC),
                age_minutes=180,
            )
        ],
        threshold_minutes=120,
    )

    assert sent is True
    event = sender.events[0]
    assert event.event_type == "live_orders.stale_detected"
    assert event.metadata["stale_order_count"] == 1
    assert event.metadata["order_ids"] == [5]


def test_notification_failures_are_logged_and_do_not_raise(caplog) -> None:
    audit = RecordingAudit()
    service = NotificationService(sender=FailingSender(), channel="webhook", audit=audit)
    settings = build_settings()

    with caplog.at_level(logging.ERROR):
        sent = service.notify_backtest_skipped(settings, reason="no_candles")

    assert sent is False
    assert "notification_delivery_failed channel=webhook event_type=backtest.skipped" in caplog.text
    assert len(audit.entries) == 1
    assert audit.entries[0]["status"] == "failed"
    assert audit.entries[0]["related_event_type"] == "backtest.skipped"


def test_build_notification_service_requires_webhook_url() -> None:
    settings = build_settings(NOTIFICATION_CHANNEL="webhook")

    with pytest.raises(
        ValueError,
        match="NOTIFICATION_WEBHOOK_URL is required when NOTIFICATION_CHANNEL=webhook",
    ):
        build_notification_service(settings)


def test_webhook_sender_posts_json_payload(monkeypatch) -> None:
    captured: dict[str, object] = {}
    audit = RecordingAudit()

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return b"ok"

    def fake_urlopen(request, timeout: int):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("app.infrastructure.notifications.senders.urlopen", fake_urlopen)

    sender = WebhookNotificationSender(url="https://example.com/hook", timeout_seconds=7)
    service = NotificationService(sender=sender, channel="webhook", audit=audit)
    settings = build_settings()

    sent = service.notify_backtest_skipped(
        settings,
        reason="not_enough_candles",
        count=1,
        required=6,
    )

    assert sent is True
    assert captured["url"] == "https://example.com/hook"
    assert captured["timeout"] == 7
    assert captured["body"]["event_type"] == "backtest.skipped"
    assert captured["body"]["metadata"]["required"] == 6
    assert len(audit.entries) == 1
    assert audit.entries[0]["status"] == "sent"
    assert audit.entries[0]["channel"] == "webhook"


def test_webhook_sender_raises_on_non_2xx_response(monkeypatch) -> None:
    class FakeResponse:
        status = 500

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return b"error"

    monkeypatch.setattr(
        "app.infrastructure.notifications.senders.urlopen",
        lambda request, timeout: FakeResponse(),
    )

    sender = WebhookNotificationSender(url="https://example.com/hook", timeout_seconds=7)

    with pytest.raises(RuntimeError, match="webhook returned HTTP 500"):
        sender.send(RecordingSenderEventFactory.build())


class RecordingSenderEventFactory:
    @staticmethod
    def build():
        from app.infrastructure.notifications.models import NotificationEvent

        return NotificationEvent(
            event_type="test.event",
            severity="info",
            title="Test",
            body="Test body",
            metadata={},
        )
