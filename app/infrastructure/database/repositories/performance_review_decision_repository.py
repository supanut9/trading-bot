from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.performance_review_decision import (
    PerformanceReviewDecisionRecord,
)


class PerformanceReviewDecisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_latest(self, *, exchange: str, symbol: str) -> PerformanceReviewDecisionRecord | None:
        statement: Select[tuple[PerformanceReviewDecisionRecord]] = (
            select(PerformanceReviewDecisionRecord)
            .where(
                PerformanceReviewDecisionRecord.exchange == exchange,
                PerformanceReviewDecisionRecord.symbol == symbol,
            )
            .order_by(
                PerformanceReviewDecisionRecord.created_at.desc(),
                PerformanceReviewDecisionRecord.id.desc(),
            )
            .limit(1)
        )
        return self._session.execute(statement).scalar_one_or_none()

    def create(
        self,
        *,
        exchange: str,
        symbol: str,
        review_period_days: int,
        recommendation: str,
        operator_decision: str,
        rationale: str,
        root_cause_driver: str,
        root_cause_regime: str,
        review_generated_at: str,
        decided_by: str,
        snapshot_json: str,
    ) -> PerformanceReviewDecisionRecord:
        record = PerformanceReviewDecisionRecord(
            exchange=exchange,
            symbol=symbol,
            review_period_days=review_period_days,
            recommendation=recommendation,
            operator_decision=operator_decision,
            rationale=rationale,
            root_cause_driver=root_cause_driver,
            root_cause_regime=root_cause_regime,
            review_generated_at=review_generated_at,
            decided_by=decided_by,
            snapshot_json=snapshot_json,
        )
        self._session.add(record)
        self._session.flush()
        return record
