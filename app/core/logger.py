import logging

from app.config import Settings, get_settings

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s event=%(message)s"


def configure_logging(settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    logging.basicConfig(
        level=active_settings.log_level.upper(),
        format=LOG_FORMAT,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
