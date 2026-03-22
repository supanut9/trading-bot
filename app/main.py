from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.application.services.runtime_startup_service import validate_runtime_startup
from app.config import get_settings
from app.core.logger import (
    build_correlation_id,
    configure_logging,
    correlation_context,
    get_logger,
)
from app.infrastructure.database.init_db import init_database
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
    tables = init_database(settings)
    logger.info("api_database_initialized tables=%s", ",".join(tables))
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

    if settings.allowed_frontend_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_frontend_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def add_request_correlation(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or build_correlation_id("req")
        started_at = perf_counter()
        request.state.request_id = request_id
        with correlation_context(request_id):
            logger.info(
                "http_request_started method=%s path=%s",
                request.method,
                request.url.path,
            )
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(
                    "http_request_failed method=%s path=%s",
                    request.method,
                    request.url.path,
                )
                raise
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "http_request_completed method=%s path=%s status_code=%s duration_ms=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response

    app.include_router(controls_router)
    app.include_router(health_router)
    app.include_router(market_data_router)
    app.include_router(operations_router)
    app.include_router(performance_router)
    app.include_router(reports_router)
    app.include_router(status_router)
    return app


app = create_app()
