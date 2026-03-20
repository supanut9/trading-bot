from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, TimestampMixin


class RuntimeControlRecord(TimestampMixin, Base):
    __tablename__ = "runtime_controls"
    __table_args__ = (
        UniqueConstraint("control_name", name="uq_runtime_controls_control_name"),
        Index("ix_runtime_controls_control_name", "control_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    control_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bool_value: Mapped[bool] = mapped_column(nullable=False)
    string_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str] = mapped_column(String(100), nullable=False)
