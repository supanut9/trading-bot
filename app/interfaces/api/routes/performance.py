from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.application.services.performance_analytics_service import PerformanceAnalyticsService
from app.application.services.reporting_export_service import ReportingExportService
from app.config import Settings, get_settings
from app.infrastructure.database.session import get_session
from app.interfaces.api.schemas import PerformanceAnalyticsResponse

router = APIRouter(prefix="/performance", tags=["performance"])
session_dependency = Depends(get_session)
settings_dependency = Depends(get_settings)


@router.get("/summary", response_model=PerformanceAnalyticsResponse)
def get_performance_summary(
    session: Session = session_dependency,
) -> PerformanceAnalyticsResponse:
    analytics = PerformanceAnalyticsService(session).build()
    return PerformanceAnalyticsResponse.model_validate(analytics)


@router.get("/daily.csv")
def export_performance_daily_csv(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
) -> Response:
    content = ReportingExportService(session, settings).export_performance_daily_csv()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="performance-daily.csv"'},
    )


@router.get("/equity.csv")
def export_performance_equity_csv(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
) -> Response:
    content = ReportingExportService(session, settings).export_performance_equity_csv()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="performance-equity.csv"'},
    )
