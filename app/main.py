from fastapi import FastAPI

from app.config import get_settings
from app.core.logger import configure_logging
from app.interfaces.api.routes.controls import router as controls_router
from app.interfaces.api.routes.health import router as health_router
from app.interfaces.api.routes.market_data import router as market_data_router
from app.interfaces.api.routes.operations import router as operations_router
from app.interfaces.api.routes.reports import router as reports_router
from app.interfaces.api.routes.status import router as status_router

settings = get_settings()
configure_logging(settings)

app = FastAPI(title=settings.app_name)
app.include_router(controls_router)
app.include_router(health_router)
app.include_router(market_data_router)
app.include_router(operations_router)
app.include_router(reports_router)
app.include_router(status_router)
