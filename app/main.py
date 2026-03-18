from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.application.services.runtime_startup_service import validate_runtime_startup
from app.config import get_settings
from app.core.logger import configure_logging, get_logger
from app.interfaces.api.routes.console import router as console_router
from app.interfaces.api.routes.controls import router as controls_router
from app.interfaces.api.routes.health import router as health_router
from app.interfaces.api.routes.market_data import router as market_data_router
from app.interfaces.api.routes.operations import router as operations_router
from app.interfaces.api.routes.performance import router as performance_router
from app.interfaces.api.routes.reports import router as reports_router
from app.interfaces.api.routes.status import router as status_router

settings = get_settings()
configure_logging(settings)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("runtime_starting component=api")
    context = validate_runtime_startup(settings, "api")
    logger.info(
        "runtime_ready component=%s app=%s env=%s mode=%s exchange=%s symbol=%s "
        "timeframe=%s database_scheme=%s log_level=%s",
        context.component,
        context.app,
        context.environment,
        context.execution_mode,
        context.exchange,
        context.symbol,
        context.timeframe,
        context.database_scheme,
        context.log_level,
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(console_router)
    app.include_router(controls_router)
    app.include_router(health_router)
    app.include_router(market_data_router)
    app.include_router(operations_router)
    app.include_router(performance_router)
    app.include_router(reports_router)
    app.include_router(status_router)
    return app


app = create_app()
