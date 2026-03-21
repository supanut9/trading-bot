from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.position import PositionRecord
from app.infrastructure.database.models.trade import TradeRecord
from app.infrastructure.database.repositories.order_repository import OrderRepository
from app.infrastructure.database.repositories.position_repository import PositionRepository
from app.infrastructure.database.repositories.trade_repository import TradeRepository

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PaperExecutionRequest:
    exchange: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    order_type: str = "market"
    mode: str = "paper"
    trading_mode: str = "SPOT"
    client_order_id: str | None = None
    submitted_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PaperExecutionResult:
    order: OrderRecord
    trade: TradeRecord
    position: PositionRecord
    realized_pnl: Decimal


class PaperExecutionService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._orders = OrderRepository(session)
        self._trades = TradeRepository(session)
        self._positions = PositionRepository(session)

    def execute(self, request: PaperExecutionRequest) -> PaperExecutionResult:
        if request.mode != "paper":
            raise ValueError("paper execution service only supports paper mode")
        if request.quantity <= Decimal("0"):
            raise ValueError("quantity must be positive")
        if request.price <= Decimal("0"):
            raise ValueError("price must be positive")
        if request.side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")

        logger.info(
            "paper_execution_requested exchange=%s symbol=%s side=%s quantity=%s price=%s",
            request.exchange,
            request.symbol,
            request.side,
            request.quantity,
            request.price,
        )

        current_position = self._positions.get(
            exchange=request.exchange,
            symbol=request.symbol,
            trading_mode=request.trading_mode,
            mode=request.mode,
        )
        self._validate_request_against_position(
            current_position=current_position,
            request=request,
        )

        order = self._orders.create(
            exchange=request.exchange,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            status="filled",
            trading_mode=request.trading_mode,
            mode=request.mode,
            quantity=request.quantity,
            price=request.price,
            average_fill_price=request.price,
            client_order_id=request.client_order_id,
            submitted_reason=request.submitted_reason,
        )

        position, realized_pnl = self._apply_position_update(
            current_position=current_position,
            request=request,
        )

        trade = self._trades.create(
            exchange=request.exchange,
            symbol=request.symbol,
            trading_mode=request.trading_mode,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            order_id=order.id,
            realized_pnl=realized_pnl if request.side == "sell" else None,
        )

        self._session.commit()

        logger.info(
            "paper_execution_completed exchange=%s symbol=%s side=%s quantity=%s realized_pnl=%s",
            request.exchange,
            request.symbol,
            request.side,
            request.quantity,
            realized_pnl,
        )

        return PaperExecutionResult(
            order=order,
            trade=trade,
            position=position,
            realized_pnl=realized_pnl,
        )

    def _apply_position_update(
        self,
        *,
        current_position: PositionRecord | None,
        request: PaperExecutionRequest,
    ) -> tuple[PositionRecord, Decimal]:
        existing_quantity = current_position.quantity if current_position else Decimal("0")
        existing_average = None
        if current_position and current_position.average_entry_price:
            existing_average = current_position.average_entry_price
        existing_realized = current_position.realized_pnl if current_position else Decimal("0")

        if request.side == "buy":
            total_cost = (existing_quantity * (existing_average or Decimal("0"))) + (
                request.quantity * request.price
            )
            new_quantity = existing_quantity + request.quantity
            new_average = total_cost / new_quantity
            position = self._positions.upsert(
                exchange=request.exchange,
                symbol=request.symbol,
                trading_mode=request.trading_mode,
                mode=request.mode,
                side="long",
                quantity=new_quantity,
                average_entry_price=new_average,
                realized_pnl=existing_realized,
                unrealized_pnl=Decimal("0"),
            )
            return position, Decimal("0")

        closed_quantity = request.quantity
        if existing_average is None:
            raise ValueError("cannot calculate realized pnl without an average entry price")
        realized_pnl = (request.price - existing_average) * closed_quantity

        new_quantity = existing_quantity - closed_quantity
        new_average = existing_average if new_quantity > Decimal("0") else None

        position = self._positions.upsert(
            exchange=request.exchange,
            symbol=request.symbol,
            trading_mode=request.trading_mode,
            mode=request.mode,
            side="long",
            quantity=new_quantity,
            average_entry_price=new_average,
            realized_pnl=existing_realized + realized_pnl,
            unrealized_pnl=Decimal("0"),
        )
        return position, realized_pnl

    def _validate_request_against_position(
        self,
        *,
        current_position: PositionRecord | None,
        request: PaperExecutionRequest,
    ) -> None:
        if request.side != "sell":
            return

        if current_position is None or current_position.quantity <= Decimal("0"):
            raise ValueError("cannot execute sell without an existing position")

        if current_position.average_entry_price is None:
            raise ValueError("existing position must have an average entry price")

        if request.quantity > current_position.quantity:
            raise ValueError("cannot execute sell larger than existing position")
