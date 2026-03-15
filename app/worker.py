from app.config import get_settings
from app.core.logger import configure_logging, get_logger

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


if __name__ == "__main__":
    main()
