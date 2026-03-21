from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, TimestampMixin


class OperatorConfigRecord(TimestampMixin, Base):
    __tablename__ = "operator_configs"
    __table_args__ = (
        UniqueConstraint("config_name", name="uq_operator_configs_config_name"),
        Index("ix_operator_configs_config_name", "config_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(50), nullable=False)
    fast_period: Mapped[int] = mapped_column(nullable=False)
    slow_period: Mapped[int] = mapped_column(nullable=False)
    trading_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="SPOT")
    updated_by: Mapped[str] = mapped_column(String(100), nullable=False)
