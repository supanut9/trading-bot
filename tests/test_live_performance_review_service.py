from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.application.services.live_performance_review_service import LivePerformanceReviewService
from app.infrastructure.database.models.backtest_run import BacktestRunRecord
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.trade import TradeRecord


def _make_trade(
    *,
    realized_pnl: str,
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    order_mode: str = "live",
    created_at: datetime | None = None,
) -> tuple[TradeRecord, OrderRecord]:
    order = MagicMock(spec=OrderRecord)
    order.mode = order_mode
    order.signal_price = None
    order.average_fill_price = None

    trade = MagicMock(spec=TradeRecord)
    trade.exchange = exchange
    trade.symbol = symbol
    trade.realized_pnl = Decimal(realized_pnl)
    trade.fee_amount = Decimal("0")
    trade.created_at = created_at or datetime.now(UTC)
    trade.order_id = 1
    trade.price = Decimal("100")
    trade.quantity = Decimal("1")
    return trade, order


def _make_wf_run(
    *,
    oos_return_pct: str = "5.0",
    oos_drawdown_pct: str = "10.0",
    oos_total_trades: int = 40,
    in_sample_return_pct: str = "8.0",
    slippage_pct: str | None = None,
    spread_pct: str | None = None,
    overfitting_warning: bool = False,
) -> BacktestRunRecord:
    run = MagicMock(spec=BacktestRunRecord)
    run.id = 1
    run.created_at = datetime.now(UTC)
    run.walk_forward_oos_return_pct = Decimal(oos_return_pct)
    run.walk_forward_oos_drawdown_pct = Decimal(oos_drawdown_pct)
    run.walk_forward_oos_total_trades = oos_total_trades
    run.walk_forward_in_sample_return_pct = Decimal(in_sample_return_pct)
    run.slippage_pct = Decimal(slippage_pct) if slippage_pct is not None else None
    run.spread_pct = Decimal(spread_pct) if spread_pct is not None else None
    run.walk_forward_overfitting_warning = overfitting_warning
    return run


@pytest.fixture
def session():
    return MagicMock()


# ------------------------------------------------------------------
# Test: no live trades → keep_running
# ------------------------------------------------------------------


def test_no_live_trades_returns_keep_running(session, monkeypatch):
    """When there are no live trades the recommendation should be keep_running."""

    # Shadow trades: empty
    mock_shadow_repo = MagicMock()
    mock_shadow_repo.list_closed.return_value = []

    # Trade repo: no consecutive losses
    mock_trade_repo = MagicMock()
    mock_trade_repo.get_consecutive_losses.return_value = 0

    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.ShadowTradeRepository",
        lambda session: mock_shadow_repo,
    )
    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.TradeRepository",
        lambda session: mock_trade_repo,
    )

    # No live trades → _compute_live_metrics returns None early (no slippage query)
    # Execution order: (1) live trades query, (2) oos_baseline query
    scalars_result = MagicMock()
    scalars_result.scalars.return_value = iter([])

    wf_result = MagicMock()
    wf_result.scalar_one_or_none.return_value = None

    session.execute.side_effect = [scalars_result, wf_result]

    service = LivePerformanceReviewService(session)
    review = service.get_performance_review(
        exchange="binance",
        symbol="BTC/USDT",
    )

    assert review.recommendation == "keep_running"
    assert review.live_metrics is None
    assert "paper or shadow mode" in review.recommendation_reasons[0].lower()
    assert review.root_cause.primary_driver == "insufficient_live_data"


# ------------------------------------------------------------------
# Test: high consecutive losses → halt
# ------------------------------------------------------------------


def test_high_consecutive_losses_triggers_halt(session, monkeypatch):
    """Five or more consecutive losses must trigger a halt recommendation."""

    mock_shadow_repo = MagicMock()
    mock_shadow_repo.list_closed.return_value = []

    mock_trade_repo = MagicMock()
    mock_trade_repo.get_consecutive_losses.return_value = 6

    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.ShadowTradeRepository",
        lambda session: mock_shadow_repo,
    )
    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.TradeRepository",
        lambda session: mock_trade_repo,
    )

    # Simulate 6 live losing trades so live_metrics is not None
    trades = []
    for _ in range(6):
        t = MagicMock(spec=TradeRecord)
        t.realized_pnl = Decimal("-50")
        t.fee_amount = Decimal("1")
        t.created_at = datetime.now(UTC)
        trades.append(t)

    # session.execute is called twice: once for live trades (scalars),
    # once for slippage orders (all)
    scalars_result = MagicMock()
    scalars_result.scalars.return_value = iter(trades)

    all_result = MagicMock()
    all_result.all.return_value = []

    # BacktestRunRecord query: no walk-forward run
    wf_result = MagicMock()
    wf_result.scalar_one_or_none.return_value = None

    session.execute.side_effect = [scalars_result, all_result, wf_result]

    service = LivePerformanceReviewService(session)
    review = service.get_performance_review(
        exchange="binance",
        symbol="BTC/USDT",
    )

    assert review.recommendation == "halt"
    assert review.live_metrics is not None
    assert any("consecutive" in r.lower() for r in review.recommendation_reasons)


# ------------------------------------------------------------------
# Test: slippage over pause threshold → pause_and_rework
# ------------------------------------------------------------------


def test_high_slippage_triggers_pause_and_rework(session, monkeypatch):
    """Slippage > 2.0% must trigger pause_and_rework."""

    mock_shadow_repo = MagicMock()
    # Provide shadow trades so shadow_metrics has a win_rate
    shadow_trade = MagicMock()
    shadow_trade.net_pnl = Decimal("100")
    shadow_trade.quantity = Decimal("1")
    shadow_trade.simulated_fill_price = Decimal("100")
    mock_shadow_repo.list_closed.return_value = [shadow_trade] * 5

    mock_trade_repo = MagicMock()
    mock_trade_repo.get_consecutive_losses.return_value = 0

    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.ShadowTradeRepository",
        lambda session: mock_shadow_repo,
    )
    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.TradeRepository",
        lambda session: mock_trade_repo,
    )

    # Two live winning trades (so no halt trigger)
    live_trade = MagicMock(spec=TradeRecord)
    live_trade.realized_pnl = Decimal("50")
    live_trade.fee_amount = Decimal("1")
    live_trade.created_at = datetime.now(UTC)
    live_trade.price = Decimal("100")
    live_trade.quantity = Decimal("1")

    scalars_result = MagicMock()
    scalars_result.scalars.return_value = iter([live_trade, live_trade])

    # Slippage: signal_price=100, fill=102.5 → 2.5% slippage
    all_result = MagicMock()
    all_result.all.return_value = [
        (Decimal("100"), Decimal("102.5")),
        (Decimal("100"), Decimal("102.5")),
    ]

    wf_result = MagicMock()
    wf_result.scalar_one_or_none.return_value = None

    session.execute.side_effect = [scalars_result, all_result, wf_result]

    service = LivePerformanceReviewService(session)
    review = service.get_performance_review(
        exchange="binance",
        symbol="BTC/USDT",
    )

    assert review.recommendation == "pause_and_rework"
    assert any("slippage" in r.lower() for r in review.recommendation_reasons)
    assert review.root_cause.primary_driver == "execution_cost_overshoot"


# ------------------------------------------------------------------
# Test: moderate slippage → reduce_risk
# ------------------------------------------------------------------


def test_moderate_slippage_triggers_reduce_risk(session, monkeypatch):
    """Slippage > 1.0% but <= 2.0% must trigger reduce_risk."""

    mock_shadow_repo = MagicMock()
    shadow_trade = MagicMock()
    shadow_trade.net_pnl = Decimal("100")
    shadow_trade.quantity = Decimal("1")
    shadow_trade.simulated_fill_price = Decimal("100")
    mock_shadow_repo.list_closed.return_value = [shadow_trade] * 5

    mock_trade_repo = MagicMock()
    mock_trade_repo.get_consecutive_losses.return_value = 0

    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.ShadowTradeRepository",
        lambda session: mock_shadow_repo,
    )
    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.TradeRepository",
        lambda session: mock_trade_repo,
    )

    live_trade = MagicMock(spec=TradeRecord)
    live_trade.realized_pnl = Decimal("50")
    live_trade.fee_amount = Decimal("1")
    live_trade.created_at = datetime.now(UTC)
    live_trade.price = Decimal("100")
    live_trade.quantity = Decimal("1")

    scalars_result = MagicMock()
    scalars_result.scalars.return_value = iter([live_trade, live_trade])

    # Slippage: 1.5% → reduce_risk
    all_result = MagicMock()
    all_result.all.return_value = [
        (Decimal("100"), Decimal("101.5")),
        (Decimal("100"), Decimal("101.5")),
    ]

    wf_result = MagicMock()
    wf_result.scalar_one_or_none.return_value = None

    session.execute.side_effect = [scalars_result, all_result, wf_result]

    service = LivePerformanceReviewService(session)
    review = service.get_performance_review(
        exchange="binance",
        symbol="BTC/USDT",
    )

    assert review.recommendation == "reduce_risk"
    assert any("slippage" in r.lower() for r in review.recommendation_reasons)


# ------------------------------------------------------------------
# Test: no backtest run → oos_baseline is None
# ------------------------------------------------------------------


def test_no_backtest_run_produces_none_oos_baseline(session, monkeypatch):
    """When no walk-forward backtest run exists, oos_baseline should be None."""

    mock_shadow_repo = MagicMock()
    mock_shadow_repo.list_closed.return_value = []

    mock_trade_repo = MagicMock()
    mock_trade_repo.get_consecutive_losses.return_value = 0

    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.ShadowTradeRepository",
        lambda session: mock_shadow_repo,
    )
    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.TradeRepository",
        lambda session: mock_trade_repo,
    )

    # No live trades → _compute_live_metrics returns None early (no slippage query)
    # Execution order: (1) live trades query, (2) oos_baseline query
    scalars_result = MagicMock()
    scalars_result.scalars.return_value = iter([])

    wf_result = MagicMock()
    wf_result.scalar_one_or_none.return_value = None

    session.execute.side_effect = [scalars_result, wf_result]

    service = LivePerformanceReviewService(session)
    review = service.get_performance_review(
        exchange="binance",
        symbol="BTC/USDT",
    )

    assert review.oos_baseline is None


# ------------------------------------------------------------------
# Test: all healthy → keep_running
# ------------------------------------------------------------------


def test_healthy_live_metrics_returns_keep_running(session, monkeypatch):
    """A system with winning live trades and no anomalies should keep running."""

    mock_shadow_repo = MagicMock()
    shadow_trade = MagicMock()
    shadow_trade.net_pnl = Decimal("80")
    shadow_trade.quantity = Decimal("1")
    shadow_trade.simulated_fill_price = Decimal("100")
    mock_shadow_repo.list_closed.return_value = [shadow_trade] * 10

    mock_trade_repo = MagicMock()
    mock_trade_repo.get_consecutive_losses.return_value = 1

    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.ShadowTradeRepository",
        lambda session: mock_shadow_repo,
    )
    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.TradeRepository",
        lambda session: mock_trade_repo,
    )

    live_trade = MagicMock(spec=TradeRecord)
    live_trade.realized_pnl = Decimal("100")
    live_trade.fee_amount = Decimal("1")
    live_trade.created_at = datetime.now(UTC)
    live_trade.price = Decimal("100")
    live_trade.quantity = Decimal("1")

    scalars_result = MagicMock()
    scalars_result.scalars.return_value = iter([live_trade, live_trade, live_trade])

    # Low slippage: 0.3%
    all_result = MagicMock()
    all_result.all.return_value = [
        (Decimal("100"), Decimal("100.3")),
    ]

    wf_result = MagicMock()
    wf_result.scalar_one_or_none.return_value = None

    session.execute.side_effect = [scalars_result, all_result, wf_result]

    service = LivePerformanceReviewService(session)
    review = service.get_performance_review(
        exchange="binance",
        symbol="BTC/USDT",
    )

    assert review.recommendation == "keep_running"
    assert review.live_metrics is not None
    assert review.live_metrics.trade_count == 3
    assert review.root_cause.primary_driver == "within_expected_variation"


def test_modeled_slippage_baseline_reduces_observed_overshoot(session, monkeypatch):
    mock_shadow_repo = MagicMock()
    shadow_trade = MagicMock()
    shadow_trade.net_pnl = Decimal("100")
    shadow_trade.quantity = Decimal("1")
    shadow_trade.simulated_fill_price = Decimal("100")
    mock_shadow_repo.list_closed.return_value = [shadow_trade] * 5

    mock_trade_repo = MagicMock()
    mock_trade_repo.get_consecutive_losses.return_value = 0

    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.ShadowTradeRepository",
        lambda session: mock_shadow_repo,
    )
    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.TradeRepository",
        lambda session: mock_trade_repo,
    )

    live_trade = MagicMock(spec=TradeRecord)
    live_trade.realized_pnl = Decimal("50")
    live_trade.fee_amount = Decimal("1")
    live_trade.created_at = datetime.now(UTC)
    live_trade.price = Decimal("100")
    live_trade.quantity = Decimal("1")

    scalars_result = MagicMock()
    scalars_result.scalars.return_value = iter([live_trade, live_trade])

    all_result = MagicMock()
    all_result.all.return_value = [
        (Decimal("100"), Decimal("101.5")),
        (Decimal("100"), Decimal("101.5")),
    ]

    wf_result = MagicMock()
    wf_result.scalar_one_or_none.return_value = _make_wf_run(
        slippage_pct="0.8",
        spread_pct="0.4",
    )

    session.execute.side_effect = [scalars_result, all_result, wf_result]

    service = LivePerformanceReviewService(session)
    review = service.get_performance_review(exchange="binance", symbol="BTC/USDT")

    assert review.oos_baseline is not None
    assert review.oos_baseline.modeled_slippage_pct == Decimal("1.2")
    assert review.health_indicators.slippage_vs_model_pct == Decimal("0.3")
    assert review.recommendation == "keep_running"
    assert review.root_cause.primary_driver == "within_expected_variation"


def test_shadow_vs_oos_drift_uses_return_pct_basis(session, monkeypatch):
    mock_shadow_repo = MagicMock()
    shadow_trade = MagicMock()
    shadow_trade.net_pnl = Decimal("10")
    shadow_trade.quantity = Decimal("1")
    shadow_trade.simulated_fill_price = Decimal("100")
    mock_shadow_repo.list_closed.return_value = [shadow_trade] * 5

    mock_trade_repo = MagicMock()
    mock_trade_repo.get_consecutive_losses.return_value = 0

    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.ShadowTradeRepository",
        lambda session: mock_shadow_repo,
    )
    monkeypatch.setattr(
        "app.application.services.live_performance_review_service.TradeRepository",
        lambda session: mock_trade_repo,
    )

    scalars_result = MagicMock()
    scalars_result.scalars.return_value = iter([])

    wf_result = MagicMock()
    wf_result.scalar_one_or_none.return_value = _make_wf_run(oos_return_pct="20.0")

    session.execute.side_effect = [scalars_result, wf_result]

    service = LivePerformanceReviewService(session)
    review = service.get_performance_review(exchange="binance", symbol="BTC/USDT")

    assert review.shadow_metrics.total_return_pct == Decimal("10")
    assert review.health_indicators.shadow_vs_oos_expectancy_drift == Decimal("-50")
    assert review.root_cause.primary_driver == "strategy_or_regime_drift"
