from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text

from app.application.services.live_readiness_service import LiveReadinessService
from app.config import Settings
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory

RuntimeComponent = Literal["api", "worker", "backtest"]


@dataclass(frozen=True)
class RuntimeStartupContext:
    component: RuntimeComponent
    app: str
    environment: str
    execution_mode: str
    exchange: str
    symbol: str
    timeframe: str
    database_scheme: str
    log_level: str
    live_readiness_status: str | None = None
    live_readiness_blocking_reasons: tuple[str, ...] = ()


def build_runtime_startup_context(
    settings: Settings,
    component: RuntimeComponent,
) -> RuntimeStartupContext:
    database_scheme = settings.database_url.split(":", 1)[0]
    return RuntimeStartupContext(
        component=component,
        app=settings.app_name,
        environment=settings.app_env,
        execution_mode=settings.execution_mode,
        exchange=settings.exchange_name,
        symbol=settings.default_symbol,
        timeframe=settings.default_timeframe,
        database_scheme=database_scheme,
        log_level=settings.log_level.upper(),
    )


def validate_runtime_settings(
    settings: Settings,
    component: RuntimeComponent,
) -> list[str]:
    errors: list[str] = []
    non_local_runtime = settings.app_env.lower() != "local"

    if non_local_runtime and settings.database_url.startswith("sqlite"):
        errors.append("non-local runtime requires a PostgreSQL-compatible DATABASE_URL")

    if component == "api" and non_local_runtime and settings.api_host in {"127.0.0.1", "localhost"}:
        errors.append("non-local api runtime must not bind API_HOST to a loopback address")

    if settings.notification_channel == "webhook" and not settings.notification_webhook_url:
        errors.append("NOTIFICATION_WEBHOOK_URL is required when NOTIFICATION_CHANNEL=webhook")

    if (
        component == "worker"
        and settings.live_trading_enabled
        and not settings.startup_state_sync_enabled
    ):
        errors.append("live worker runtime requires STARTUP_STATE_SYNC_ENABLED=true")

    return errors


def ensure_database_connectivity(settings: Settings) -> None:
    engine = create_engine_from_settings(settings)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _log_redacted_settings(settings: Settings) -> None:
    from app.core.logger import get_logger

    logger = get_logger(__name__)
    dump = settings.model_dump()
    for key in dump:
        if any(secret_term in key.lower() for secret_term in ["key", "secret", "url", "password"]):
            dump[key] = "********"
    logger.info("startup_configuration_redacted config=%s", dump)


def validate_runtime_startup(
    settings: Settings,
    component: RuntimeComponent,
) -> RuntimeStartupContext:
    _log_redacted_settings(settings)

    errors = validate_runtime_settings(settings, component)
    if errors:
        detail = "; ".join(errors)
        raise ValueError(detail)

    ensure_database_connectivity(settings)

    # Record startup in audit log
    from app.application.services.audit_service import AuditService

    session = create_session_factory(settings)()
    try:
        AuditService(session=session).record_event(
            event_type="system_startup",
            exchange=settings.exchange_name,
            symbol=settings.default_symbol,
            detail=f"component={component} mode={settings.execution_mode} env={settings.app_env}",
        )
        session.commit()
    finally:
        session.close()

    context = build_runtime_startup_context(settings, component)
    if not settings.live_trading_enabled:
        return context

    session = create_session_factory(settings)()
    try:
        report = LiveReadinessService(session, settings).build_report()
    finally:
        session.close()

    return RuntimeStartupContext(
        component=context.component,
        app=context.app,
        environment=context.environment,
        execution_mode=context.execution_mode,
        exchange=context.exchange,
        symbol=context.symbol,
        timeframe=context.timeframe,
        database_scheme=context.database_scheme,
        log_level=context.log_level,
        live_readiness_status=report.status,
        live_readiness_blocking_reasons=tuple(report.blocking_reasons),
    )
