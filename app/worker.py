from time import sleep

from app.config import get_settings
from app.core.logger import configure_logging, get_logger
from app.infrastructure.database.init_db import init_database
from app.jobs.backtest_summary_job import BacktestSummaryJob
from app.jobs.interval_scheduler import IntervalScheduler
from app.jobs.live_reconcile_job import LiveReconcileJob
from app.jobs.worker_cycle_job import WorkerCycleJob

logger = get_logger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    logger.info(
        "worker_started app=%s env=%s mode=%s symbol=%s timeframe=%s",
        settings.app_name,
        settings.app_env,
        settings.execution_mode,
        settings.default_symbol,
        settings.default_timeframe,
    )
    tables = init_database(settings)
    logger.info("worker_database_initialized tables=%s", ",".join(tables))
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
