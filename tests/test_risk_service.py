from decimal import Decimal

from app.domain.risk import PortfolioState, RiskLimits, RiskService, TradeContext
from app.domain.strategies.base import Signal


def build_service() -> RiskService:
    return RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=True,
        )
    )


def build_signal() -> Signal:
    return Signal(
        action="buy",
        reason="test signal",
        fast_value=Decimal("101"),
        slow_value=Decimal("100"),
    )


def test_approves_trade_and_calculates_position_size() -> None:
    service = build_service()

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            daily_realized_loss_pct=Decimal("0.00"),
            trading_mode="paper",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is True
    assert decision.reason == "risk checks passed"
    assert decision.quantity == Decimal("0.00200000")


def test_rejects_trade_when_live_mode_is_used() -> None:
    service = build_service()

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            daily_realized_loss_pct=Decimal("0.00"),
            trading_mode="live",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.reason == "live trading is not allowed by risk policy"


def test_rejects_trade_when_max_open_positions_is_reached() -> None:
    service = build_service()

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=1,
            daily_realized_loss_pct=Decimal("0.00"),
            trading_mode="paper",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.reason == "max open positions reached"


def test_rejects_trade_when_daily_loss_limit_is_reached() -> None:
    service = build_service()

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            daily_realized_loss_pct=Decimal("0.03"),
            trading_mode="paper",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.reason == "daily loss limit reached"


def test_rejects_trade_when_entry_price_is_invalid() -> None:
    service = build_service()

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            daily_realized_loss_pct=Decimal("0.00"),
            trading_mode="paper",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("0")),
    )

    assert decision.approved is False
    assert decision.reason == "entry price must be positive"
