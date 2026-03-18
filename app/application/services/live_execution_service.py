from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.application.services.live_order_state import (
    resolve_submission_state,
    transition_live_order,
)
from app.application.services.paper_execution_service import PaperExecutionRequest
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.position import PositionRecord
from app.infrastructure.database.repositories.order_repository import OrderRepository
from app.infrastructure.database.repositories.position_repository import PositionRepository
from app.infrastructure.exchanges.base import (
    ExchangeOrderRequest,
    ExchangeOrderSubmission,
    LiveOrderExchangeClient,
)


class DuplicateLiveOrderError(ValueError):
    """Raised when a matching unresolved live order already exists."""


@dataclass(frozen=True, slots=True)
class LiveExecutionResult:
    order: OrderRecord
    trade: None = None
    position: PositionRecord | None = None
    realized_pnl: Decimal = Decimal("0")
    submission: ExchangeOrderSubmission | None = None


class LiveExecutionService:
    def __init__(self, session: Session, *, client: LiveOrderExchangeClient) -> None:
        self._session = session
        self._client = client
        self._orders = OrderRepository(session)
        self._positions = PositionRepository(session)

    def execute(self, request: PaperExecutionRequest) -> LiveExecutionResult:
        if request.mode != "live":
            raise ValueError("live execution service only supports live mode")
        if request.quantity <= Decimal("0"):
            raise ValueError("quantity must be positive")
        if request.price <= Decimal("0"):
            raise ValueError("price must be positive")
        if request.side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")

        current_position = self._positions.get(
            exchange=request.exchange,
            symbol=request.symbol,
            mode=request.mode,
        )
        self._validate_request_against_position(
            current_position=current_position,
            request=request,
        )
        self._validate_no_duplicate_live_order(request)

        order = self._orders.create(
            exchange=request.exchange,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            status="submitting",
            mode=request.mode,
            quantity=request.quantity,
            price=request.price,
            client_order_id=request.client_order_id,
            submitted_reason=request.submitted_reason,
        )
        submission = self._client.submit_order(
            ExchangeOrderRequest(
                symbol=request.symbol,
                side=request.side,
                quantity=request.quantity,
                order_type=request.order_type,
                validate_only=False,
                client_order_id=request.client_order_id,
            )
        )
        resolution = resolve_submission_state(submission.status)
        transition_live_order(order, next_status=resolution.status)
        order.exchange_order_id = submission.exchange_order_id
        self._session.commit()

        return LiveExecutionResult(
            order=order,
            position=current_position,
            submission=submission,
        )

    def _validate_no_duplicate_live_order(self, request: PaperExecutionRequest) -> None:
        if not self._orders.has_active_live_order(
            exchange=request.exchange,
            symbol=request.symbol,
            side=request.side,
        ):
            return
        raise DuplicateLiveOrderError("active live order already exists for the same market side")

    @staticmethod
    def _validate_request_against_position(
        *,
        current_position: PositionRecord | None,
        request: PaperExecutionRequest,
    ) -> None:
        if request.side != "sell":
            return
        if current_position is None or current_position.quantity <= Decimal("0"):
            raise ValueError("cannot execute sell without an existing position")
        if request.quantity > current_position.quantity:
            raise ValueError("cannot execute sell larger than existing position")
