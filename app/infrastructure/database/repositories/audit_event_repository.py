from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.audit_event import AuditEventRecord


class AuditEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_recent(self, *, limit: int = 50) -> list[AuditEventRecord]:
        return self.list_filtered(limit=limit)

    def list_filtered(
        self,
        *,
        limit: int = 50,
        event_type: str | None = None,
        status: str | None = None,
        source: str | None = None,
        channel: str | None = None,
        related_event_type: str | None = None,
        search: str | None = None,
    ) -> list[AuditEventRecord]:
        statement: Select[tuple[AuditEventRecord]] = select(AuditEventRecord)
        if event_type is not None:
            statement = statement.where(AuditEventRecord.event_type == event_type)
        if status is not None:
            statement = statement.where(AuditEventRecord.status == status)
        if source is not None:
            statement = statement.where(AuditEventRecord.source == source)
        if channel is not None:
            statement = statement.where(AuditEventRecord.channel == channel)
        if related_event_type is not None:
            statement = statement.where(AuditEventRecord.related_event_type == related_event_type)
        if search is not None:
            search_term = f"%{search.lower()}%"
            statement = statement.where(
                or_(
                    func.lower(AuditEventRecord.event_type).like(search_term),
                    func.lower(AuditEventRecord.source).like(search_term),
                    func.lower(AuditEventRecord.status).like(search_term),
                    func.lower(AuditEventRecord.detail).like(search_term),
                    func.lower(func.coalesce(AuditEventRecord.channel, "")).like(search_term),
                    func.lower(func.coalesce(AuditEventRecord.related_event_type, "")).like(
                        search_term
                    ),
                )
            )
        statement = statement.order_by(
            AuditEventRecord.created_at.desc(),
            AuditEventRecord.id.desc(),
        ).limit(limit)
        return self._session.execute(statement).scalars().all()

    def create(
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
        payload_json: str | None = None,
    ) -> AuditEventRecord:
        record = AuditEventRecord(
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
        self._session.add(record)
        self._session.flush()
        return record
