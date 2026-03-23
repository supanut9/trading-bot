"""Tests for StrategyIterationService."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.application.services.strategy_iteration_service import (
    StrategyIterationPlan,
    StrategyIterationService,
)
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def make_session(tmp_path: Path) -> object:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'iter_test.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    return create_session_factory(settings)()


def _make_review(
    recommendation: str,
    reasons: list,
    shadow_count: int = 0,
    latest_decision: object | None = None,
):
    from decimal import Decimal

    from app.application.services.live_performance_review_service import (
        LivePerformanceReview,
        ShadowModeMetrics,
        StrategyHealthIndicators,
    )

    shadow = ShadowModeMetrics(
        trade_count=shadow_count,
        win_rate_pct=None,
        expectancy=None,
        total_return_pct=None,
        max_drawdown_pct=None,
        total_net_pnl=Decimal("0"),
    )
    health = StrategyHealthIndicators(
        slippage_vs_model_pct=None,
        shadow_vs_oos_expectancy_drift=None,
        live_vs_shadow_win_rate_drift=None,
        consecutive_losses=0,
        signal_frequency_per_week=None,
    )
    return LivePerformanceReview(
        live_metrics=None,
        shadow_metrics=shadow,
        oos_baseline=None,
        health_indicators=health,
        root_cause=MagicMock(
            primary_driver="insufficient_live_data",
            regime_assessment="insufficient_live_sample",
            summary="No live trades yet.",
            operator_focus=["Collect more sample data."],
        ),
        recommendation=recommendation,
        recommendation_reasons=reasons,
        review_period_days=30,
        generated_at=MagicMock(),
        latest_decision=latest_decision,
    )


def _make_qual(all_passed: bool):
    from app.application.services.qualification_service import (
        QualificationGate,
        QualificationReport,
    )

    gate = QualificationGate(
        name="shadow_trade_count",
        passed=all_passed,
        reason="Test gate",
    )
    return QualificationReport(
        exchange="binance",
        symbol="BTC/USDT",
        all_passed=all_passed,
        gates=[gate],
    )


def test_keep_running_plan(tmp_path: Path) -> None:
    session = make_session(tmp_path)
    service = StrategyIterationService(session)

    with (
        patch.object(service._review_svc, "get_performance_review") as mock_review,
        patch.object(service._qual_svc, "evaluate") as mock_qual,
        patch.object(service._promotion_svc, "get_state") as mock_state,
    ):
        mock_review.return_value = _make_review("keep_running", ["All healthy."])
        mock_qual.return_value = _make_qual(all_passed=True)
        mock_state.return_value = MagicMock(stage="canary")

        plan = service.get_iteration_plan(exchange="binance", symbol="BTC/USDT")

    assert isinstance(plan, StrategyIterationPlan)
    assert plan.recommendation == "keep_running"
    assert plan.all_steps_clear is True
    names = [s.name for s in plan.steps]
    assert "performance_review" in names
    review_step = next(s for s in plan.steps if s.name == "performance_review")
    assert "current_runtime_stage=canary" in (review_step.evidence or "")


def test_halt_plan_contains_required_steps(tmp_path: Path) -> None:
    session = make_session(tmp_path)
    service = StrategyIterationService(session)

    with (
        patch.object(service._review_svc, "get_performance_review") as mock_review,
        patch.object(service._qual_svc, "evaluate") as mock_qual,
        patch.object(service._promotion_svc, "get_state") as mock_state,
    ):
        mock_review.return_value = _make_review(
            "halt", ["5 consecutive losses.", "Drawdown 35%."], shadow_count=5
        )
        mock_qual.return_value = _make_qual(all_passed=False)
        mock_state.return_value = MagicMock(stage="live")

        plan = service.get_iteration_plan(exchange="binance", symbol="BTC/USDT")

    assert plan.recommendation == "halt"
    assert plan.all_steps_clear is False
    names = [s.name for s in plan.steps]
    assert "record_operator_decision" in names
    assert "adjust_runtime_promotion" in names
    assert "immediate_halt" in names
    assert "run_walk_forward" in names
    assert "promote_to_live" in names
    decision_step = next(s for s in plan.steps if s.name == "record_operator_decision")
    assert decision_step.status == "required"
    stage_step = next(s for s in plan.steps if s.name == "adjust_runtime_promotion")
    assert stage_step.status == "required"
    # promote_to_live must be blocked because gates not passed
    promote = next(s for s in plan.steps if s.name == "promote_to_live")
    assert promote.status == "blocked"


def test_pause_and_rework_plan(tmp_path: Path) -> None:
    session = make_session(tmp_path)
    service = StrategyIterationService(session)

    with (
        patch.object(service._review_svc, "get_performance_review") as mock_review,
        patch.object(service._qual_svc, "evaluate") as mock_qual,
        patch.object(service._promotion_svc, "get_state") as mock_state,
    ):
        mock_review.return_value = _make_review(
            "pause_and_rework", ["Win rate drift below threshold."], shadow_count=10
        )
        mock_qual.return_value = _make_qual(all_passed=False)
        mock_state.return_value = MagicMock(stage="qualified")

        plan = service.get_iteration_plan(exchange="binance", symbol="BTC/USDT")

    assert plan.recommendation == "pause_and_rework"
    names = [s.name for s in plan.steps]
    assert "record_operator_decision" in names
    assert "adjust_runtime_promotion" in names
    assert "halt_live_exposure" in names
    assert "shadow_revalidation" in names


def test_reduce_risk_plan(tmp_path: Path) -> None:
    session = make_session(tmp_path)
    service = StrategyIterationService(session)

    with (
        patch.object(service._review_svc, "get_performance_review") as mock_review,
        patch.object(service._qual_svc, "evaluate") as mock_qual,
        patch.object(service._promotion_svc, "get_state") as mock_state,
    ):
        mock_review.return_value = _make_review(
            "reduce_risk", ["Slippage above threshold."], shadow_count=20
        )
        mock_qual.return_value = _make_qual(all_passed=False)
        mock_state.return_value = MagicMock(stage="live")

        plan = service.get_iteration_plan(exchange="binance", symbol="BTC/USDT")

    assert plan.recommendation == "reduce_risk"
    names = [s.name for s in plan.steps]
    assert "record_operator_decision" in names
    assert "adjust_runtime_promotion" in names
    assert "reduce_position_size" in names
    assert "shadow_monitoring" in names
    stage_step = next(s for s in plan.steps if s.name == "adjust_runtime_promotion")
    assert stage_step.status == "required"


def test_pause_plan_keeps_live_repromotion_blocked_until_review_turns_keep_running(
    tmp_path: Path,
) -> None:
    session = make_session(tmp_path)
    service = StrategyIterationService(session)

    latest_decision = MagicMock(operator_decision="keep_running", stale=False)

    with (
        patch.object(service._review_svc, "get_performance_review") as mock_review,
        patch.object(service._qual_svc, "evaluate") as mock_qual,
        patch.object(service._promotion_svc, "get_state") as mock_state,
    ):
        mock_review.return_value = _make_review(
            "pause_and_rework",
            ["Recovered after revalidation."],
            shadow_count=35,
            latest_decision=latest_decision,
        )
        mock_qual.return_value = _make_qual(all_passed=True)
        mock_state.return_value = MagicMock(stage="shadow")

        plan = service.get_iteration_plan(exchange="binance", symbol="BTC/USDT")

    decision_step = next(s for s in plan.steps if s.name == "record_operator_decision")
    promote_step = next(s for s in plan.steps if s.name == "promote_to_live")
    assert decision_step.status == "required"
    assert promote_step.status == "blocked"
    assert "revalidation must produce keep_running" in (promote_step.evidence or "")
