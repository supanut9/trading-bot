"""
StrategyIterationService: Orchestrates the re-validation and re-promotion workflow
when live performance falls short of expectations.

Workflow steps depend on the current performance recommendation:
  - halt        → full re-validation cycle required (WF → shadow ≥ 30 → gates → promote)
  - pause_and_rework → shadow reset + new WF run required
  - reduce_risk → shadow monitoring only, rules adjustment optional
  - keep_running → no action required
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.application.services.live_performance_review_service import (
    LivePerformanceReviewService,
)
from app.application.services.qualification_service import QualificationService
from app.core.logger import get_logger

logger = get_logger(__name__)

IterationRecommendation = Literal["halt", "pause_and_rework", "reduce_risk", "keep_running"]
StepStatus = Literal["required", "pending", "passed", "blocked"]


@dataclass(frozen=True, slots=True)
class IterationStep:
    name: str
    status: StepStatus
    description: str
    evidence: str | None = None


@dataclass(frozen=True, slots=True)
class StrategyIterationPlan:
    recommendation: IterationRecommendation
    recommendation_reasons: list[str]
    steps: list[IterationStep]
    all_steps_clear: bool
    generated_at: datetime
    exchange: str
    symbol: str
    review_period_days: int


class StrategyIterationService:
    """
    Combines the LivePerformanceReview with QualificationGates to produce
    a concrete, ordered re-validation checklist for operators and for AI agents
    to execute the promotion loop.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._review_svc = LivePerformanceReviewService(session)
        self._qual_svc = QualificationService(session)

    def get_iteration_plan(
        self,
        *,
        exchange: str,
        symbol: str,
        review_period_days: int = 30,
    ) -> StrategyIterationPlan:
        review = self._review_svc.get_performance_review(
            exchange=exchange,
            symbol=symbol,
            review_period_days=review_period_days,
        )
        qual = self._qual_svc.evaluate(exchange=exchange, symbol=symbol)

        recommendation: IterationRecommendation = review.recommendation  # type: ignore[assignment]
        steps = self._build_steps(
            recommendation=recommendation,
            review=review,
            qual=qual,
        )

        all_clear = all(s.status in ("passed", "pending") for s in steps)

        logger.info(
            "strategy_iteration_plan exchange=%s symbol=%s recommendation=%s all_clear=%s",
            exchange,
            symbol,
            recommendation,
            all_clear,
        )

        return StrategyIterationPlan(
            recommendation=recommendation,
            recommendation_reasons=review.recommendation_reasons,
            steps=steps,
            all_steps_clear=all_clear,
            generated_at=datetime.now(UTC),
            exchange=exchange,
            symbol=symbol,
            review_period_days=review_period_days,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_steps(
        self, *, recommendation: str, review: object, qual: object
    ) -> list[IterationStep]:
        from app.application.services.live_performance_review_service import LivePerformanceReview
        from app.application.services.qualification_service import QualificationReport

        assert isinstance(review, LivePerformanceReview)
        assert isinstance(qual, QualificationReport)

        if recommendation == "keep_running":
            return self._steps_keep_running(qual)
        if recommendation == "reduce_risk":
            return self._steps_reduce_risk(qual, review)
        if recommendation == "pause_and_rework":
            return self._steps_pause_and_rework(qual, review)
        # halt
        return self._steps_halt(qual, review)

    @staticmethod
    def _steps_keep_running(qual: object) -> list[IterationStep]:
        from app.application.services.qualification_service import QualificationReport

        assert isinstance(qual, QualificationReport)
        gates_passed = qual.all_passed
        return [
            IterationStep(
                name="performance_review",
                status="passed",
                description="Performance is within healthy ranges. No action required.",
            ),
            IterationStep(
                name="qualification_gates",
                status="passed" if gates_passed else "pending",
                description=(
                    "All qualification gates are passing."
                    if gates_passed
                    else "Some qualification gates are not yet met. Monitor before promoting."
                ),
                evidence=(
                    None
                    if gates_passed
                    else "; ".join(
                        g.reason
                        for g in qual.gates  # type: ignore[union-attr]
                        if not g.passed
                    )
                ),
            ),
        ]

    @staticmethod
    def _steps_reduce_risk(qual: object, review: object) -> list[IterationStep]:
        from app.application.services.live_performance_review_service import LivePerformanceReview
        from app.application.services.qualification_service import QualificationReport

        assert isinstance(qual, QualificationReport)
        assert isinstance(review, LivePerformanceReview)

        steps: list[IterationStep] = [
            IterationStep(
                name="reduce_position_size",
                status="required",
                description=(
                    "Reduce live position size or canary multiplier "
                    "while signals are underperforming vs shadow."
                ),
                evidence=(
                    f"{review.root_cause.summary} "
                    f"Focus: {'; '.join(review.root_cause.operator_focus)}"
                ),
            ),
            IterationStep(
                name="shadow_monitoring",
                status="required",
                description=(
                    f"Continue shadow trading. Shadow trades so far: "
                    f"{review.shadow_metrics.trade_count}. "
                    "Monitor for at least 30 additional trades before re-evaluating."
                ),
            ),
            IterationStep(
                name="qualification_gates",
                status="passed" if qual.all_passed else "pending",
                description=(
                    "Re-evaluate all qualification gates once shadow sample is large enough."
                ),
                evidence=(
                    "; ".join(g.reason for g in qual.gates if not g.passed)  # type: ignore[union-attr]
                    if not qual.all_passed
                    else None
                ),
            ),
        ]
        return steps

    @staticmethod
    def _steps_pause_and_rework(qual: object, review: object) -> list[IterationStep]:
        from app.application.services.live_performance_review_service import LivePerformanceReview
        from app.application.services.qualification_service import QualificationReport

        assert isinstance(qual, QualificationReport)
        assert isinstance(review, LivePerformanceReview)

        shadow_count = review.shadow_metrics.trade_count
        oos_baseline = review.oos_baseline

        steps: list[IterationStep] = [
            IterationStep(
                name="halt_live_exposure",
                status="required",
                description=(
                    "Pause live trading. Significant divergence detected between "
                    "live and shadow metrics."
                ),
                evidence=(
                    f"{review.root_cause.summary} "
                    f"Focus: {'; '.join(review.root_cause.operator_focus)}"
                ),
            ),
            IterationStep(
                name="diagnose_underperformance",
                status="required",
                description=(
                    "Diagnose the performance gap: check cost overshoot, "
                    "signal decay, or regime change using the live performance report."
                ),
                evidence=(
                    f"Primary driver: {review.root_cause.primary_driver}; "
                    f"regime: {review.root_cause.regime_assessment}"
                ),
            ),
            IterationStep(
                name="rework_strategy_params",
                status="required",
                description=(
                    "Adjust strategy parameters (fast/slow period, RSI filter, volume filter) "
                    "or risk settings (fee model, slippage assumption)."
                ),
            ),
            IterationStep(
                name="run_walk_forward",
                status="required" if oos_baseline is None else "pending",
                description=("Run a fresh walk-forward backtest to establish new OOS baseline."),
                evidence=(
                    f"Last baseline: run_id={oos_baseline.backtest_run_id}, "
                    f"date={oos_baseline.run_date.date()}"
                )
                if oos_baseline
                else None,
            ),
            IterationStep(
                name="shadow_revalidation",
                status="required" if shadow_count < 30 else "pending",
                description=(f"Accumulate at least 30 shadow trades. Current: {shadow_count}."),
            ),
            IterationStep(
                name="qualification_gates",
                status="passed" if qual.all_passed else "required",
                description="All qualification gates must pass before live re-promotion.",
                evidence=(
                    "; ".join(g.reason for g in qual.gates if not g.passed)  # type: ignore[union-attr]
                    if not qual.all_passed
                    else None
                ),
            ),
            IterationStep(
                name="promote_to_live",
                status="blocked" if not qual.all_passed else "pending",
                description=(
                    "Re-enable live trading (set LIVE_TRADING_ENABLED=true and "
                    "clear the halt flag via the operator controls API)."
                ),
            ),
        ]
        return steps

    @staticmethod
    def _steps_halt(qual: object, review: object) -> list[IterationStep]:
        from app.application.services.live_performance_review_service import LivePerformanceReview
        from app.application.services.qualification_service import QualificationReport

        assert isinstance(qual, QualificationReport)
        assert isinstance(review, LivePerformanceReview)

        shadow_count = review.shadow_metrics.trade_count
        live_metrics = review.live_metrics
        oos_baseline = review.oos_baseline

        health = review.health_indicators
        drawdown_note = (
            f"Max drawdown: {live_metrics.max_drawdown_pct:.2f}%"
            if live_metrics and live_metrics.max_drawdown_pct is not None
            else ""
        )

        steps: list[IterationStep] = [
            IterationStep(
                name="immediate_halt",
                status="required",
                description=(
                    "HALT live trading immediately via operator controls API. "
                    f"Consecutive losses: {health.consecutive_losses}. {drawdown_note}"
                ).strip(),
                evidence="; ".join(review.recommendation_reasons),
            ),
            IterationStep(
                name="incident_review",
                status="required",
                description=(
                    "Audit recent trades and orders to determine if the drawdown stems from "
                    "strategy decay, a market regime shift, or an execution bug."
                ),
            ),
            IterationStep(
                name="rework_strategy_params",
                status="required",
                description=(
                    "Rework strategy parameters or risk limits before any re-promotion attempt."
                ),
            ),
            IterationStep(
                name="run_walk_forward",
                status="required" if oos_baseline is None else "pending",
                description="Run a full walk-forward backtest on new parameters.",
                evidence=(
                    f"Previous baseline: run_id={oos_baseline.backtest_run_id}, "
                    f"OOS return={oos_baseline.oos_return_pct:.2f}%"
                )
                if oos_baseline
                else None,
            ),
            IterationStep(
                name="shadow_revalidation",
                status="required" if shadow_count < 30 else "pending",
                description=(
                    f"Accumulate ≥30 shadow trades on the revised strategy. "
                    f"Current shadow trade count: {shadow_count}."
                ),
            ),
            IterationStep(
                name="qualification_gates",
                status="passed" if qual.all_passed else "required",
                description=("All qualification gates must pass before re-promotion is allowed."),
                evidence=(
                    "; ".join(g.reason for g in qual.gates if not g.passed)  # type: ignore[union-attr]
                    if not qual.all_passed
                    else None
                ),
            ),
            IterationStep(
                name="promote_to_live",
                status="blocked" if not qual.all_passed else "pending",
                description=(
                    "Re-enable live trading only after all gates are green and "
                    "canary rollout is confirmed."
                ),
            ),
        ]
        return steps


# ---------------------------------------------------------------------------
# Response helper for computing iteration readiness summary
# ---------------------------------------------------------------------------


def summarise_plan(plan: StrategyIterationPlan) -> dict:
    required = [s for s in plan.steps if s.status == "required"]
    blocked = [s for s in plan.steps if s.status == "blocked"]
    return {
        "recommendation": plan.recommendation,
        "all_steps_clear": plan.all_steps_clear,
        "required_step_count": len(required),
        "blocked_step_count": len(blocked),
        "next_required_steps": [s.name for s in required[:3]],
    }
