import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from uuid import uuid4

from app.config import Settings, get_settings

LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s correlation_id=%(correlation_id)s event=%(message)s"
)
_CORRELATION_ID: ContextVar[str] = ContextVar("correlation_id", default="-")
_DEFAULT_RECORD_FACTORY = logging.getLogRecordFactory()


def _build_log_record(*args, **kwargs) -> logging.LogRecord:
    record = _DEFAULT_RECORD_FACTORY(*args, **kwargs)
    record.correlation_id = get_correlation_id()
    return record


logging.setLogRecordFactory(_build_log_record)


def configure_logging(settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    logging.basicConfig(
        level=active_settings.log_level.upper(),
        format=LOG_FORMAT,
        force=True,
    )
    logging.setLogRecordFactory(_build_log_record)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def get_correlation_id() -> str:
    return _CORRELATION_ID.get()


def build_correlation_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


@contextmanager
def correlation_context(correlation_id: str | None = None) -> Iterator[str]:
    active_correlation_id = correlation_id or build_correlation_id("runtime")
    token: Token[str] = _CORRELATION_ID.set(active_correlation_id)
    try:
        yield active_correlation_id
    finally:
        _CORRELATION_ID.reset(token)
