from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class NotificationEvent:
    event_type: str
    severity: str
    title: str
    body: str
    metadata: dict[str, Any]
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "severity": self.severity,
            "title": self.title,
            "body": self.body,
            "metadata": self._normalize_value(self.metadata),
            "occurred_at": self._normalize_datetime(self.occurred_at),
        }

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: cls._normalize_value(item) for key, item in value.items()}
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return cls._normalize_datetime(value)
        if isinstance(value, tuple):
            return [cls._normalize_value(item) for item in value]
        return value

    @staticmethod
    def _normalize_datetime(value: datetime) -> str:
        normalized = value.astimezone(UTC)
        return normalized.isoformat().replace("+00:00", "Z")


class NotificationSender(Protocol):
    def send(self, event: NotificationEvent) -> None: ...
