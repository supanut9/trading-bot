from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.application.services.live_performance_review_service import LivePerformanceReviewService
from app.application.services.performance_analytics_service import PerformanceAnalyticsService
from app.application.services.reporting_export_service import ReportingExportService
from app.application.services.strategy_iteration_service import StrategyIterationService
from app.config import Settings, get_settings
from app.infrastructure.database.session import get_session
from app.interfaces.api.schemas import (
    LivePerformanceReviewResponse,
    PerformanceAnalyticsResponse,
    StrategyIterationPlanResponse,
)

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


@router.get("/live-review", response_model=LivePerformanceReviewResponse)
def get_live_performance_review(
    exchange: str = Query(default="binance"),
    symbol: str = Query(default="BTC/USDT"),
    review_period_days: int = Query(default=30, ge=1, le=365),
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
) -> LivePerformanceReviewResponse:
    review = LivePerformanceReviewService(session).get_performance_review(
        exchange=exchange,
        symbol=symbol,
        review_period_days=review_period_days,
    )
    return LivePerformanceReviewResponse.model_validate(review)


@router.get("/iteration-plan", response_model=StrategyIterationPlanResponse)
def get_strategy_iteration_plan(
    exchange: str = Query(default="binance"),
    symbol: str = Query(default="BTC/USDT"),
    review_period_days: int = Query(default=30, ge=1, le=365),
    session: Session = session_dependency,
) -> StrategyIterationPlanResponse:
    """
    Returns a structured re-validation checklist based on live performance.
    Steps describe what the operator (or AI agent) must do to re-promote
    the strategy to live trading.
    """
    plan = StrategyIterationService(session).get_iteration_plan(
        exchange=exchange,
        symbol=symbol,
        review_period_days=review_period_days,
    )
    return StrategyIterationPlanResponse.model_validate(plan)
