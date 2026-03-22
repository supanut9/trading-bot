from decimal import Decimal

from app.domain.order_rules import SymbolRules
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


def build_exit_signal() -> Signal:
    return Signal(
        action="sell",
        reason="test exit signal",
        fast_value=Decimal("99"),
        slow_value=Decimal("100"),
    )


def test_approves_trade_and_calculates_position_size() -> None:
    service = build_service()

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="paper",
            trading_mode="SPOT",
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
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="live",
            trading_mode="SPOT",
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
            current_position_quantity=Decimal("0.50000000"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="paper",
            trading_mode="SPOT",
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
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.03"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="paper",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.reason == "daily loss limit reached"


def test_allows_exit_signal_when_max_open_positions_is_reached() -> None:
    service = build_service()

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=1,
            current_position_quantity=Decimal("0.50000000"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="paper",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_exit_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is True
    assert decision.reason == "risk checks passed"


def test_allows_exit_signal_when_daily_loss_limit_is_reached() -> None:
    service = build_service()

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=1,
            current_position_quantity=Decimal("0.50000000"),
            daily_realized_loss_pct=Decimal("0.03"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="paper",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_exit_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is True
    assert decision.reason == "risk checks passed"


def test_rejects_trade_when_entry_price_is_invalid() -> None:
    service = build_service()

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="paper",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("0")),
    )

    assert decision.approved is False
    assert decision.reason == "entry price must be positive"


def test_rejects_live_entry_when_live_trading_is_halted() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=False,
            live_trading_halted=True,
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="live",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.reason == "live trading is halted by configuration"


def test_rejects_live_entry_when_order_notional_exceeds_limit() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=False,
            live_max_order_notional=Decimal("50"),
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="live",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.reason == "live order notional exceeds configured limit"


def test_rejects_live_entry_when_position_quantity_exceeds_limit() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=False,
            live_max_position_quantity=Decimal("0.00300000"),
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            current_position_quantity=Decimal("0.00200000"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="live",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.reason == "live position quantity exceeds configured limit"


def test_rejects_live_entry_when_total_exposure_exceeds_limit() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=5,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=False,
            live_max_total_exposure_notional=Decimal("140"),
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=1,
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.01"),
            consecutive_losses=0,
            execution_mode="live",
            trading_mode="SPOT",
            total_open_exposure_notional=Decimal("100"),
            current_symbol_exposure_notional=Decimal("0"),
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.is_hard_violation is True
    assert decision.reason == "live total exposure exceeds configured limit"


def test_rejects_live_entry_when_symbol_exposure_exceeds_limit() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=5,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=False,
            live_max_symbol_exposure_notional=Decimal("150"),
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=1,
            current_position_quantity=Decimal("0.00100000"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.01"),
            consecutive_losses=0,
            execution_mode="live",
            trading_mode="SPOT",
            total_open_exposure_notional=Decimal("100"),
            current_symbol_exposure_notional=Decimal("120"),
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.is_hard_violation is True
    assert decision.reason == "live symbol exposure exceeds configured limit"


def test_rejects_live_entry_when_symbol_concentration_exceeds_limit() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=5,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=False,
            live_max_symbol_concentration_pct=Decimal("0.60"),
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=1,
            current_position_quantity=Decimal("0.00100000"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.01"),
            consecutive_losses=0,
            execution_mode="live",
            trading_mode="SPOT",
            total_open_exposure_notional=Decimal("100"),
            current_symbol_exposure_notional=Decimal("40"),
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.is_hard_violation is True
    assert decision.reason == "live symbol concentration exceeds configured limit"


def test_rejects_live_entry_when_live_concurrent_positions_limit_is_reached() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=5,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=False,
            live_max_concurrent_positions=2,
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=2,
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.02"),
            consecutive_losses=0,
            execution_mode="live",
            trading_mode="SPOT",
            total_open_exposure_notional=Decimal("200"),
            current_symbol_exposure_notional=Decimal("0"),
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.is_hard_violation is True
    assert decision.reason == "live max concurrent positions reached"


def test_allows_live_exit_when_live_trading_is_halted() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=False,
            live_trading_halted=True,
            live_max_order_notional=Decimal("1"),
            live_max_position_quantity=Decimal("0.00100000"),
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=1,
            current_position_quantity=Decimal("0.50000000"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="live",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_exit_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is True
    assert decision.reason == "risk checks passed"


def build_btc_rules(
    *,
    min_qty: str = "0.00001",
    max_qty: str = "9000",
    step_size: str = "0.00001",
    min_notional: str = "10",
) -> SymbolRules:
    return SymbolRules(
        exchange="binance",
        symbol="BTC/USDT",
        min_qty=Decimal(min_qty),
        max_qty=Decimal(max_qty),
        step_size=Decimal(step_size),
        min_notional=Decimal(min_notional),
        tick_size=Decimal("0.01"),
    )


def test_snaps_quantity_to_step_size_when_symbol_rules_present() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=True,
            symbol_rules=build_btc_rules(step_size="0.001"),
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="paper",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is True
    # raw quantity = 10000 * 0.01 / 50000 = 0.002, snapped to 0.001 step => 0.002 exactly
    assert decision.quantity == Decimal("0.002")


def test_rejects_when_quantity_below_min_qty_after_snap() -> None:
    # raw qty = 10000 * 0.0001 / 50000 = 0.00002; step_size=0.00001 snaps to 0.00002;
    # 0.00002 < min_qty=0.001 → rejected
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.0001"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=True,
            symbol_rules=build_btc_rules(min_qty="0.001", step_size="0.00001"),
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="paper",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert "below exchange minimum" in decision.reason


def test_rejects_when_notional_below_min_after_snap() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=True,
            symbol_rules=build_btc_rules(min_notional="200"),
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("100"),
            open_positions=0,
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="paper",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert "below exchange minimum" in decision.reason


def test_rejects_trade_when_weekly_loss_limit_is_reached() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            max_weekly_loss_pct=Decimal("0.05"),
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.01"),
            weekly_realized_loss_pct=Decimal("0.05"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="paper",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.reason == "weekly loss limit reached"


def test_rejects_trade_when_consecutive_losses_limit_is_reached() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            max_consecutive_losses=3,
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=3,
            execution_mode="paper",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.reason == "max consecutive losses (3) reached"


def test_rejects_trade_when_concurrent_exposure_limit_is_reached() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=5,
            max_daily_loss_pct=Decimal("0.03"),
            max_concurrent_exposure_pct=Decimal("0.50"),
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=2,
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.00"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.51"),
            consecutive_losses=0,
            execution_mode="paper",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.reason == "max concurrent exposure reached"


def test_rejects_as_hard_violation_for_major_breaches() -> None:
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            max_weekly_loss_pct=Decimal("0.05"),
        )
    )

    decision = service.evaluate(
        portfolio=PortfolioState(
            account_equity=Decimal("10000"),
            open_positions=0,
            current_position_quantity=Decimal("0"),
            daily_realized_loss_pct=Decimal("0.035"),
            weekly_realized_loss_pct=Decimal("0.00"),
            concurrent_exposure_pct=Decimal("0.00"),
            consecutive_losses=0,
            execution_mode="paper",
            trading_mode="SPOT",
        ),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000")),
    )

    assert decision.approved is False
    assert decision.is_hard_violation is True
    assert decision.reason == "daily loss limit reached"


def build_portfolio(equity: str = "10000") -> PortfolioState:
    return PortfolioState(
        account_equity=Decimal(equity),
        open_positions=0,
        current_position_quantity=Decimal("0"),
        daily_realized_loss_pct=Decimal("0"),
        weekly_realized_loss_pct=Decimal("0"),
        concurrent_exposure_pct=Decimal("0"),
        consecutive_losses=0,
        execution_mode="paper",
        trading_mode="SPOT",
    )


def test_volatility_sizing_uses_atr_as_divisor() -> None:
    """With volatility sizing, quantity = dollar_risk / atr instead of / entry_price."""
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=True,
            volatility_sizing_enabled=True,
        )
    )
    # equity=10000, risk=1% → dollar_risk=100; atr=500 → qty=100/500=0.2
    decision = service.evaluate(
        portfolio=build_portfolio("10000"),
        trade=TradeContext(
            signal=build_signal(),
            entry_price=Decimal("50000"),
            atr_value=Decimal("500"),
        ),
    )
    assert decision.approved is True
    assert decision.quantity == Decimal("0.20000000")


def test_volatility_sizing_falls_back_to_price_when_atr_is_none() -> None:
    """When atr_value is None, falls back to price-based sizing even if flag is enabled."""
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=True,
            volatility_sizing_enabled=True,
        )
    )
    decision = service.evaluate(
        portfolio=build_portfolio("10000"),
        trade=TradeContext(signal=build_signal(), entry_price=Decimal("50000"), atr_value=None),
    )
    assert decision.approved is True
    assert decision.quantity == Decimal("0.00200000")


def test_volatility_sizing_disabled_uses_price_even_with_atr_provided() -> None:
    """When flag is off, ATR is ignored and price-based sizing is used."""
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=True,
            volatility_sizing_enabled=False,
        )
    )
    decision = service.evaluate(
        portfolio=build_portfolio("10000"),
        trade=TradeContext(
            signal=build_signal(),
            entry_price=Decimal("50000"),
            atr_value=Decimal("500"),
        ),
    )
    assert decision.approved is True
    assert decision.quantity == Decimal("0.00200000")


def test_volatility_sizing_smaller_when_high_volatility() -> None:
    """High ATR → smaller quantity than low ATR (same equity and risk%)."""
    service = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.03"),
            paper_trading_only=True,
            volatility_sizing_enabled=True,
        )
    )
    low_vol = service.evaluate(
        portfolio=build_portfolio(),
        trade=TradeContext(
            signal=build_signal(), entry_price=Decimal("100"), atr_value=Decimal("1")
        ),
    )
    high_vol = service.evaluate(
        portfolio=build_portfolio(),
        trade=TradeContext(
            signal=build_signal(), entry_price=Decimal("100"), atr_value=Decimal("5")
        ),
    )
    assert low_vol.approved and high_vol.approved
    assert low_vol.quantity > high_vol.quantity
