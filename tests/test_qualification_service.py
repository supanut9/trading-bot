from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.application.services.qualification_service import (
    _MAX_OOS_DRAWDOWN_PCT,
    _MAX_RETURN_DEGRADATION_PCT,
    _MIN_SHADOW_TRADES,
    QualificationService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_session(*, wf_run=None, closed_trades=None):
    """Return a mock Session pre-wired with the given fixtures."""
    session = MagicMock()
    # Scalar result for the walk-forward backtest query
    session.execute.return_value.scalar_one_or_none.return_value = wf_run
    return session, closed_trades or []


def make_wf_run(
    *,
    id: int = 1,
    oos_return_pct: str = "5.00",
    oos_drawdown_pct: str = "10.00",
    in_sample_return_pct: str = "8.00",
    degradation_pct: str = "10.00",
    overfitting_warning: bool = False,
):
    run = MagicMock()
    run.id = id
    run.walk_forward_oos_return_pct = Decimal(oos_return_pct)
    run.walk_forward_oos_drawdown_pct = Decimal(oos_drawdown_pct)
    run.walk_forward_in_sample_return_pct = Decimal(in_sample_return_pct)
    run.walk_forward_return_degradation_pct = Decimal(degradation_pct)
    run.walk_forward_overfitting_warning = overfitting_warning
    return run


@dataclass
class FakeShadowTrade:
    net_pnl: Decimal | None


def make_closed_trades(*, wins: int, losses: int, win_pnl: str = "50", loss_pnl: str = "-30"):
    trades = []
    for _ in range(wins):
        trades.append(FakeShadowTrade(net_pnl=Decimal(win_pnl)))
    for _ in range(losses):
        trades.append(FakeShadowTrade(net_pnl=Decimal(loss_pnl)))
    return trades


# ---------------------------------------------------------------------------
# All gates pass
# ---------------------------------------------------------------------------


def test_all_gates_pass_when_evidence_is_sufficient():
    wf_run = make_wf_run()
    # wins=20 @ +50, losses=10 @ -5 → drawdown = (10*5)/1000 = 5% < 25%
    closed = make_closed_trades(wins=20, losses=10, loss_pnl="-5")  # 30 trades total

    with patch.object(
        QualificationService,
        "_latest_walk_forward_run",
        return_value=wf_run,
    ):
        session = MagicMock()
        svc = QualificationService(session)
        svc._shadow_trades = MagicMock()
        svc._shadow_trades.list_closed.return_value = closed

        report = svc.evaluate(exchange="binance", symbol="BTC/USDT")

    assert report.all_passed is True
    assert report.exchange == "binance"
    assert report.symbol == "BTC/USDT"
    assert all(g.passed for g in report.gates)


# ---------------------------------------------------------------------------
# Gate 1: walk_forward_run_exists
# ---------------------------------------------------------------------------


def test_gate_fails_when_no_walk_forward_run():
    with patch.object(
        QualificationService,
        "_latest_walk_forward_run",
        return_value=None,
    ):
        session = MagicMock()
        svc = QualificationService(session)
        svc._shadow_trades = MagicMock()
        svc._shadow_trades.list_closed.return_value = []

        report = svc.evaluate(exchange="binance", symbol="BTC/USDT")

    assert report.all_passed is False
    gate = next(g for g in report.gates if g.name == "walk_forward_run_exists")
    assert gate.passed is False


# ---------------------------------------------------------------------------
# Gate 2: oos_positive_return
# ---------------------------------------------------------------------------


def test_gate_fails_when_oos_return_is_negative():
    wf_run = make_wf_run(oos_return_pct="-2.00")
    closed = make_closed_trades(wins=20, losses=10)

    with patch.object(QualificationService, "_latest_walk_forward_run", return_value=wf_run):
        session = MagicMock()
        svc = QualificationService(session)
        svc._shadow_trades = MagicMock()
        svc._shadow_trades.list_closed.return_value = closed

        report = svc.evaluate(exchange="binance", symbol="BTC/USDT")

    gate = next(g for g in report.gates if g.name == "oos_positive_return")
    assert gate.passed is False
    assert report.all_passed is False


# ---------------------------------------------------------------------------
# Gate 3: oos_drawdown_acceptable
# ---------------------------------------------------------------------------


def test_gate_fails_when_oos_drawdown_exceeds_threshold():
    wf_run = make_wf_run(oos_drawdown_pct=str(_MAX_OOS_DRAWDOWN_PCT + Decimal("1")))
    closed = make_closed_trades(wins=20, losses=10)

    with patch.object(QualificationService, "_latest_walk_forward_run", return_value=wf_run):
        session = MagicMock()
        svc = QualificationService(session)
        svc._shadow_trades = MagicMock()
        svc._shadow_trades.list_closed.return_value = closed

        report = svc.evaluate(exchange="binance", symbol="BTC/USDT")

    gate = next(g for g in report.gates if g.name == "oos_drawdown_acceptable")
    assert gate.passed is False


# ---------------------------------------------------------------------------
# Gate 4: no_overfitting
# ---------------------------------------------------------------------------


def test_gate_fails_when_overfitting_warning_is_set():
    wf_run = make_wf_run(overfitting_warning=True)
    closed = make_closed_trades(wins=20, losses=10)

    with patch.object(QualificationService, "_latest_walk_forward_run", return_value=wf_run):
        session = MagicMock()
        svc = QualificationService(session)
        svc._shadow_trades = MagicMock()
        svc._shadow_trades.list_closed.return_value = closed

        report = svc.evaluate(exchange="binance", symbol="BTC/USDT")

    gate = next(g for g in report.gates if g.name == "no_overfitting")
    assert gate.passed is False


def test_gate_fails_when_degradation_exceeds_threshold():
    wf_run = make_wf_run(degradation_pct=str(_MAX_RETURN_DEGRADATION_PCT + Decimal("1")))
    closed = make_closed_trades(wins=20, losses=10)

    with patch.object(QualificationService, "_latest_walk_forward_run", return_value=wf_run):
        session = MagicMock()
        svc = QualificationService(session)
        svc._shadow_trades = MagicMock()
        svc._shadow_trades.list_closed.return_value = closed

        report = svc.evaluate(exchange="binance", symbol="BTC/USDT")

    gate = next(g for g in report.gates if g.name == "no_overfitting")
    assert gate.passed is False


# ---------------------------------------------------------------------------
# Gate 5: shadow_trade_count
# ---------------------------------------------------------------------------


def test_gate_fails_when_shadow_trade_count_is_below_minimum():
    wf_run = make_wf_run()
    closed = make_closed_trades(wins=10, losses=5)  # only 15 trades

    with patch.object(QualificationService, "_latest_walk_forward_run", return_value=wf_run):
        session = MagicMock()
        svc = QualificationService(session)
        svc._shadow_trades = MagicMock()
        svc._shadow_trades.list_closed.return_value = closed

        report = svc.evaluate(exchange="binance", symbol="BTC/USDT")

    gate = next(g for g in report.gates if g.name == "shadow_trade_count")
    assert gate.passed is False
    assert str(_MIN_SHADOW_TRADES) in gate.reason


def test_gate_passes_at_exactly_minimum_shadow_trades():
    wf_run = make_wf_run()
    closed = make_closed_trades(wins=20, losses=10)  # exactly 30

    with patch.object(QualificationService, "_latest_walk_forward_run", return_value=wf_run):
        session = MagicMock()
        svc = QualificationService(session)
        svc._shadow_trades = MagicMock()
        svc._shadow_trades.list_closed.return_value = closed

        report = svc.evaluate(exchange="binance", symbol="BTC/USDT")

    gate = next(g for g in report.gates if g.name == "shadow_trade_count")
    assert gate.passed is True


# ---------------------------------------------------------------------------
# Gate 6: shadow_positive_expectancy
# ---------------------------------------------------------------------------


def test_gate_fails_when_shadow_expectancy_is_negative():
    wf_run = make_wf_run()
    # all losses
    closed = make_closed_trades(wins=0, losses=30, loss_pnl="-20")

    with patch.object(QualificationService, "_latest_walk_forward_run", return_value=wf_run):
        session = MagicMock()
        svc = QualificationService(session)
        svc._shadow_trades = MagicMock()
        svc._shadow_trades.list_closed.return_value = closed

        report = svc.evaluate(exchange="binance", symbol="BTC/USDT")

    gate = next(g for g in report.gates if g.name == "shadow_positive_expectancy")
    assert gate.passed is False


def test_gate_fails_when_no_shadow_trades():
    wf_run = make_wf_run()

    with patch.object(QualificationService, "_latest_walk_forward_run", return_value=wf_run):
        session = MagicMock()
        svc = QualificationService(session)
        svc._shadow_trades = MagicMock()
        svc._shadow_trades.list_closed.return_value = []

        report = svc.evaluate(exchange="binance", symbol="BTC/USDT")

    gate = next(g for g in report.gates if g.name == "shadow_positive_expectancy")
    assert gate.passed is False


# ---------------------------------------------------------------------------
# Gate 7: shadow_drawdown_acceptable
# ---------------------------------------------------------------------------


def test_gate_fails_when_shadow_drawdown_exceeds_threshold():
    wf_run = make_wf_run()
    # Big drawdown: gains then large losses
    closed = [FakeShadowTrade(net_pnl=Decimal("100"))] + [
        FakeShadowTrade(net_pnl=Decimal("-5")) for _ in range(29)
    ]

    with patch.object(QualificationService, "_latest_walk_forward_run", return_value=wf_run):
        session = MagicMock()
        svc = QualificationService(session)
        svc._shadow_trades = MagicMock()
        svc._shadow_trades.list_closed.return_value = closed

        report = svc.evaluate(exchange="binance", symbol="BTC/USDT")

    gate = next(g for g in report.gates if g.name == "shadow_drawdown_acceptable")
    # peak=100, then 29*(-5)=-145 cumulative → drawdown 145% > 25%
    assert gate.passed is False


# ---------------------------------------------------------------------------
# Evidence fields
# ---------------------------------------------------------------------------


def test_gate_evidence_is_populated():
    wf_run = make_wf_run()
    closed = make_closed_trades(wins=20, losses=10)

    with patch.object(QualificationService, "_latest_walk_forward_run", return_value=wf_run):
        session = MagicMock()
        svc = QualificationService(session)
        svc._shadow_trades = MagicMock()
        svc._shadow_trades.list_closed.return_value = closed

        report = svc.evaluate(exchange="binance", symbol="BTC/USDT")

    gate = next(g for g in report.gates if g.name == "walk_forward_run_exists")
    assert gate.evidence is not None
    assert "backtest_run_id" in gate.evidence
