from decimal import Decimal
from pathlib import Path

import pytest

from app.application.services.paper_execution_service import (
    PaperExecutionRequest,
    PaperExecutionService,
)
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def build_service(tmp_path: Path) -> PaperExecutionService:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'paper_execution.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()
    return PaperExecutionService(session)


def test_executes_buy_and_creates_filled_order_trade_and_position(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    result = service.execute(
        PaperExecutionRequest(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
            submitted_reason="entry signal",
        )
    )

    assert result.order.status == "filled"
    assert result.trade.order_id == result.order.id
    assert result.position.quantity == Decimal("0.00200000")
    assert result.position.average_entry_price == Decimal("50000")
    assert result.realized_pnl == Decimal("0")


def test_executes_sell_and_realizes_pnl(tmp_path: Path) -> None:
    service = build_service(tmp_path)
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
    service = build_service(tmp_path)

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
