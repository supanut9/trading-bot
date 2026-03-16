from time import sleep

from app.application.services.notification_service import build_notification_service
from app.application.services.worker_orchestration_service import WorkerOrchestrationService
from app.config import get_settings
from app.core.logger import configure_logging, get_logger
from app.infrastructure.database.init_db import init_database
from app.infrastructure.database.session import create_session_factory

logger = get_logger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    mode = "paper" if settings.paper_trading else "live"
    logger.info(
        "worker_started app=%s env=%s mode=%s symbol=%s timeframe=%s",
        settings.app_name,
        settings.app_env,
        mode,
        settings.default_symbol,
        settings.default_timeframe,
    )
    tables = init_database(settings)
    logger.info("worker_database_initialized tables=%s", ",".join(tables))
    session_factory = create_session_factory(settings)
    notifications = build_notification_service(settings)

    try:
        while True:
            result = None
            with session_factory() as session:
                result = WorkerOrchestrationService(session, settings).run_cycle()
                logger.info(
                    "worker_cycle_completed status=%s detail=%s signal=%s order_id=%s trade_id=%s",
                    result.status,
                    result.detail,
                    result.signal_action,
                    result.order_id,
                    result.trade_id,
                )
            if result is not None:
                notifications.notify_worker_cycle(settings, result)

            if settings.worker_run_once:
                break

            sleep(settings.worker_poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("worker_stopped reason=keyboard_interrupt")


if __name__ == "__main__":
    main()
