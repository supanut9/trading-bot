from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.application.services.live_order_state import (
    resolve_submission_state,
    transition_live_order,
)
from app.application.services.paper_execution_service import PaperExecutionRequest
from app.config import Settings
from app.core.logger import get_logger
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.position import PositionRecord
from app.infrastructure.database.repositories.order_repository import OrderRepository
from app.infrastructure.database.repositories.position_repository import PositionRepository
from app.infrastructure.exchanges.base import (
    ExchangeAPIError,
    ExchangeOrderRequest,
    ExchangeOrderSubmission,
    LiveOrderExchangeClient,
)

logger = get_logger(__name__)


class DuplicateLiveOrderError(ValueError):
    """Raised when a matching unresolved live order already exists."""


class InsufficientExpectedProfitError(ValueError):
    """Raised when expected profit does not cover fees."""


class InsufficientFuturesMarginBalanceError(ValueError):
    """Raised when the futures wallet balance is below estimated initial margin."""


@dataclass(frozen=True, slots=True)
class LiveExecutionResult:
    order: OrderRecord
    trade: None = None
    position: PositionRecord | None = None
    realized_pnl: Decimal = Decimal("0")
    submission: ExchangeOrderSubmission | None = None


class LiveExecutionService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        client: LiveOrderExchangeClient,
    ) -> None:
        self._session = session
        self._settings = settings
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
            trading_mode=request.trading_mode,
            mode=request.mode,
        )
        self._validate_request_against_position(
            current_position=current_position,
            request=request,
        )
        self._validate_no_duplicate_live_order(request)

        order_type = request.order_type
        price = request.price
        signal_price = request.price  # Keep original signal price to record it

        if self._settings.live_order_routing_mode == "limit" and order_type == "market":
            order_type = "limit"
            offset_ratio = Decimal(self._settings.live_limit_order_offset_bps) / Decimal("10000")
            if request.side == "buy":
                # Buy below signal price to reduce fill cost
                price = signal_price * (Decimal("1") - offset_ratio)
            else:
                # Sell above signal price to reduce fill cost
                price = signal_price * (Decimal("1") + offset_ratio)

        if order_type == "limit":
            from app.application.services.symbol_rules_service import SymbolRulesService
            from app.domain.order_rules import validate_and_snap_price

            rules = SymbolRulesService(self._session).get_rules(
                exchange=request.exchange,
                symbol=request.symbol,
            )
            if rules:
                price = validate_and_snap_price(price, rules)

        # Fee-aware pre-submit check
        round_trip_fee_pct = Decimal(str(self._settings.live_fee_pct)) * Decimal("2")
        expected_profit_pct = Decimal(self._settings.live_expected_profit_bps) / Decimal("10000")

        if expected_profit_pct < round_trip_fee_pct:
            logger.warning(
                "live_order_blocked reason=insufficient_expected_profit "
                "expected_profit_pct=%.4f round_trip_fee_pct=%.4f symbol=%s",
                expected_profit_pct,
                round_trip_fee_pct,
                request.symbol,
            )
            # Use specific error so orchestration can handle it
            raise InsufficientExpectedProfitError(
                f"expected profit ({expected_profit_pct:.4f}%) does not cover "
                f"estimated round-trip fees ({round_trip_fee_pct:.4f}%)"
            )

        self._validate_futures_margin_balance(
            request=request,
            execution_price=price,
        )

        order = self._orders.create(
            exchange=request.exchange,
            symbol=request.symbol,
            side=request.side,
            order_type=order_type,
            status="submitting",
            trading_mode=request.trading_mode,
            mode=request.mode,
            strategy_name=request.strategy_name,
            quantity=request.quantity,
            price=price,
            signal_price=signal_price,
            client_order_id=request.client_order_id,
            submitted_reason=request.submitted_reason,
        )
        self._prepare_futures_execution(request)
        submission = self._client.submit_order(
            ExchangeOrderRequest(
                symbol=request.symbol,
                side=request.side,
                quantity=request.quantity,
                price=price if order_type == "limit" else None,
                order_type=order_type,
                trading_mode=request.trading_mode,
                validate_only=self._settings.live_order_validate_only,
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

    def _prepare_futures_execution(self, request: PaperExecutionRequest) -> None:
        if request.trading_mode != "FUTURES":
            return
        if self._settings.live_order_validate_only:
            return
        if not hasattr(self._client, "set_margin_mode") or not hasattr(
            self._client, "set_leverage"
        ):
            raise ValueError("futures live execution requires a futures-capable exchange client")

        try:
            margin_mode = request.margin_mode or self._settings.live_futures_margin_mode
            self._client.set_margin_mode(
                symbol=request.symbol,
                margin_mode=margin_mode,
            )
        except ExchangeAPIError as exc:
            if "code=-4046" not in str(exc) and "No need to change margin type" not in str(exc):
                raise
        leverage = request.leverage or self._settings.live_futures_leverage
        self._client.set_leverage(
            symbol=request.symbol,
            leverage=leverage,
        )

    def _validate_futures_margin_balance(
        self,
        *,
        request: PaperExecutionRequest,
        execution_price: Decimal,
    ) -> None:
        if request.trading_mode != "FUTURES":
            return
        if self._settings.live_order_validate_only:
            return

        leverage = request.leverage or self._settings.live_futures_leverage
        quote_asset = self._split_symbol_assets(request.symbol)[1]
        available_balance = Decimal("0")
        for balance in self._client.fetch_account_balances():
            if balance.asset.upper() == quote_asset:
                available_balance = balance.free
                break

        required_initial_margin = (request.quantity * execution_price) / Decimal(leverage)
        if available_balance >= required_initial_margin:
            return

        logger.warning(
            "live_order_blocked reason=insufficient_futures_margin_balance "
            "symbol=%s quote_asset=%s available_balance=%s required_initial_margin=%s leverage=%s",
            request.symbol,
            quote_asset,
            format(available_balance, "f"),
            format(required_initial_margin, "f"),
            leverage,
        )
        raise InsufficientFuturesMarginBalanceError(
            "available futures wallet balance is below estimated initial margin "
            f"for {quote_asset} ({available_balance:.4f} available vs "
            f"{required_initial_margin:.4f} required)"
        )

    def _validate_no_duplicate_live_order(self, request: PaperExecutionRequest) -> None:
        if not self._orders.has_active_live_order(
            exchange=request.exchange,
            symbol=request.symbol,
            side=request.side,
            trading_mode=request.trading_mode,
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

    @staticmethod
    def _split_symbol_assets(symbol: str) -> tuple[str, str]:
        base_asset, quote_asset = symbol.split("/", maxsplit=1)
        return base_asset.upper(), quote_asset.upper()
