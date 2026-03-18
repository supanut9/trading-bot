from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.infrastructure.database.repositories.audit_event_repository import AuditEventRepository


@dataclass(frozen=True, slots=True)
class AuditEventView:
    id: int
    created_at: datetime
    event_type: str
    source: str
    status: str
    detail: str
    exchange: str | None
    symbol: str | None
    timeframe: str | None
    channel: str | None
    related_event_type: str | None
    correlation_id: str | None
    payload_json: str | None


@dataclass(frozen=True, slots=True)
class AuditEventFilters:
    event_type: str | None = None
    status: str | None = None
    source: str | None = None
    channel: str | None = None
    related_event_type: str | None = None
    search: str | None = None


class AuditService:
    def __init__(
        self,
        *,
        session: Session | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self._session = session
        self._session_factory = session_factory

    def list_recent(
        self,
        *,
        limit: int = 50,
        filters: AuditEventFilters | None = None,
    ) -> list[AuditEventView]:
        active_filters = filters or AuditEventFilters()
        return [
            self._to_view(record)
            for record in self._with_repository(
                lambda repository: repository.list_filtered(
                    limit=limit,
                    event_type=active_filters.event_type,
                    status=active_filters.status,
                    source=active_filters.source,
                    channel=active_filters.channel,
                    related_event_type=active_filters.related_event_type,
                    search=active_filters.search,
                )
            )
        ]

    def record_control_result(
        self,
        *,
        control_type: str,
        source: str,
        status: str,
        detail: str,
        settings: Settings,
        payload: dict[str, Any],
    ) -> None:
        self._record(
            event_type=control_type,
            source=source,
            status=status,
            detail=detail,
            exchange=settings.exchange_name,
            symbol=settings.default_symbol,
            timeframe=settings.default_timeframe,
            payload=payload,
        )

    def record_notification_delivery(
        self,
        *,
        source: str,
        channel: str,
        status: str,
        detail: str,
        related_event_type: str,
        payload: dict[str, Any],
    ) -> None:
        metadata = payload.get("metadata", {})
        self._record(
            event_type="notification_delivery",
            source=source,
            status=status,
            detail=detail,
            exchange=self._optional_str(metadata.get("exchange")),
            symbol=self._optional_str(metadata.get("symbol")),
            timeframe=self._optional_str(metadata.get("timeframe")),
            channel=channel,
            related_event_type=related_event_type,
            payload=payload,
        )

    def _record(
        self,
        *,
        event_type: str,
        source: str,
        status: str,
        detail: str,
        exchange: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        channel: str | None = None,
        related_event_type: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        payload_json = None
        if payload is not None:
            payload_json = json.dumps(payload, sort_keys=True, default=str)

        self._with_repository(
            lambda repository: repository.create(
                event_type=event_type,
                source=source,
                status=status,
                detail=detail,
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                channel=channel,
                related_event_type=related_event_type,
                payload_json=payload_json,
            )
        )

    def _with_repository(self, fn: Any) -> Any:
        if self._session is not None:
            return fn(AuditEventRepository(self._session))
        if self._session_factory is None:
            return None
        with self._session_factory() as session:
            result = fn(AuditEventRepository(session))
            session.commit()
            return result

    @staticmethod
    def _to_view(record: Any) -> AuditEventView:
        correlation_id = AuditService._extract_correlation_id(record.payload_json)
        return AuditEventView(
            id=record.id,
            created_at=record.created_at,
            event_type=record.event_type,
            source=record.source,
            status=record.status,
            detail=record.detail,
            exchange=record.exchange,
            symbol=record.symbol,
            timeframe=record.timeframe,
            channel=record.channel,
            related_event_type=record.related_event_type,
            correlation_id=correlation_id,
            payload_json=record.payload_json,
        )

    @staticmethod
    def _optional_str(value: object) -> str | None:
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _extract_correlation_id(payload_json: str | None) -> str | None:
        if payload_json is None:
            return None
        try:
            payload = json.loads(payload_json)
        except (TypeError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        correlation_id = payload.get("correlation_id")
        if correlation_id in {None, ""}:
            return None
        return str(correlation_id)
