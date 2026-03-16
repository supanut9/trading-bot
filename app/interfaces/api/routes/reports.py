from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.application.services.reporting_export_service import ReportingExportService
from app.config import Settings, get_settings
from app.infrastructure.database.session import get_session

router = APIRouter(prefix="/reports", tags=["reports"])
session_dependency = Depends(get_session)
settings_dependency = Depends(get_settings)


def _csv_response(filename: str, content: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/positions.csv")
def export_positions(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
) -> Response:
    content = ReportingExportService(session, settings).export_positions_csv()
    return _csv_response("positions.csv", content)


@router.get("/trades.csv")
def export_trades(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Response:
    content = ReportingExportService(session, settings).export_trades_csv(limit=limit)
    return _csv_response("trades.csv", content)


@router.get("/backtest-summary.csv")
def export_backtest_summary(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
) -> Response:
    content = ReportingExportService(session, settings).export_backtest_summary_csv()
    return _csv_response("backtest-summary.csv", content)
