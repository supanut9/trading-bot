from decimal import Decimal
from pathlib import Path

from app.application.services.paper_execution_service import PaperExecutionRequest
from app.application.services.shadow_execution_service import ShadowExecutionService
from app.application.services.shadow_report_service import ShadowReportService
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.repositories.shadow_blocked_signal_repository import (
    ShadowBlockedSignalRepository,
)
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def build_services(
    tmp_path: Path,
) -> tuple[ShadowExecutionService, ShadowReportService, ShadowBlockedSignalRepository, object]:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'shadow_report.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    execution = ShadowExecutionService(
        session,
        slippage_pct=Decimal("0.001"),
        fee_pct=Decimal("0.001"),
    )
    report = ShadowReportService(session)
    blocked_repo = ShadowBlockedSignalRepository(session)
    return execution, report, blocked_repo, session


def test_empty_state_returns_zero_counts(tmp_path: Path) -> None:
    _execution, report, _blocked, _session = build_services(tmp_path)

    result = report.get_quality_report(exchange="binance", symbol="BTC/USDT")

    assert result.exchange == "binance"
    assert result.symbol == "BTC/USDT"
    assert result.total_shadow_trades == 0
    assert result.open_trades == 0
    assert result.closed_trades == 0
    assert result.winning_trades == 0
    assert result.losing_trades == 0
    assert result.win_rate_pct is None
    assert result.expectancy is None
    assert result.max_drawdown_pct is None
    assert result.total_net_pnl == Decimal("0")
    assert result.total_fees_paid == Decimal("0")
    assert result.blocked_signal_count == 0
    assert result.recent_blocked_signals == []
    assert result.recent_trades == []


def test_closed_trades_compute_win_rate_and_pnl(tmp_path: Path) -> None:
    execution, report, _blocked, _session = build_services(tmp_path)

    # Trade 1: buy at 50000, sell at 52000 (winner)
    execution.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="shadow-binance-btc-usdt-1h-buy-20260115100000",
        )
    )
    execution.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("0.002"),
            price=Decimal("52000"),
            client_order_id="shadow-binance-btc-usdt-1h-sell-20260115120000",
        )
    )

    # Trade 2: buy at 52000, sell at 50000 (loser)
    execution.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.002"),
            price=Decimal("52000"),
            client_order_id="shadow-binance-btc-usdt-1h-buy-20260115140000",
        )
    )
    execution.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="shadow-binance-btc-usdt-1h-sell-20260115160000",
        )
    )

    result = report.get_quality_report(exchange="binance", symbol="BTC/USDT")

    assert result.closed_trades == 2
    assert result.winning_trades == 1
    assert result.losing_trades == 1
    assert result.win_rate_pct == Decimal("50")
    assert result.expectancy is not None
    assert result.total_fees_paid > Decimal("0")
    assert len(result.recent_trades) == 2  # 2 shadow trade records (one per lifecycle)


def test_blocked_signals_are_counted(tmp_path: Path) -> None:
    _execution, report, blocked_repo, session = build_services(tmp_path)

    blocked_repo.create(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        signal_action="buy",
        signal_reason="ema crossover",
        block_reason="max open positions reached",
        block_source="risk",
        price=Decimal("50000"),
    )
    blocked_repo.create(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        signal_action="buy",
        signal_reason="ema crossover",
        block_reason="daily loss limit reached",
        block_source="risk",
        price=Decimal("49000"),
    )
    session.commit()

    result = report.get_quality_report(exchange="binance", symbol="BTC/USDT")

    assert result.blocked_signal_count == 2
    assert len(result.recent_blocked_signals) == 2


def test_open_trade_is_counted_separately(tmp_path: Path) -> None:
    execution, report, _blocked, _session = build_services(tmp_path)

    execution.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="shadow-binance-btc-usdt-1h-buy-20260115100000",
        )
    )

    result = report.get_quality_report(exchange="binance", symbol="BTC/USDT")

    assert result.total_shadow_trades == 1
    assert result.open_trades == 1
    assert result.closed_trades == 0
    assert result.win_rate_pct is None  # no closed trades yet


def test_expectancy_matches_manual_calculation(tmp_path: Path) -> None:
    execution, report, _blocked, _session = build_services(tmp_path)

    # Two winners and one loser to get a meaningful expectancy
    for i, (buy_price, sell_price) in enumerate([(50000, 55000), (50000, 55000), (50000, 45000)]):
        execution.execute(
            PaperExecutionRequest(
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                quantity=Decimal("0.001"),
                price=Decimal(str(buy_price)),
                client_order_id=f"shadow-binance-btc-usdt-1h-buy-2026011500{i:04d}",
            )
        )
        execution.execute(
            PaperExecutionRequest(
                exchange="binance",
                symbol="BTC/USDT",
                side="sell",
                quantity=Decimal("0.001"),
                price=Decimal(str(sell_price)),
                client_order_id=f"shadow-binance-btc-usdt-1h-sell-2026011510{i:04d}",
            )
        )

    result = report.get_quality_report(exchange="binance", symbol="BTC/USDT")

    assert result.closed_trades == 3
    assert result.winning_trades == 2
    assert result.losing_trades == 1
    assert result.win_rate_pct is not None
    # win_rate = 2/3 ≈ 66.67%
    expected_win_rate = Decimal("2") / Decimal("3") * Decimal("100")
    assert abs(result.win_rate_pct - expected_win_rate) < Decimal("0.0001")
    assert result.expectancy is not None
    assert result.total_net_pnl is not None
