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


@dataclass(frozen=True, slots=True)
class MarketSyncControlResult:
    status: str
    detail: str
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
            result = WorkerOrchestrationService(session, self._settings).run_cycle()

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
        source: str = "internal",
        audit: bool = True,
    ) -> MarketSyncControlResult:
        with self._session_factory() as session:
            try:
                result = MarketDataSyncService(
                    session,
                    build_market_data_exchange_client(self._settings),
                ).sync_recent_closed_candles(
                    exchange=self._settings.exchange_name,
                    symbol=self._settings.default_symbol,
                    timeframe=self._settings.default_timeframe,
                    limit=self._settings.market_data_sync_limit,
                )
            except Exception:
                failed = MarketSyncControlResult(
                    status="failed",
                    detail="market data sync failed",
                    fetched_count=0,
                    stored_count=0,
                )
                notified = self._notifications.notify_market_sync(self._settings, failed)
                control_result = MarketSyncControlResult(
                    status=failed.status,
                    detail=failed.detail,
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
                            "fetched_count": control_result.fetched_count,
                            "stored_count": control_result.stored_count,
                            "latest_open_time": control_result.latest_open_time,
                            "notified": control_result.notified,
                        },
                    )
                return control_result

        detail = "market data sync completed"
        if result.fetched_count == 0:
            detail = "no candles fetched"
        elif result.stored_count == 0:
            detail = "no new candles stored"

        completed = MarketSyncControlResult(
            status="completed",
            detail=detail,
            fetched_count=result.fetched_count,
            stored_count=result.stored_count,
            latest_open_time=result.latest_open_time,
        )
        notified = self._notifications.notify_market_sync(self._settings, completed)
        control_result = MarketSyncControlResult(
            status=completed.status,
            detail=completed.detail,
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
        notify: bool = True,
        source: str = "internal",
        audit: bool = True,
    ) -> BacktestControlResult:
        with self._session_factory() as session:
            records = MarketDataService(session).list_historical_candles(
                exchange=self._settings.exchange_name,
                symbol=self._settings.default_symbol,
                timeframe=self._settings.default_timeframe,
            )
            candle_count = len(records)
            required_candles = self._settings.strategy_slow_period + 1

            if not records:
                backtest_result = None
                status = "skipped"
                detail = "no_candles"
            elif candle_count < required_candles:
                backtest_result = None
                status = "skipped"
                detail = "not_enough_candles"
            else:
                backtest_result = self._run_backtest_from_records(records)
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
        )
        if audit:
            self._audit.record_control_result(
                control_type="backtest",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
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

    def _run_backtest_from_records(self, records: Sequence[CandleRecord]) -> BacktestResult:
        return BacktestService(
            strategy=EmaCrossoverStrategy(
                fast_period=self._settings.strategy_fast_period,
                slow_period=self._settings.strategy_slow_period,
            ),
            risk_service=self._build_risk_service(),
            starting_equity=Decimal(str(self._settings.paper_account_equity)),
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

    def _build_risk_service(self) -> RiskService:
        return RiskService(
            RiskLimits(
                risk_per_trade_pct=Decimal(str(self._settings.risk_per_trade_pct)),
                max_open_positions=self._settings.max_open_positions,
                max_daily_loss_pct=Decimal(str(self._settings.max_daily_loss_pct)),
                paper_trading_only=not self._settings.live_trading_enabled,
            )
        )

    @classmethod
    def _quantize_decimal(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return value.quantize(cls._decimal_precision)
