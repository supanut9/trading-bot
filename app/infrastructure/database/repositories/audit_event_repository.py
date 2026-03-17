from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.audit_event import AuditEventRecord


class AuditEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_recent(self, *, limit: int = 50) -> list[AuditEventRecord]:
        statement: Select[tuple[AuditEventRecord]] = (
            select(AuditEventRecord)
            .order_by(
                AuditEventRecord.created_at.desc(),
                AuditEventRecord.id.desc(),
            )
            .limit(limit)
        )
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
