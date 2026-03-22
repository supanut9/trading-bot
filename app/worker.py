from time import sleep

from app.application.services.runtime_startup_service import validate_runtime_startup
from app.config import get_settings
from app.core.logger import configure_logging, get_logger
from app.infrastructure.database.init_db import init_database
from app.jobs.backtest_summary_job import BacktestSummaryJob
from app.jobs.interval_scheduler import IntervalScheduler
from app.jobs.live_reconcile_job import LiveReconcileJob
from app.jobs.startup_state_sync_job import StartupStateSyncJob
from app.jobs.worker_cycle_job import WorkerCycleJob

logger = get_logger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    logger.info("runtime_starting component=worker")
    try:
        context = validate_runtime_startup(settings, "worker")
    except Exception as exc:
        logger.error("runtime_startup_failed component=worker detail=%s", exc)
        return
    logger.info(
        "runtime_ready component=%s app=%s env=%s mode=%s exchange=%s symbol=%s "
        "timeframe=%s database_scheme=%s log_level=%s live_safety_status=%s "
        "live_trading_halted=%s live_max_order_notional=%s live_max_position_quantity=%s "
        "live_readiness_status=%s live_readiness_blocking_reasons=%s",
        context.component,
        context.app,
        context.environment,
        context.execution_mode,
        context.exchange,
        context.symbol,
        context.timeframe,
        context.database_scheme,
        context.log_level,
        "disabled"
        if not settings.live_trading_enabled
        else ("halted" if settings.live_trading_halted else "enabled"),
        settings.live_trading_halted,
        settings.live_max_order_notional,
        settings.live_max_position_quantity,
        context.live_readiness_status,
        list(context.live_readiness_blocking_reasons),
    )
    tables = init_database(settings)
    logger.info("worker_database_initialized tables=%s", ",".join(tables))

    if settings.live_trading_enabled and settings.startup_state_sync_enabled:
        startup_sync = StartupStateSyncJob(settings).run()
        if startup_sync.status != "completed":
            logger.warning(
                "worker_startup_aborted reason=startup_state_sync_failed detail=%s "
                "reconciled_count=%s filled_count=%s review_required_count=%s",
                startup_sync.detail,
                startup_sync.reconciled_count,
                startup_sync.filled_count,
                startup_sync.review_required_count,
            )
            return

    worker_job = WorkerCycleJob(settings)

    try:
        if settings.worker_run_once:
            worker_job.run()
            return

        scheduler = IntervalScheduler()
        scheduler.add_job(
            name="worker_cycle",
            interval_seconds=settings.worker_poll_interval_seconds,
            runner=worker_job.run,
        )

        if settings.backtest_schedule_enabled:
            logger.info(
                "worker_backtest_schedule_enabled interval_seconds=%s",
                settings.backtest_schedule_interval_seconds,
            )
            scheduler.add_job(
                name="backtest_summary",
                interval_seconds=settings.backtest_schedule_interval_seconds,
                runner=BacktestSummaryJob(settings).run,
            )

        if settings.live_trading_enabled and settings.live_reconcile_schedule_enabled:
            logger.info(
                "worker_live_reconcile_schedule_enabled interval_seconds=%s",
                settings.live_reconcile_schedule_interval_seconds,
            )
            scheduler.add_job(
                name="live_reconcile",
                interval_seconds=settings.live_reconcile_schedule_interval_seconds,
                runner=LiveReconcileJob(settings).run,
            )

        while True:
            scheduler.run_pending()
            sleep_for = scheduler.seconds_until_next_run()
            sleep(max(sleep_for or 0.0, 1.0))
    except KeyboardInterrupt:
        logger.info("worker_stopped reason=keyboard_interrupt")


if __name__ == "__main__":
    main()
