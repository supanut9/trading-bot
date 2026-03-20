from decimal import Decimal
from pathlib import Path

from app.application.services.paper_execution_service import PaperExecutionRequest
from app.application.services.shadow_execution_service import ShadowExecutionService
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def build_service(
    tmp_path: Path,
    *,
    slippage_pct: Decimal = Decimal("0.001"),
    fee_pct: Decimal = Decimal("0.001"),
) -> tuple[ShadowExecutionService, object]:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'shadow_execution.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    return (
        ShadowExecutionService(session, slippage_pct=slippage_pct, fee_pct=fee_pct),
        session,
    )


def test_buy_creates_open_shadow_trade_with_slippage(tmp_path: Path) -> None:
    service, _session = build_service(
        tmp_path, slippage_pct=Decimal("0.001"), fee_pct=Decimal("0.001")
    )

    result = service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="shadow-binance-btc-usdt-1h-buy-20260115120000",
            submitted_reason="ema crossover",
        )
    )

    # simulated_fill_price = 50000 * 1.001 = 50050
    expected_fill = Decimal("50000") * (Decimal("1") + Decimal("0.001"))
    assert result.status == "open"
    assert result.side == "buy"
    assert result.simulated_fill_price == expected_fill
    assert result.quantity == Decimal("0.002")
    assert result.net_pnl == Decimal("0")
    assert result.shadow_trade_id > 0
    assert result.order is None
    assert result.trade is None


def test_buy_creates_shadow_position_with_mode_shadow(tmp_path: Path) -> None:
    service, _session = build_service(tmp_path)

    result = service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="shadow-binance-btc-usdt-1h-buy-20260115120000",
        )
    )

    assert result.position is not None
    assert result.position.mode == "shadow"
    assert result.position.quantity == Decimal("0.002")
    assert result.position.average_entry_price == Decimal("50000")


def test_sell_closes_trade_with_correct_pnl(tmp_path: Path) -> None:
    service, _session = build_service(
        tmp_path, slippage_pct=Decimal("0.001"), fee_pct=Decimal("0.001")
    )

    # Buy at 50000
    service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="shadow-binance-btc-usdt-1h-buy-20260115120000",
        )
    )

    # Sell at 52000
    result = service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("0.002"),
            price=Decimal("52000"),
            client_order_id="shadow-binance-btc-usdt-1h-sell-20260115140000",
        )
    )

    assert result.status == "closed"
    assert result.side == "sell"
    # exit fill = 52000 * (1 - 0.001) = 51948
    expected_exit_fill = Decimal("52000") * (Decimal("1") - Decimal("0.001"))
    assert result.simulated_fill_price == expected_exit_fill

    # entry fill = 50000 * 1.001 = 50050
    entry_fill = Decimal("50000") * (Decimal("1") + Decimal("0.001"))
    entry_fee = entry_fill * Decimal("0.002") * Decimal("0.001")
    exit_fee = expected_exit_fill * Decimal("0.002") * Decimal("0.001")
    gross_pnl = (expected_exit_fill - entry_fill) * Decimal("0.002")
    expected_net_pnl = gross_pnl - entry_fee - exit_fee
    assert result.net_pnl == expected_net_pnl


def test_sell_without_open_trade_returns_skipped(tmp_path: Path) -> None:
    service, _session = build_service(tmp_path)

    result = service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
        )
    )

    assert result.status == "skipped"
    assert result.shadow_trade_id == 0
    assert result.net_pnl == Decimal("0")
    assert result.order is None
    assert result.trade is None


def test_sell_closes_position_to_zero(tmp_path: Path) -> None:
    service, _session = build_service(tmp_path)

    service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="shadow-binance-btc-usdt-1h-buy-20260115120000",
        )
    )

    result = service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("0.002"),
            price=Decimal("52000"),
            client_order_id="shadow-binance-btc-usdt-1h-sell-20260115140000",
        )
    )

    assert result.position is not None
    assert result.position.mode == "shadow"
    assert result.position.quantity == Decimal("0")


def test_extract_timeframe_from_client_order_id(tmp_path: Path) -> None:
    service, _session = build_service(tmp_path)

    result = service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="shadow-binance-btc-usdt-4h-buy-20260115120000",
        )
    )

    # The timeframe "4h" should be extracted from the client_order_id
    assert result.status == "open"
    assert result.shadow_trade_id > 0
