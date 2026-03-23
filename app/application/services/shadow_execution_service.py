from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from app.application.services.paper_execution_service import PaperExecutionRequest
from app.core.logger import get_logger
from app.infrastructure.database.models.position import PositionRecord
from app.infrastructure.database.repositories.position_repository import PositionRepository
from app.infrastructure.database.repositories.shadow_trade_repository import ShadowTradeRepository

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ShadowExecutionResult:
    shadow_trade_id: int
    side: str
    status: str  # "open" | "closed" | "skipped"
    simulated_fill_price: Decimal
    quantity: Decimal
    net_pnl: Decimal
    order: None = field(default=None)  # satisfies worker duck-typed access with guard
    trade: None = field(default=None)
    position: PositionRecord | None = field(default=None)


class ShadowExecutionService:
    def __init__(
        self,
        session: Session,
        *,
        slippage_pct: Decimal,
        fee_pct: Decimal,
    ) -> None:
        self._session = session
        self._slippage_pct = slippage_pct
        self._fee_pct = fee_pct
        self._shadow_trades = ShadowTradeRepository(session)
        self._positions = PositionRepository(session)

    def execute(self, request: PaperExecutionRequest) -> ShadowExecutionResult:
        if request.side == "buy":
            return self._execute_entry(request)
        return self._execute_exit(request)

    def _execute_entry(self, request: PaperExecutionRequest) -> ShadowExecutionResult:
        simulated_fill_price = request.price * (Decimal("1") + self._slippage_pct)
        entry_fee = simulated_fill_price * request.quantity * self._fee_pct

        record = self._shadow_trades.create_open(
            exchange=request.exchange,
            symbol=request.symbol,
            timeframe=self._extract_timeframe(request.client_order_id),
            side="buy",
            signal_reason=request.submitted_reason,
            entry_price=request.price,
            simulated_fill_price=simulated_fill_price,
            quantity=request.quantity,
            entry_fee=entry_fee,
            client_order_id=request.client_order_id,
        )

        position = self._positions.upsert(
            exchange=request.exchange,
            symbol=request.symbol,
            mode="shadow",
            side="long",
            strategy_name=request.strategy_name,
            quantity=request.quantity,
            average_entry_price=request.price,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
        )

        self._session.commit()

        logger.info(
            "shadow_execution_entry exchange=%s symbol=%s quantity=%s fill_price=%s fee=%s",
            request.exchange,
            request.symbol,
            request.quantity,
            simulated_fill_price,
            entry_fee,
        )

        return ShadowExecutionResult(
            shadow_trade_id=record.id,
            side="buy",
            status="open",
            simulated_fill_price=simulated_fill_price,
            quantity=request.quantity,
            net_pnl=Decimal("0"),
            position=position,
        )

    def _execute_exit(self, request: PaperExecutionRequest) -> ShadowExecutionResult:
        open_trade = self._shadow_trades.get_open_trade(
            exchange=request.exchange,
            symbol=request.symbol,
        )
        if open_trade is None:
            logger.warning(
                "shadow_execution_exit_skipped reason=no_open_trade exchange=%s symbol=%s",
                request.exchange,
                request.symbol,
            )
            return ShadowExecutionResult(
                shadow_trade_id=0,
                side="sell",
                status="skipped",
                simulated_fill_price=request.price,
                quantity=request.quantity,
                net_pnl=Decimal("0"),
            )

        closed = self._shadow_trades.close_trade(
            open_trade,
            exit_price=request.price,
            slippage_pct=self._slippage_pct,
            fee_pct=self._fee_pct,
        )

        existing_position = self._positions.get(
            exchange=request.exchange,
            symbol=request.symbol,
            mode="shadow",
        )
        realized = existing_position.realized_pnl if existing_position else Decimal("0")
        position = self._positions.upsert(
            exchange=request.exchange,
            symbol=request.symbol,
            mode="shadow",
            side="long",
            strategy_name=existing_position.strategy_name
            if existing_position is not None
            else None,
            quantity=Decimal("0"),
            average_entry_price=None,
            realized_pnl=realized + (closed.net_pnl or Decimal("0")),
            unrealized_pnl=Decimal("0"),
        )

        self._session.commit()

        logger.info(
            "shadow_execution_exit exchange=%s symbol=%s fill_price=%s net_pnl=%s",
            request.exchange,
            request.symbol,
            closed.simulated_exit_fill_price,
            closed.net_pnl,
        )

        return ShadowExecutionResult(
            shadow_trade_id=closed.id,
            side="sell",
            status="closed",
            simulated_fill_price=closed.simulated_exit_fill_price or request.price,
            quantity=request.quantity,
            net_pnl=closed.net_pnl or Decimal("0"),
            position=position,
        )

    @staticmethod
    def _extract_timeframe(client_order_id: str | None) -> str:
        # client_order_id format: shadow-binance-btc-usdt-1h-buy-20260115120000
        if client_order_id:
            parts = client_order_id.split("-")
            if len(parts) >= 5:
                return parts[4]
        return "unknown"
