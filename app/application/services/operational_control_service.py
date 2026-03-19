from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.application.services.audit_service import AuditService
from app.application.services.backtest_service import BacktestResult, BacktestService
from app.application.services.live_fill_reconciliation_service import (
    LiveFillReconciliationService,
)
from app.application.services.live_operator_control_service import LiveOperatorControlService
from app.application.services.live_order_state import (
    CANCELABLE_LIVE_ORDER_STATUSES,
    resolve_cancellation_state,
    transition_live_order,
)
from app.application.services.market_data_service import MarketDataService
from app.application.services.market_data_sync_service import MarketDataSyncService
from app.application.services.notification_service import (
    NotificationService,
    build_notification_service,
)
from app.application.services.operator_runtime_config_service import (
    OPERATOR_STRATEGY_EMA_CROSSOVER,
    OperatorRuntimeConfig,
    OperatorRuntimeConfigService,
)
from app.application.services.worker_orchestration_service import WorkerOrchestrationService
from app.config import Settings
from app.domain.risk import RiskLimits, RiskService
from app.domain.strategies.base import Candle
from app.domain.strategies.ema_crossover import EmaCrossoverStrategy
from app.infrastructure.database.models.candle import CandleRecord
from app.infrastructure.database.repositories.order_repository import OrderRepository
from app.infrastructure.database.session import create_session_factory
from app.infrastructure.exchanges.factory import (
    build_live_order_exchange_client,
    build_market_data_exchange_client,
)

BACKTEST_STRATEGY_EMA_CROSSOVER = OPERATOR_STRATEGY_EMA_CROSSOVER


@dataclass(frozen=True, slots=True)
class BacktestRunOptions:
    strategy_name: str = BACKTEST_STRATEGY_EMA_CROSSOVER
    exchange: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    fast_period: int | None = None
    slow_period: int | None = None
    starting_equity: Decimal | None = None


@dataclass(frozen=True, slots=True)
class BacktestExecutionResult:
    action: str
    price: Decimal
    quantity: Decimal
    realized_pnl: Decimal
    reason: str


@dataclass(frozen=True, slots=True)
class WorkerControlResult:
    status: str
    detail: str
    signal_action: str | None = None
    client_order_id: str | None = None
    order_id: int | None = None
    trade_id: int | None = None
    position_quantity: Decimal | None = None
    notified: bool = False


@dataclass(frozen=True, slots=True)
class BacktestControlResult:
    status: str
    detail: str
    notified: bool
    strategy_name: str
    exchange: str
    symbol: str
    timeframe: str
    fast_period: int
    slow_period: int
    starting_equity_input: Decimal
    candle_count: int
    required_candles: int
    starting_equity: Decimal | None = None
    ending_equity: Decimal | None = None
    realized_pnl: Decimal | None = None
    total_return_pct: Decimal | None = None
    max_drawdown_pct: Decimal | None = None
    total_trades: int | None = None
    winning_trades: int | None = None
    losing_trades: int | None = None
    executions: tuple[BacktestExecutionResult, ...] = ()


@dataclass(frozen=True, slots=True)
class MarketSyncControlResult:
    status: str
    detail: str
    symbol: str
    timeframe: str
    limit: int
    backfill: bool
    fetched_count: int
    stored_count: int
    latest_open_time: datetime | None = None
    notified: bool = False


@dataclass(frozen=True, slots=True)
class LiveReconcileControlResult:
    status: str
    detail: str
    reconciled_count: int
    filled_count: int
    review_required_count: int
    notified: bool = False


@dataclass(frozen=True, slots=True)
class LiveCancelControlResult:
    status: str
    detail: str
    order_id: int | None
    client_order_id: str | None
    exchange_order_id: str | None
    order_status: str | None
    notified: bool = False


@dataclass(frozen=True, slots=True)
class LiveHaltControlResult:
    status: str
    detail: str
    live_trading_halted: bool
    changed: bool
    notified: bool = False


@dataclass(frozen=True, slots=True)
class OperatorConfigControlResult:
    status: str
    detail: str
    strategy_name: str
    exchange: str
    symbol: str
    timeframe: str
    fast_period: int
    slow_period: int
    source: str
    changed: bool = False
    notified: bool = False


class OperationalControlService:
    _decimal_precision = Decimal("0.00000001")

    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: sessionmaker[Session] | None = None,
        notifications: NotificationService | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory or create_session_factory(settings)
        self._notifications = notifications or build_notification_service(
            settings,
            session_factory=self._session_factory,
        )
        self._audit = audit or AuditService(session_factory=self._session_factory)

    def run_worker_cycle(
        self,
        *,
        source: str = "internal",
        audit: bool = True,
    ) -> WorkerControlResult:
        with self._session_factory() as session:
            operator_config = OperatorRuntimeConfigService(
                session,
                self._settings,
            ).get_effective_config()
            result = WorkerOrchestrationService(
                session,
                self._settings,
                operator_config=operator_config,
            ).run_cycle()

        notified = self._notifications.notify_worker_cycle(self._settings, result)
        control_result = WorkerControlResult(
            status=result.status,
            detail=result.detail,
            signal_action=result.signal_action,
            client_order_id=result.client_order_id,
            order_id=result.order_id,
            trade_id=result.trade_id,
            position_quantity=result.position_quantity,
            notified=notified,
        )
        if audit:
            self._audit.record_control_result(
                control_type="worker_cycle",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "signal_action": control_result.signal_action,
                    "client_order_id": control_result.client_order_id,
                    "order_id": control_result.order_id,
                    "trade_id": control_result.trade_id,
                    "position_quantity": control_result.position_quantity,
                    "notified": control_result.notified,
                },
            )
        return control_result

    def run_market_sync(
        self,
        *,
        limit: int | None = None,
        backfill: bool = False,
        source: str = "internal",
        audit: bool = True,
    ) -> MarketSyncControlResult:
        resolved_limit = limit if limit is not None else self._settings.market_data_sync_limit
        with self._session_factory() as session:
            operator_config = OperatorRuntimeConfigService(
                session,
                self._settings,
            ).get_effective_config()
            try:
                result = MarketDataSyncService(
                    session,
                    build_market_data_exchange_client(self._settings),
                ).sync_recent_closed_candles(
                    exchange=self._settings.exchange_name,
                    symbol=operator_config.symbol,
                    timeframe=operator_config.timeframe,
                    limit=resolved_limit,
                    backfill=backfill,
                )
            except Exception:
                failed = MarketSyncControlResult(
                    status="failed",
                    detail="market data sync failed",
                    symbol=operator_config.symbol,
                    timeframe=operator_config.timeframe,
                    limit=resolved_limit,
                    backfill=backfill,
                    fetched_count=0,
                    stored_count=0,
                )
                notified = self._notifications.notify_market_sync(self._settings, failed)
                control_result = MarketSyncControlResult(
                    status=failed.status,
                    detail=failed.detail,
                    symbol=failed.symbol,
                    timeframe=failed.timeframe,
                    fetched_count=failed.fetched_count,
                    stored_count=failed.stored_count,
                    latest_open_time=failed.latest_open_time,
                    notified=notified,
                )
                if audit:
                    self._audit.record_control_result(
                        control_type="market_sync",
                        source=source,
                        status=control_result.status,
                        detail=control_result.detail,
                        settings=self._settings,
                        payload={
                            "symbol": control_result.symbol,
                            "timeframe": control_result.timeframe,
                            "limit": control_result.limit,
                            "backfill": control_result.backfill,
                            "fetched_count": control_result.fetched_count,
                            "stored_count": control_result.stored_count,
                            "latest_open_time": control_result.latest_open_time,
                            "notified": control_result.notified,
                        },
                    )
                return control_result

        detail = "market data sync completed"
        if backfill:
            detail = "market data backfill completed"
        if result.fetched_count == 0:
            detail = "no candles fetched"
        elif result.stored_count == 0:
            detail = "no new candles stored" if not backfill else "no candles stored"

        completed = MarketSyncControlResult(
            status="completed",
            detail=detail,
            symbol=operator_config.symbol,
            timeframe=operator_config.timeframe,
            limit=resolved_limit,
            backfill=backfill,
            fetched_count=result.fetched_count,
            stored_count=result.stored_count,
            latest_open_time=result.latest_open_time,
        )
        notified = self._notifications.notify_market_sync(self._settings, completed)
        control_result = MarketSyncControlResult(
            status=completed.status,
            detail=completed.detail,
            symbol=completed.symbol,
            timeframe=completed.timeframe,
            limit=completed.limit,
            backfill=completed.backfill,
            fetched_count=completed.fetched_count,
            stored_count=completed.stored_count,
            latest_open_time=completed.latest_open_time,
            notified=notified,
        )
        if audit:
            self._audit.record_control_result(
                control_type="market_sync",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "symbol": control_result.symbol,
                    "timeframe": control_result.timeframe,
                    "limit": control_result.limit,
                    "backfill": control_result.backfill,
                    "fetched_count": control_result.fetched_count,
                    "stored_count": control_result.stored_count,
                    "latest_open_time": control_result.latest_open_time,
                    "notified": control_result.notified,
                },
            )
        return control_result

    def run_backtest(
        self,
        *,
        options: BacktestRunOptions | None = None,
        notify: bool = True,
        source: str = "internal",
        audit: bool = True,
    ) -> BacktestControlResult:
        defaults = self._get_effective_operator_config()
        try:
            resolved = self._resolve_backtest_options(options, defaults=defaults)
        except ValueError as exc:
            preview = self._preview_backtest_options(options, defaults=defaults)
            control_result = BacktestControlResult(
                status="failed",
                detail=str(exc),
                notified=False,
                strategy_name=preview.strategy_name,
                exchange=preview.exchange,
                symbol=preview.symbol,
                timeframe=preview.timeframe,
                fast_period=preview.fast_period,
                slow_period=preview.slow_period,
                starting_equity_input=self._quantize_decimal(preview.starting_equity)
                or Decimal("0"),
                candle_count=0,
                required_candles=max(preview.slow_period + 1, 0),
            )
            if audit:
                self._audit.record_control_result(
                    control_type="backtest",
                    source=source,
                    status=control_result.status,
                    detail=control_result.detail,
                    settings=self._settings,
                    payload={
                        "strategy_name": control_result.strategy_name,
                        "exchange": control_result.exchange,
                        "symbol": control_result.symbol,
                        "timeframe": control_result.timeframe,
                        "fast_period": control_result.fast_period,
                        "slow_period": control_result.slow_period,
                        "starting_equity_input": control_result.starting_equity_input,
                        "candle_count": control_result.candle_count,
                        "required_candles": control_result.required_candles,
                        "notified": control_result.notified,
                    },
                )
            return control_result
        with self._session_factory() as session:
            records = MarketDataService(session).list_historical_candles(
                exchange=resolved.exchange,
                symbol=resolved.symbol,
                timeframe=resolved.timeframe,
            )
            candle_count = len(records)
            required_candles = resolved.slow_period + 1

            if not records:
                backtest_result = None
                status = "skipped"
                detail = "no_candles"
            elif candle_count < required_candles:
                backtest_result = None
                status = "skipped"
                detail = "not_enough_candles"
            else:
                backtest_result = self._run_backtest_from_records(records, options=resolved)
                status = "completed"
                detail = "backtest completed"

        if backtest_result is None:
            notified = False
            if notify:
                notified = self._notifications.notify_backtest_skipped(
                    self._settings,
                    reason=detail,
                    count=candle_count,
                    required=required_candles,
                )
            control_result = BacktestControlResult(
                status=status,
                detail=detail,
                notified=notified,
                strategy_name=resolved.strategy_name,
                exchange=resolved.exchange,
                symbol=resolved.symbol,
                timeframe=resolved.timeframe,
                fast_period=resolved.fast_period,
                slow_period=resolved.slow_period,
                starting_equity_input=self._quantize_decimal(resolved.starting_equity)
                or Decimal("0"),
                candle_count=candle_count,
                required_candles=required_candles,
            )
            if audit:
                self._audit.record_control_result(
                    control_type="backtest",
                    source=source,
                    status=control_result.status,
                    detail=control_result.detail,
                    settings=self._settings,
                    payload={
                        "strategy_name": control_result.strategy_name,
                        "exchange": control_result.exchange,
                        "symbol": control_result.symbol,
                        "timeframe": control_result.timeframe,
                        "fast_period": control_result.fast_period,
                        "slow_period": control_result.slow_period,
                        "starting_equity_input": control_result.starting_equity_input,
                        "candle_count": control_result.candle_count,
                        "required_candles": control_result.required_candles,
                        "notified": control_result.notified,
                    },
                )
            return control_result

        notified = False
        if notify:
            notified = self._notifications.notify_backtest_completed(
                self._settings,
                backtest_result,
            )
        control_result = BacktestControlResult(
            status=status,
            detail=detail,
            notified=notified,
            strategy_name=resolved.strategy_name,
            exchange=resolved.exchange,
            symbol=resolved.symbol,
            timeframe=resolved.timeframe,
            fast_period=resolved.fast_period,
            slow_period=resolved.slow_period,
            starting_equity_input=self._quantize_decimal(resolved.starting_equity) or Decimal("0"),
            candle_count=candle_count,
            required_candles=required_candles,
            starting_equity=self._quantize_decimal(backtest_result.starting_equity),
            ending_equity=self._quantize_decimal(backtest_result.ending_equity),
            realized_pnl=self._quantize_decimal(backtest_result.realized_pnl),
            total_return_pct=self._quantize_decimal(backtest_result.total_return_pct),
            max_drawdown_pct=self._quantize_decimal(backtest_result.max_drawdown_pct),
            total_trades=backtest_result.total_trades,
            winning_trades=backtest_result.winning_trades,
            losing_trades=backtest_result.losing_trades,
            executions=tuple(
                BacktestExecutionResult(
                    action=execution.action,
                    price=self._quantize_decimal(execution.price) or Decimal("0"),
                    quantity=self._quantize_decimal(execution.quantity) or Decimal("0"),
                    realized_pnl=self._quantize_decimal(execution.realized_pnl) or Decimal("0"),
                    reason=execution.reason,
                )
                for execution in backtest_result.executions
            ),
        )
        if audit:
            self._audit.record_control_result(
                control_type="backtest",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "strategy_name": control_result.strategy_name,
                    "exchange": control_result.exchange,
                    "symbol": control_result.symbol,
                    "timeframe": control_result.timeframe,
                    "fast_period": control_result.fast_period,
                    "slow_period": control_result.slow_period,
                    "starting_equity_input": control_result.starting_equity_input,
                    "candle_count": control_result.candle_count,
                    "required_candles": control_result.required_candles,
                    "starting_equity": control_result.starting_equity,
                    "ending_equity": control_result.ending_equity,
                    "realized_pnl": control_result.realized_pnl,
                    "total_return_pct": control_result.total_return_pct,
                    "max_drawdown_pct": control_result.max_drawdown_pct,
                    "total_trades": control_result.total_trades,
                    "winning_trades": control_result.winning_trades,
                    "losing_trades": control_result.losing_trades,
                    "execution_count": len(control_result.executions),
                    "notified": control_result.notified,
                },
            )
        return control_result

    def run_live_reconcile(
        self,
        *,
        source: str = "internal",
        audit: bool = True,
    ) -> LiveReconcileControlResult:
        try:
            with self._session_factory() as session:
                results = LiveFillReconciliationService(
                    session,
                    client=build_live_order_exchange_client(self._settings),
                ).reconcile_recent_live_orders()
        except Exception:
            control_result = LiveReconcileControlResult(
                status="failed",
                detail="live reconciliation failed",
                reconciled_count=0,
                filled_count=0,
                review_required_count=0,
                notified=False,
            )
            if audit:
                self._audit.record_control_result(
                    control_type="live_reconcile",
                    source=source,
                    status=control_result.status,
                    detail=control_result.detail,
                    settings=self._settings,
                    payload={
                        "reconciled_count": control_result.reconciled_count,
                        "filled_count": control_result.filled_count,
                        "review_required_count": control_result.review_required_count,
                    },
                )
            return control_result

        reconciled_count = len(results)
        filled_count = sum(1 for result in results if result.trade_created)
        review_required_count = sum(1 for result in results if result.requires_operator_review)
        detail = "no live orders to reconcile"
        if reconciled_count > 0:
            detail = "live orders reconciled"
        if review_required_count > 0:
            detail = "live orders require operator review"
        control_result = LiveReconcileControlResult(
            status="completed",
            detail=detail,
            reconciled_count=reconciled_count,
            filled_count=filled_count,
            review_required_count=review_required_count,
            notified=False,
        )
        if audit:
            self._audit.record_control_result(
                control_type="live_reconcile",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "reconciled_count": control_result.reconciled_count,
                    "filled_count": control_result.filled_count,
                    "review_required_count": control_result.review_required_count,
                },
            )
        return control_result

    def run_live_halt(
        self,
        *,
        halted: bool,
        source: str = "internal",
        audit: bool = True,
    ) -> LiveHaltControlResult:
        with self._session_factory() as session:
            control_update = LiveOperatorControlService(
                session,
                self._settings,
            ).set_live_trading_halted(
                halted=halted,
                updated_by=source,
            )
            session.commit()

        detail = "live entry halted" if halted else "live entry resumed"
        if not control_update.changed:
            detail = "live entry halt state unchanged"

        control_result = LiveHaltControlResult(
            status="completed",
            detail=detail,
            live_trading_halted=control_update.current_halted,
            changed=control_update.changed,
            notified=False,
        )
        if audit:
            self._audit.record_control_result(
                control_type="live_halt",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "previous_halted": control_update.previous_halted,
                    "live_trading_halted": control_result.live_trading_halted,
                    "changed": control_result.changed,
                    "updated_by": control_update.updated_by,
                },
            )
        return control_result

    def get_operator_config(self) -> OperatorConfigControlResult:
        config = self._get_effective_operator_config()
        return OperatorConfigControlResult(
            status="completed",
            detail="operator runtime config loaded",
            strategy_name=config.strategy_name,
            exchange=config.exchange,
            symbol=config.symbol,
            timeframe=config.timeframe,
            fast_period=config.fast_period,
            slow_period=config.slow_period,
            source=config.source,
        )

    def run_update_operator_config(
        self,
        *,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        fast_period: int,
        slow_period: int,
        source: str = "internal",
        audit: bool = True,
    ) -> OperatorConfigControlResult:
        try:
            with self._session_factory() as session:
                update = OperatorRuntimeConfigService(
                    session,
                    self._settings,
                ).set_config(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    timeframe=timeframe,
                    fast_period=fast_period,
                    slow_period=slow_period,
                    updated_by=source,
                )
                session.commit()
        except ValueError as exc:
            current = self.get_operator_config()
            return OperatorConfigControlResult(
                status="failed",
                detail=str(exc),
                strategy_name=strategy_name.strip().lower() or current.strategy_name,
                exchange=self._settings.exchange_name,
                symbol=symbol.strip() or current.symbol,
                timeframe=timeframe.strip() or current.timeframe,
                fast_period=fast_period,
                slow_period=slow_period,
                source=current.source,
            )

        control_result = OperatorConfigControlResult(
            status="completed",
            detail=(
                "operator runtime config updated"
                if update.changed
                else "operator runtime config unchanged"
            ),
            strategy_name=update.current.strategy_name,
            exchange=update.current.exchange,
            symbol=update.current.symbol,
            timeframe=update.current.timeframe,
            fast_period=update.current.fast_period,
            slow_period=update.current.slow_period,
            source=update.current.source,
            changed=update.changed,
        )
        if audit:
            self._audit.record_control_result(
                control_type="operator_config",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "strategy_name": control_result.strategy_name,
                    "exchange": control_result.exchange,
                    "symbol": control_result.symbol,
                    "timeframe": control_result.timeframe,
                    "fast_period": control_result.fast_period,
                    "slow_period": control_result.slow_period,
                    "config_source": control_result.source,
                    "changed": control_result.changed,
                },
            )
        return control_result

    def run_live_cancel(
        self,
        *,
        order_id: int | None = None,
        client_order_id: str | None = None,
        exchange_order_id: str | None = None,
        source: str = "internal",
        audit: bool = True,
    ) -> LiveCancelControlResult:
        provided_identifiers = [
            value is not None for value in (order_id, client_order_id, exchange_order_id)
        ]
        if sum(provided_identifiers) != 1:
            control_result = LiveCancelControlResult(
                status="failed",
                detail="exactly one live order identifier is required",
                order_id=order_id,
                client_order_id=client_order_id,
                exchange_order_id=exchange_order_id,
                order_status=None,
            )
            if audit:
                self._audit.record_control_result(
                    control_type="live_cancel",
                    source=source,
                    status=control_result.status,
                    detail=control_result.detail,
                    settings=self._settings,
                    payload={
                        "order_id": control_result.order_id,
                        "client_order_id": control_result.client_order_id,
                        "exchange_order_id": control_result.exchange_order_id,
                        "order_status": control_result.order_status,
                    },
                )
            return control_result

        with self._session_factory() as session:
            orders = OrderRepository(session)
            if order_id is not None:
                order = orders.get_by_id(order_id)
            elif client_order_id is not None:
                order = orders.get_by_client_order_id(client_order_id)
            else:
                order = orders.get_by_exchange_order_id(str(exchange_order_id))

            if order is None or order.mode != "live":
                control_result = LiveCancelControlResult(
                    status="failed",
                    detail="live order not found",
                    order_id=order_id,
                    client_order_id=client_order_id,
                    exchange_order_id=exchange_order_id,
                    order_status=None,
                )
            elif order.status not in CANCELABLE_LIVE_ORDER_STATUSES:
                control_result = LiveCancelControlResult(
                    status="skipped",
                    detail="live order is not cancelable in its current status",
                    order_id=order.id,
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    order_status=order.status,
                )
            else:
                try:
                    cancellation = build_live_order_exchange_client(self._settings).cancel_order(
                        symbol=order.symbol,
                        client_order_id=order.client_order_id,
                        exchange_order_id=order.exchange_order_id,
                    )
                    resolution = resolve_cancellation_state(cancellation.status)
                    transition_live_order(order, next_status=resolution.status)
                    if cancellation.exchange_order_id:
                        order.exchange_order_id = cancellation.exchange_order_id
                    session.commit()
                    control_result = LiveCancelControlResult(
                        status="completed",
                        detail=resolution.detail,
                        order_id=order.id,
                        client_order_id=order.client_order_id,
                        exchange_order_id=order.exchange_order_id,
                        order_status=order.status,
                    )
                except Exception:
                    control_result = LiveCancelControlResult(
                        status="failed",
                        detail="live order cancel failed",
                        order_id=order.id,
                        client_order_id=order.client_order_id,
                        exchange_order_id=order.exchange_order_id,
                        order_status=order.status,
                    )

        if audit:
            self._audit.record_control_result(
                control_type="live_cancel",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "order_id": control_result.order_id,
                    "client_order_id": control_result.client_order_id,
                    "exchange_order_id": control_result.exchange_order_id,
                    "order_status": control_result.order_status,
                },
            )
        return control_result

    def _run_backtest_from_records(
        self,
        records: Sequence[CandleRecord],
        *,
        options: BacktestRunOptions,
    ) -> BacktestResult:
        return BacktestService(
            strategy=self._build_backtest_strategy(options),
            risk_service=self._build_risk_service(),
            starting_equity=options.starting_equity,
        ).run(
            [
                Candle(
                    open_time=record.open_time,
                    close_time=record.close_time,
                    open_price=record.open_price,
                    high_price=record.high_price,
                    low_price=record.low_price,
                    close_price=record.close_price,
                    volume=record.volume,
                )
                for record in records
            ]
        )

    def _resolve_backtest_options(
        self,
        options: BacktestRunOptions | None,
        *,
        defaults: OperatorRuntimeConfig,
    ) -> BacktestRunOptions:
        active = options or BacktestRunOptions()
        strategy_name = active.strategy_name.strip().lower()
        if strategy_name != BACKTEST_STRATEGY_EMA_CROSSOVER:
            raise ValueError(f"unsupported backtest strategy: {active.strategy_name}")
        exchange = (active.exchange or defaults.exchange).strip()
        symbol = (active.symbol or defaults.symbol).strip()
        timeframe = (active.timeframe or defaults.timeframe).strip()
        fast_period = active.fast_period or defaults.fast_period
        slow_period = active.slow_period or defaults.slow_period
        starting_equity = active.starting_equity or Decimal(
            str(self._settings.paper_account_equity)
        )
        if not exchange or not symbol or not timeframe:
            raise ValueError("exchange, symbol, and timeframe are required for backtest")
        if fast_period <= 0 or slow_period <= 0:
            raise ValueError("backtest periods must be positive")
        if fast_period >= slow_period:
            raise ValueError("fast period must be smaller than slow period")
        if starting_equity <= Decimal("0"):
            raise ValueError("starting equity must be positive")
        return BacktestRunOptions(
            strategy_name=strategy_name,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            fast_period=fast_period,
            slow_period=slow_period,
            starting_equity=starting_equity,
        )

    def _preview_backtest_options(
        self,
        options: BacktestRunOptions | None,
        *,
        defaults: OperatorRuntimeConfig,
    ) -> BacktestRunOptions:
        active = options or BacktestRunOptions()
        return BacktestRunOptions(
            strategy_name=(active.strategy_name or BACKTEST_STRATEGY_EMA_CROSSOVER).strip().lower(),
            exchange=(active.exchange or defaults.exchange).strip(),
            symbol=(active.symbol or defaults.symbol).strip(),
            timeframe=(active.timeframe or defaults.timeframe).strip(),
            fast_period=int(active.fast_period or defaults.fast_period),
            slow_period=int(active.slow_period or defaults.slow_period),
            starting_equity=Decimal(
                str(active.starting_equity or self._settings.paper_account_equity)
            ),
        )

    @staticmethod
    def _build_backtest_strategy(options: BacktestRunOptions) -> EmaCrossoverStrategy:
        if options.strategy_name != BACKTEST_STRATEGY_EMA_CROSSOVER:
            raise ValueError(f"unsupported backtest strategy: {options.strategy_name}")
        return EmaCrossoverStrategy(
            fast_period=options.fast_period or 0,
            slow_period=options.slow_period or 0,
        )

    def _build_risk_service(self) -> RiskService:
        return RiskService(
            RiskLimits(
                risk_per_trade_pct=Decimal(str(self._settings.risk_per_trade_pct)),
                max_open_positions=self._settings.max_open_positions,
                max_daily_loss_pct=Decimal(str(self._settings.max_daily_loss_pct)),
                paper_trading_only=not self._settings.live_trading_enabled,
            )
        )

    def _get_effective_operator_config(self) -> OperatorRuntimeConfig:
        with self._session_factory() as session:
            return OperatorRuntimeConfigService(
                session,
                self._settings,
            ).get_effective_config()

    @classmethod
    def _quantize_decimal(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return value.quantize(cls._decimal_precision)
