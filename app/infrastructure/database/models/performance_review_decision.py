from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, TimestampMixin


class PerformanceReviewDecisionRecord(TimestampMixin, Base):
    __tablename__ = "performance_review_decisions"
    __table_args__ = (
        Index(
            "ix_performance_review_decisions_lookup",
            "exchange",
            "symbol",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    review_period_days: Mapped[int] = mapped_column(nullable=False)
    recommendation: Mapped[str] = mapped_column(String(50), nullable=False)
    operator_decision: Mapped[str] = mapped_column(String(50), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause_driver: Mapped[str] = mapped_column(String(80), nullable=False)
    root_cause_regime: Mapped[str] = mapped_column(String(80), nullable=False)
    review_generated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    decided_by: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
