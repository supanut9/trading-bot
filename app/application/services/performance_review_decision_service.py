from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.application.services.live_performance_review_service import LivePerformanceReviewService
from app.infrastructure.database.repositories.performance_review_decision_repository import (
    PerformanceReviewDecisionRepository,
)

OperatorDecision = Literal["keep_running", "reduce_risk", "pause_and_rework", "halt"]


@dataclass(frozen=True, slots=True)
class PerformanceReviewDecisionView:
    recommendation: str
    operator_decision: str
    rationale: str
    review_period_days: int
    root_cause_driver: str
    root_cause_regime: str
    review_generated_at: datetime
    decided_at: datetime
    decided_by: str
    age_days: int
    stale: bool


class PerformanceReviewDecisionService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = PerformanceReviewDecisionRepository(session)
        self._review_svc = LivePerformanceReviewService(session)

    def get_latest_decision(
        self, *, exchange: str, symbol: str
    ) -> PerformanceReviewDecisionView | None:
        record = self._repo.get_latest(exchange=exchange, symbol=symbol)
        if record is None:
            return None
        return self._to_view(record)

    def record_decision(
        self,
        *,
        exchange: str,
        symbol: str,
        operator_decision: OperatorDecision,
        rationale: str,
        review_period_days: int,
        decided_by: str,
    ) -> PerformanceReviewDecisionView:
        review = self._review_svc.get_performance_review(
            exchange=exchange,
            symbol=symbol,
            review_period_days=review_period_days,
        )
        record = self._repo.create(
            exchange=exchange,
            symbol=symbol,
            review_period_days=review.review_period_days,
            recommendation=review.recommendation,
            operator_decision=operator_decision,
            rationale=rationale,
            root_cause_driver=review.root_cause.primary_driver,
            root_cause_regime=review.root_cause.regime_assessment,
            review_generated_at=review.generated_at.isoformat(),
            decided_by=decided_by,
            snapshot_json=json.dumps(asdict(review), sort_keys=True, default=str),
        )
        return self._to_view(record)

    @staticmethod
    def _to_view(record: object) -> PerformanceReviewDecisionView:
        from app.infrastructure.database.models.performance_review_decision import (
            PerformanceReviewDecisionRecord,
        )

        assert isinstance(record, PerformanceReviewDecisionRecord)
        review_generated_at = datetime.fromisoformat(record.review_generated_at)
        if review_generated_at.tzinfo is None:
            review_generated_at = review_generated_at.replace(tzinfo=UTC)
        decided_at = record.created_at
        age_days = max(
            0,
            int((datetime.now(UTC) - decided_at.astimezone(UTC)).total_seconds() // 86400),
        )
        stale = age_days > record.review_period_days
        return PerformanceReviewDecisionView(
            recommendation=record.recommendation,
            operator_decision=record.operator_decision,
            rationale=record.rationale,
            review_period_days=record.review_period_days,
            root_cause_driver=record.root_cause_driver,
            root_cause_regime=record.root_cause_regime,
            review_generated_at=review_generated_at,
            decided_at=decided_at,
            decided_by=record.decided_by,
            age_days=age_days,
            stale=stale,
        )
