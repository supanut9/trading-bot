import json
from urllib.request import Request, urlopen

from app.core.logger import get_logger
from app.infrastructure.notifications.models import NotificationEvent

logger = get_logger(__name__)


class NoOpNotificationSender:
    def send(self, event: NotificationEvent) -> None:
        del event


class LogNotificationSender:
    def send(self, event: NotificationEvent) -> None:
        logger.info("notification_event payload=%s", json.dumps(event.to_payload(), sort_keys=True))


class WebhookNotificationSender:
    def __init__(self, *, url: str, timeout_seconds: int) -> None:
        self._url = url
        self._timeout_seconds = timeout_seconds

    def send(self, event: NotificationEvent) -> None:
        request = Request(
            self._url,
            data=json.dumps(event.to_payload(), sort_keys=True).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self._timeout_seconds) as response:
            status_code = getattr(response, "status", None)
            if isinstance(status_code, int) and not 200 <= status_code < 300:
                raise RuntimeError(f"webhook returned HTTP {status_code}")
            response.read()
