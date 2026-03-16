from time import sleep

from app.application.services.operational_control_service import OperationalControlService
from app.config import get_settings
from app.core.logger import configure_logging, get_logger
from app.infrastructure.database.init_db import init_database

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
    controls = OperationalControlService(settings)

    try:
        while True:
            result = controls.run_worker_cycle()
            logger.info(
                "worker_cycle_completed status=%s detail=%s signal=%s "
                "order_id=%s trade_id=%s notified=%s",
                result.status,
                result.detail,
                result.signal_action,
                result.order_id,
                result.trade_id,
                result.notified,
            )

            if settings.worker_run_once:
                break

            sleep(settings.worker_poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("worker_stopped reason=keyboard_interrupt")


if __name__ == "__main__":
    main()
