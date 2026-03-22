from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.runtime_control import RuntimeControlRecord


class RuntimeControlRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_name(self, control_name: str) -> RuntimeControlRecord | None:
        statement: Select[tuple[RuntimeControlRecord]] = select(RuntimeControlRecord).where(
            RuntimeControlRecord.control_name == control_name
        )
        return self._session.execute(statement).scalar_one_or_none()

    def upsert_bool(
        self,
        *,
        control_name: str,
        bool_value: bool,
        updated_by: str,
        string_value: str | None = None,
    ) -> RuntimeControlRecord:
        record = self.get_by_name(control_name)
        if record is None:
            record = RuntimeControlRecord(
                control_name=control_name,
                bool_value=bool_value,
                string_value=string_value,
                updated_by=updated_by,
            )
            self._session.add(record)
            self._session.flush()
            return record

        record.bool_value = bool_value
        record.string_value = string_value
        record.updated_by = updated_by
        self._session.flush()
        return record

    def upsert_string(
        self,
        *,
        control_name: str,
        string_value: str,
        updated_by: str,
        bool_value: bool = False,
    ) -> RuntimeControlRecord:
        record = self.get_by_name(control_name)
        if record is None:
            record = RuntimeControlRecord(
                control_name=control_name,
                bool_value=bool_value,
                string_value=string_value,
                updated_by=updated_by,
            )
            self._session.add(record)
            self._session.flush()
            return record

        record.bool_value = bool_value
        record.string_value = string_value
        record.updated_by = updated_by
        self._session.flush()
        return record
