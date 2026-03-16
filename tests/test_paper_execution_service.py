from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.application.services.paper_execution_service import (
    PaperExecutionRequest,
    PaperExecutionService,
)
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.trade import TradeRecord
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def build_service(tmp_path: Path) -> tuple[PaperExecutionService, object]:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'paper_execution.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    return PaperExecutionService(session), session


def test_executes_buy_and_creates_filled_order_trade_and_position(tmp_path: Path) -> None:
    service, _session = build_service(tmp_path)

    result = service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            client_order_id="paper-binance-btc-usdt-buy-1",
            submitted_reason="entry signal",
        )
    )

    assert result.order.status == "filled"
    assert result.order.client_order_id == "paper-binance-btc-usdt-buy-1"
    assert result.trade.order_id == result.order.id
    assert result.position.quantity == Decimal("0.00200000")
    assert result.position.average_entry_price == Decimal("50000")
    assert result.realized_pnl == Decimal("0")


def test_executes_sell_and_realizes_pnl(tmp_path: Path) -> None:
    service, _session = build_service(tmp_path)
    service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
        )
    )

    result = service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("0.001"),
            price=Decimal("52000"),
            submitted_reason="exit signal",
        )
    )

    assert result.order.status == "filled"
    assert result.position.quantity == Decimal("0.00100000")
    assert result.position.realized_pnl == Decimal("2.00000000000")
    assert result.realized_pnl == Decimal("2.000")


def test_rejects_sell_without_existing_position(tmp_path: Path) -> None:
    service, session = build_service(tmp_path)

    with pytest.raises(ValueError, match="cannot execute sell without an existing position"):
        service.execute(
            PaperExecutionRequest(
                exchange="binance",
                symbol="BTC/USDT",
                side="sell",
                quantity=Decimal("0.001"),
                price=Decimal("52000"),
            )
        )

    orders_count = session.scalar(select(func.count()).select_from(OrderRecord))
    trades_count = session.scalar(select(func.count()).select_from(TradeRecord))

    assert orders_count == 0
    assert trades_count == 0


def test_rejects_oversell_without_persisting_order_or_trade(tmp_path: Path) -> None:
    service, session = build_service(tmp_path)
    service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
        )
    )

    with pytest.raises(ValueError, match="cannot execute sell larger than existing position"):
        service.execute(
            PaperExecutionRequest(
                exchange="binance",
                symbol="BTC/USDT",
                side="sell",
                quantity=Decimal("0.003"),
                price=Decimal("52000"),
            )
        )

    orders_count = session.scalar(select(func.count()).select_from(OrderRecord))
    trades_count = session.scalar(select(func.count()).select_from(TradeRecord))

    assert orders_count == 1
    assert trades_count == 1
