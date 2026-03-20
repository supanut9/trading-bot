from decimal import Decimal
from pathlib import Path

from app.application.services.live_risk_hard_gate_service import LiveRiskHardGateService
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.position import PositionRecord
from app.infrastructure.database.models.trade import TradeRecord
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def build_service(tmp_path: Path, settings: Settings) -> tuple[LiveRiskHardGateService, object]:
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    return LiveRiskHardGateService(session, settings), session


def test_live_trading_disabled(tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'live_risk_test.db'}",
        LIVE_TRADING_ENABLED=False,
        PAPER_TRADING=True,
    )
    service, session = build_service(tmp_path, settings)
    report = service.evaluate("binance", "BTC/USDT")
    assert not report.should_halt
    assert report.reason is None


def test_max_concurrent_exposure(tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'live_risk_test.db'}",
        LIVE_TRADING_ENABLED=True,
        PAPER_TRADING=False,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_MAX_CONCURRENT_EXPOSURE_NOTIONAL=Decimal("100"),
    )
    service, session = build_service(tmp_path, settings)

    session.add(
        PositionRecord(
            exchange="binance",
            symbol="BTC/USDT",
            mode="live",
            quantity=Decimal("1"),
            average_entry_price=Decimal("150"),
        )
    )
    session.commit()

    report = service.evaluate("binance", "BTC/USDT")
    assert report.should_halt
    assert report.reason is not None and report.reason.startswith("max_exposure_exceeded_canary")


def test_repeated_reject_auto_halt(tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'live_risk_test.db'}",
        LIVE_TRADING_ENABLED=True,
        PAPER_TRADING=False,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_REPEATED_REJECT_AUTO_HALT_THRESHOLD=3,
    )
    service, session = build_service(tmp_path, settings)

    # Add 3 rejected orders
    for _ in range(3):
        session.add(
            OrderRecord(
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                order_type="market",
                status="rejected",
                mode="live",
                quantity=Decimal("1"),
            )
        )
    session.commit()

    report = service.evaluate("binance", "BTC/USDT")
    assert report.should_halt
    assert report.reason == "repeated_reject_auto_halt_threshold_exceeded"


def test_max_daily_loss(tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'live_risk_test.db'}",
        LIVE_TRADING_ENABLED=True,
        PAPER_TRADING=False,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_MAX_DAILY_LOSS_NOTIONAL=Decimal("50"),
    )
    service, session = build_service(tmp_path, settings)

    # Simulate a buy and a sell trade
    order_buy = OrderRecord(
        exchange="binance",
        symbol="BTC/USDT",
        side="buy",
        order_type="market",
        status="filled",
        mode="live",
        quantity=Decimal("1"),
    )
    session.add(order_buy)
    session.flush()

    trade_buy = TradeRecord(
        order_id=order_buy.id,
        exchange="binance",
        symbol="BTC/USDT",
        side="buy",
        quantity=Decimal("1"),
        price=Decimal("100"),
    )
    session.add(trade_buy)
    session.flush()

    # Sell at a loss of 60
    order_sell = OrderRecord(
        exchange="binance",
        symbol="BTC/USDT",
        side="sell",
        order_type="market",
        status="filled",
        mode="live",
        quantity=Decimal("1"),
    )
    session.add(order_sell)
    session.flush()

    trade_sell = TradeRecord(
        order_id=order_sell.id,
        exchange="binance",
        symbol="BTC/USDT",
        side="sell",
        quantity=Decimal("1"),
        price=Decimal("40"),
    )
    session.add(trade_sell)
    session.commit()

    report = service.evaluate("binance", "BTC/USDT")
    assert report.should_halt
    assert report.reason == "max_daily_loss_notional_exceeded"


def test_consecutive_losses(tmp_path: Path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'live_risk_test.db'}",
        LIVE_TRADING_ENABLED=True,
        PAPER_TRADING=False,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        LIVE_CONSECUTIVE_LOSS_AUTO_HALT_THRESHOLD=2,
    )
    service, session = build_service(tmp_path, settings)

    # Simulate two losing trades
    for _ in range(2):
        order_buy = OrderRecord(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            order_type="market",
            status="filled",
            mode="live",
            quantity=Decimal("1"),
        )
        session.add(order_buy)
        session.flush()
        trade_buy = TradeRecord(
            order_id=order_buy.id,
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("1"),
            price=Decimal("100"),
        )
        session.add(trade_buy)
        session.flush()

        order_sell = OrderRecord(
            exchange="binance",
            symbol="BTC/USDT",
            side="sell",
            order_type="market",
            status="filled",
            mode="live",
            quantity=Decimal("1"),
        )
        session.add(order_sell)
        session.flush()
        trade_sell = TradeRecord(
            order_id=order_sell.id,
            exchange="binance",
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("1"),
            price=Decimal("50"),  # 50 loss
        )
        session.add(trade_sell)

    session.commit()

    report = service.evaluate("binance", "BTC/USDT")
    assert report.should_halt
    assert report.reason == "consecutive_loss_auto_halt_threshold_exceeded"
