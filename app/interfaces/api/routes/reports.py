from collections import defaultdict
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session, sessionmaker

from app.application.services.audit_service import AuditEventFilters
from app.application.services.live_order_recovery_report_service import RecoveryReportFilters
from app.application.services.performance_analytics_service import EquityCurvePoint
from app.application.services.reporting_dashboard_service import (
    ReportingDashboard,
    ReportingDashboardService,
)
from app.application.services.reporting_export_service import ReportingExportService
from app.config import Settings, get_settings
from app.infrastructure.database.session import get_session, get_session_factory_dependency

router = APIRouter(prefix="/reports", tags=["reports"])
session_dependency = Depends(get_session)
settings_dependency = Depends(get_settings)
session_factory_dependency = Depends(get_session_factory_dependency)


def _csv_response(filename: str, content: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _html_response(content: str) -> HTMLResponse:
    return HTMLResponse(content=content)


def _render_card(label: str, value: str) -> str:
    return (
        f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>'
    )


def _build_recovery_filters(
    *,
    order_status: str | None,
    requires_review: bool | None,
    event_type: str | None,
    search: str | None,
) -> RecoveryReportFilters:
    return RecoveryReportFilters(
        order_status=order_status.strip() if order_status and order_status.strip() else None,
        requires_review=requires_review,
        event_type=event_type.strip() if event_type and event_type.strip() else None,
        search=search.strip() if search and search.strip() else None,
    )


def _recovery_query_string(filters: RecoveryReportFilters) -> str:
    query: dict[str, str] = {}
    if filters.order_status is not None:
        query["recovery_order_status"] = filters.order_status
    if filters.requires_review is not None:
        query["recovery_requires_review"] = str(filters.requires_review).lower()
    if filters.event_type is not None:
        query["recovery_event_type"] = filters.event_type
    if filters.search is not None:
        query["recovery_search"] = filters.search
    if not query:
        return ""
    return f"?{urlencode(query)}"


def _build_notification_filters(
    *,
    status: str | None,
    channel: str | None,
    related_event_type: str | None,
) -> AuditEventFilters:
    return AuditEventFilters(
        event_type="notification_delivery",
        status=status.strip() if status and status.strip() else None,
        channel=channel.strip() if channel and channel.strip() else None,
        related_event_type=(
            related_event_type.strip()
            if related_event_type and related_event_type.strip()
            else None
        ),
    )


def _notification_query_string(filters: AuditEventFilters) -> str:
    query: dict[str, str] = {}
    if filters.status is not None:
        query["notification_status"] = filters.status
    if filters.channel is not None:
        query["notification_channel"] = filters.channel
    if filters.related_event_type is not None:
        query["notification_related_event_type"] = filters.related_event_type
    if not query:
        return ""
    return f"?{urlencode(query)}"


def _render_equity_curve_panels(dashboard: ReportingDashboard) -> str:
    points_by_mode: dict[str, list[EquityCurvePoint]] = defaultdict(list)
    for point in dashboard.performance_equity_curve:
        points_by_mode[point.mode].append(point)

    if not points_by_mode:
        return '<div class="curve-empty">No equity curve points available.</div>'

    width = 640
    height = 180
    charts: list[str] = []
    for mode in sorted(points_by_mode):
        points = points_by_mode[mode]
        net_values = [point.net_pnl for point in points]
        minimum = min(net_values)
        maximum = max(net_values)
        if minimum == maximum:
            minimum -= Decimal("1")
            maximum += Decimal("1")
        vertical_span = maximum - minimum
        horizontal_steps = max(len(points) - 1, 1)
        path_segments: list[str] = []
        for index, point in enumerate(points):
            x = (Decimal(index) / Decimal(horizontal_steps)) * Decimal(width)
            normalized = (point.net_pnl - minimum) / vertical_span
            y = Decimal(height) - (normalized * Decimal(height))
            command = "M" if index == 0 else "L"
            path_segments.append(f"{command} {x:.2f} {y:.2f}")

        zero_line = ""
        if minimum <= Decimal("0") <= maximum:
            normalized_zero = (Decimal("0") - minimum) / vertical_span
            zero_y = Decimal(height) - (normalized_zero * Decimal(height))
            zero_line = (
                f'<line class="baseline" x1="0" y1="{zero_y:.2f}" '
                f'x2="{width}" y2="{zero_y:.2f}"></line>'
            )

        latest_point = points[-1]
        path_data = " ".join(path_segments)
        charts.append(
            '<article class="curve-card">'
            f'<div class="label">Mode</div><h3>{mode}</h3>'
            '<div class="curve-meta">'
            f"<span>Latest Net PnL {latest_point.net_pnl}</span>"
            f"<span>Max Drawdown {max(point.drawdown for point in points)}</span>"
            f"<span>Points {len(points)}</span>"
            "</div>"
            f'<svg class="equity-chart" viewBox="0 0 {width} {height}" '
            'preserveAspectRatio="none" role="img" '
            f'aria-label="{mode} equity curve">'
            f"{zero_line}"
            f'<path class="curve-line" d="{path_data}"></path>'
            "</svg>"
            "</article>"
        )
    return "".join(charts)


def _render_dashboard(service: ReportingDashboardService) -> str:
    dashboard = service.build_dashboard()
    recovery_query = _recovery_query_string(dashboard.recovery_filters)
    notification_query = _notification_query_string(dashboard.notification_filters)
    selected_requires_review = ""
    if dashboard.recovery_filters.requires_review is True:
        selected_requires_review = "review-only"
    elif dashboard.recovery_filters.requires_review is False:
        selected_requires_review = "non-review"
    recovery_order_status_value = dashboard.recovery_filters.order_status or ""
    recovery_event_type_value = dashboard.recovery_filters.event_type or ""
    recovery_search_value = dashboard.recovery_filters.search or ""
    recovery_requires_review_value = (
        str(dashboard.recovery_filters.requires_review)
        if dashboard.recovery_filters.requires_review is not None
        else "-"
    )
    recovery_requires_review_query_value = (
        ""
        if dashboard.recovery_filters.requires_review is None
        else str(dashboard.recovery_filters.requires_review).lower()
    )
    notification_status_value = dashboard.notification_filters.status or ""
    notification_channel_value = dashboard.notification_filters.channel or ""
    notification_related_event_type_value = dashboard.notification_filters.related_event_type or ""
    recovery_any_selected = "selected" if selected_requires_review == "" else ""
    recovery_review_selected = "selected" if selected_requires_review == "review-only" else ""
    recovery_non_review_selected = "selected" if selected_requires_review == "non-review" else ""
    performance_rows = (
        "".join(
            (
                "<tr>"
                f"<td>{summary.mode}</td>"
                f"<td>{summary.net_pnl}</td>"
                f"<td>{summary.total_realized_pnl}</td>"
                f"<td>{summary.total_unrealized_pnl}</td>"
                f"<td>{summary.trade_count}</td>"
                f"<td>{summary.win_rate_pct or '-'}</td>"
                f"<td>{summary.expectancy or '-'}</td>"
                f"<td>{summary.max_drawdown}</td>"
                "</tr>"
            )
            for summary in dashboard.performance_summaries
        )
        or '<tr><td colspan="8">No performance analytics available.</td></tr>'
    )
    performance_daily_rows = (
        "".join(
            (
                "<tr>"
                f"<td>{row.trade_date.isoformat()}</td>"
                f"<td>{row.mode}</td>"
                f"<td>{row.trade_count}</td>"
                f"<td>{row.closed_trade_count}</td>"
                f"<td>{row.net_pnl}</td>"
                "</tr>"
            )
            for row in dashboard.performance_daily_rows
        )
        or '<tr><td colspan="5">No daily performance rows available.</td></tr>'
    )
    equity_curve_panels = _render_equity_curve_panels(dashboard)
    positions_rows = (
        "".join(
            (
                "<tr>"
                f"<td>{position.symbol}</td>"
                f"<td>{position.side}</td>"
                f"<td>{position.quantity}</td>"
                f"<td>{position.average_entry_price or '-'}</td>"
                f"<td>{position.realized_pnl}</td>"
                f"<td>{position.unrealized_pnl}</td>"
                "</tr>"
            )
            for position in dashboard.positions
        )
        or '<tr><td colspan="6">No positions recorded.</td></tr>'
    )
    trades_rows = (
        "".join(
            (
                "<tr>"
                f"<td>{trade.id}</td>"
                f"<td>{trade.symbol}</td>"
                f"<td>{trade.side}</td>"
                f"<td>{trade.quantity}</td>"
                f"<td>{trade.price}</td>"
                "</tr>"
            )
            for trade in dashboard.trades
        )
        or '<tr><td colspan="5">No trades recorded.</td></tr>'
    )
    stale_orders_rows = (
        "".join(
            (
                "<tr>"
                f"<td>{order.id}</td>"
                f"<td>{order.symbol}</td>"
                f"<td>{order.side}</td>"
                f"<td>{order.status}</td>"
                f"<td>{order.age_minutes}</td>"
                "</tr>"
            )
            for order in dashboard.stale_live_orders
        )
        or '<tr><td colspan="5">No stale live orders detected.</td></tr>'
    )
    recovery_order_rows = (
        "".join(
            (
                "<tr>"
                f"<td>{item.order.id}</td>"
                f"<td>{item.order.symbol}</td>"
                f"<td>{item.order.side}</td>"
                f"<td>{item.order.status}</td>"
                f"<td>{'yes' if item.requires_operator_review else 'no'}</td>"
                f"<td>{item.next_action}</td>"
                "</tr>"
            )
            for item in dashboard.recovery_orders
        )
        or '<tr><td colspan="6">No unresolved live orders in the recovery queue.</td></tr>'
    )
    recovery_event_rows = (
        "".join(
            (
                "<tr>"
                f"<td>{event.created_at.isoformat()}</td>"
                f"<td>{event.event_type}</td>"
                f"<td>{event.source}</td>"
                f"<td>{event.status}</td>"
                f"<td>{event.detail}</td>"
                f"<td>{event.context}</td>"
                "</tr>"
            )
            for event in dashboard.recovery_events
        )
        or '<tr><td colspan="6">No recent recovery events recorded.</td></tr>'
    )
    audit_rows = (
        "".join(
            (
                "<tr>"
                f"<td>{event.created_at.isoformat()}</td>"
                f"<td>{event.event_type}</td>"
                f"<td>{event.source}</td>"
                f"<td>{event.status}</td>"
                f"<td>{event.detail}</td>"
                "</tr>"
            )
            for event in dashboard.audit_events
        )
        or '<tr><td colspan="5">No audit events recorded.</td></tr>'
    )
    notification_delivery_rows = (
        "".join(
            (
                "<tr>"
                f"<td>{event.created_at.isoformat()}</td>"
                f"<td>{event.status}</td>"
                f"<td>{event.channel or '-'}</td>"
                f"<td>{event.related_event_type or '-'}</td>"
                f"<td>{event.detail}</td>"
                "</tr>"
            )
            for event in dashboard.notification_delivery_events
        )
        or '<tr><td colspan="5">No notification deliveries recorded.</td></tr>'
    )

    mode_label = "Paper" if dashboard.paper_trading else "Live"
    live_label = "enabled" if dashboard.live_trading_enabled else "disabled"
    subheadline = (
        f"Environment: {dashboard.environment}. "
        f"Market: {dashboard.exchange} {dashboard.symbol} {dashboard.timeframe}. "
        f"Trading mode: {mode_label}. "
        f"Live execution: {live_label}. "
        f"Database: {dashboard.database_status}."
    )
    latest_price_label = dashboard.latest_price or dashboard.latest_price_status
    cards = "".join(
        [
            _render_card("Open Positions", str(dashboard.position_count)),
            _render_card("Recent Trades", str(dashboard.trade_count)),
            _render_card("Realized PnL", str(dashboard.total_realized_pnl)),
            _render_card("Unrealized PnL", str(dashboard.total_unrealized_pnl)),
            _render_card("Latest Price", latest_price_label),
            _render_card("Stale Live Orders", str(len(dashboard.stale_live_orders))),
            _render_card("Unresolved Live Orders", str(dashboard.unresolved_live_orders)),
            _render_card("Recovery Events", str(dashboard.recovery_event_count)),
            _render_card("Backtest Status", dashboard.backtest.status),
            _render_card("Backtest Trades", str(dashboard.backtest.total_trades or 0)),
        ]
    )
    latest_recovery_summary = "Latest recovery event: none."
    if dashboard.latest_recovery_event_at is not None:
        latest_recovery_summary = (
            f"Latest recovery event: {dashboard.latest_recovery_event_type} "
            f"{dashboard.latest_recovery_event_status} at {dashboard.latest_recovery_event_at}. "
            f"{dashboard.latest_recovery_event_context or '-'}."
        )
    latest_worker_summary = "Latest worker cycle: none."
    if dashboard.latest_worker_event_at is not None:
        latest_worker_summary = (
            f"Latest worker cycle: {dashboard.latest_worker_event_status} "
            f"at {dashboard.latest_worker_event_at}. "
            f"{dashboard.latest_worker_event_detail}."
        )
    latest_worker_signal = dashboard.latest_worker_signal_action or "-"
    latest_worker_order = dashboard.latest_worker_client_order_id or "-"
    latest_notification_delivery_summary = "Latest notification delivery: none."
    if dashboard.latest_notification_delivery_at is not None:
        latest_notification_delivery_summary = (
            f"Latest notification delivery: {dashboard.latest_notification_delivery_status} "
            f"via {dashboard.latest_notification_delivery_channel or '-'} "
            f"for {dashboard.latest_notification_related_event_type or '-'} "
            f"at {dashboard.latest_notification_delivery_at}."
        )
    summary_cards = "".join(
        [
            _render_card(
                "Latest Worker Status",
                dashboard.latest_worker_event_status or "none",
            ),
            _render_card("Worker Signal", latest_worker_signal),
            _render_card("Worker Order", latest_worker_order),
            _render_card(
                "Net PnL",
                str(dashboard.total_realized_pnl + dashboard.total_unrealized_pnl),
            ),
            _render_card("Open Positions", str(dashboard.position_count)),
            _render_card("Recent Trades", str(dashboard.trade_count)),
            _render_card("Stale Live Orders", str(len(dashboard.stale_live_orders))),
            _render_card("Unresolved Live Orders", str(dashboard.unresolved_live_orders)),
            _render_card(
                "Notification Deliveries",
                str(dashboard.notification_delivery_count),
            ),
            _render_card(
                "Notification Failures",
                str(dashboard.notification_delivery_failed_count),
            ),
        ]
    )
    net_pnl = dashboard.total_realized_pnl + dashboard.total_unrealized_pnl
    recovery_filter_summary = "Recovery filters: none."
    if any(
        value is not None
        for value in (
            dashboard.recovery_filters.order_status,
            dashboard.recovery_filters.requires_review,
            dashboard.recovery_filters.event_type,
            dashboard.recovery_filters.search,
        )
    ):
        recovery_filter_summary = (
            "Recovery filters: "
            f"order_status={dashboard.recovery_filters.order_status or '-'} "
            f"requires_review={recovery_requires_review_value} "
            f"event_type={dashboard.recovery_filters.event_type or '-'} "
            f"search={dashboard.recovery_filters.search or '-'}."
        )
    notification_filter_summary = "Notification delivery filters: none."
    if any(
        value is not None
        for value in (
            dashboard.notification_filters.status,
            dashboard.notification_filters.channel,
            dashboard.notification_filters.related_event_type,
        )
    ):
        notification_filter_summary = (
            "Notification delivery filters: "
            f"status={dashboard.notification_filters.status or '-'} "
            f"channel={dashboard.notification_filters.channel or '-'} "
            f"related_event_type={dashboard.notification_filters.related_event_type or '-'}."
        )

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{dashboard.app_name} Reporting</title>
    <style>
      :root {{
        --ink: #102542;
        --panel: #fffdf7;
        --accent: #b33f62;
        --accent-soft: #f2d1c9;
        --muted: #5d6b82;
        --line: #d7d3c8;
        --bg: linear-gradient(180deg, #f6efe4 0%, #eef4f5 100%);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: Georgia, "Iowan Old Style", serif;
        color: var(--ink);
        background: var(--bg);
      }}
      main {{
        max-width: 1180px;
        margin: 0 auto;
        padding: 32px 20px 48px;
      }}
      .hero {{
        display: grid;
        gap: 16px;
        padding: 28px;
        border: 1px solid var(--line);
        background: rgba(255, 253, 247, 0.92);
        box-shadow: 0 18px 48px rgba(16, 37, 66, 0.08);
      }}
      .eyebrow {{
        font-size: 12px;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: var(--accent);
      }}
      h1 {{
        margin: 0;
        font-size: clamp(2rem, 5vw, 4rem);
        line-height: 0.95;
      }}
      .sub {{
        color: var(--muted);
        max-width: 760px;
        font-size: 1rem;
      }}
      .meta, .cards, .tables {{
        display: grid;
        gap: 16px;
      }}
      .meta {{
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        margin-top: 18px;
      }}
      .cards {{
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        margin-top: 24px;
      }}
      .summary {{
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        margin-top: 24px;
      }}
      .card, .panel {{
        padding: 18px;
        border: 1px solid var(--line);
        background: var(--panel);
      }}
      .label {{
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--muted);
      }}
      .value {{
        margin-top: 10px;
        font-size: 1.8rem;
      }}
      .tables {{
        grid-template-columns: 1fr;
        margin-top: 24px;
      }}
      .curve-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 16px;
      }}
      .curve-card {{
        display: grid;
        gap: 12px;
      }}
      .curve-card h3 {{
        margin: 0;
        font-size: 1.4rem;
      }}
      .curve-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        color: var(--muted);
        font-size: 0.92rem;
      }}
      .equity-chart {{
        width: 100%;
        height: 180px;
        display: block;
        border: 1px solid var(--line);
        background:
          linear-gradient(180deg, rgba(179, 63, 98, 0.10) 0%, rgba(179, 63, 98, 0.02) 100%),
          linear-gradient(180deg, rgba(255, 255, 255, 0.85) 0%, rgba(242, 209, 201, 0.35) 100%);
      }}
      .equity-chart .curve-line {{
        fill: none;
        stroke: var(--accent);
        stroke-width: 3;
        stroke-linecap: round;
        stroke-linejoin: round;
      }}
      .equity-chart .baseline {{
        stroke: var(--muted);
        stroke-width: 1;
        stroke-dasharray: 4 6;
        opacity: 0.65;
      }}
      .curve-empty {{
        color: var(--muted);
      }}
      .panel h2 {{
        margin: 0 0 12px;
        font-size: 1.15rem;
      }}
      .exports {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 16px;
      }}
      .exports a {{
        color: var(--ink);
        text-decoration: none;
        padding: 10px 14px;
        border: 1px solid var(--ink);
        background: var(--accent-soft);
      }}
      .filter-form {{
        display: grid;
        gap: 12px;
      }}
      .filter-form label {{
        display: grid;
        gap: 6px;
      }}
      .filter-form span {{
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--muted);
      }}
      .filter-form input, .filter-form select {{
        width: 100%;
        border: 1px solid var(--line);
        padding: 10px 12px;
        font: inherit;
        color: var(--ink);
        background: #fff;
      }}
      .filter-actions {{
        display: flex;
        gap: 12px;
        align-items: center;
      }}
      .filter-actions button {{
        border: 0;
        padding: 10px 16px;
        font: inherit;
        font-weight: 700;
        color: white;
        background: var(--accent);
        cursor: pointer;
      }}
      .filter-actions a {{
        color: var(--ink);
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.95rem;
      }}
      th, td {{
        padding: 10px 8px;
        border-top: 1px solid var(--line);
        text-align: left;
      }}
      th {{
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
      }}
      @media (max-width: 700px) {{
        main {{ padding: 20px 14px 36px; }}
        .hero {{ padding: 20px; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="eyebrow">Reporting Deck</div>
        <h1>{dashboard.app_name}</h1>
        <div class="sub">{subheadline}</div>
        <div class="sub">{latest_recovery_summary}</div>
        <div class="sub">{latest_worker_summary}</div>
        <div class="sub">{latest_notification_delivery_summary}</div>
        <div class="exports">
          <a href="/reports/positions.csv">Download positions CSV</a>
          <a href="/reports/trades.csv">Download trades CSV</a>
          <a href="/reports/backtest-summary.csv">Download backtest CSV</a>
          <a href="/reports/audit.csv">Download audit CSV</a>
          <a href="/reports/notification-delivery.csv{notification_query}">
            Download notification delivery CSV
          </a>
          <a href="/reports/live-recovery.csv{recovery_query}">Download live recovery CSV</a>
          <a href="/performance/daily.csv">Download daily performance CSV</a>
          <a href="/performance/equity.csv">Download equity curve CSV</a>
        </div>
      </section>
      <section class="cards summary">{summary_cards}</section>
      <section class="cards">{cards}</section>
      <section class="tables">
        <div class="panel">
          <h2>Session Summary</h2>
          <table>
            <tbody>
              <tr>
                <th>Latest Worker Status</th>
                <td>{dashboard.latest_worker_event_status or "-"}</td>
              </tr>
              <tr><th>Worker Detail</th><td>{dashboard.latest_worker_event_detail or "-"}</td></tr>
              <tr><th>Worker Signal</th><td>{latest_worker_signal}</td></tr>
              <tr><th>Worker Order</th><td>{latest_worker_order}</td></tr>
              <tr><th>Net PnL</th><td>{net_pnl}</td></tr>
              <tr><th>Stale Live Orders</th><td>{len(dashboard.stale_live_orders)}</td></tr>
              <tr><th>Unresolved Live Orders</th><td>{dashboard.unresolved_live_orders}</td></tr>
            </tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Performance Summary</h2>
          <table>
            <thead>
              <tr>
                <th>Mode</th>
                <th>Net PnL</th>
                <th>Realized PnL</th>
                <th>Unrealized PnL</th>
                <th>Trades</th>
                <th>Win Rate %</th>
                <th>Expectancy</th>
                <th>Max Drawdown</th>
              </tr>
            </thead>
            <tbody>{performance_rows}</tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Equity Curve</h2>
          <div class="curve-grid">{equity_curve_panels}</div>
        </div>
        <div class="panel">
          <h2>Positions</h2>
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Quantity</th>
                <th>Average Entry</th>
                <th>Realized PnL</th>
                <th>Unrealized PnL</th>
              </tr>
            </thead>
            <tbody>{positions_rows}</tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Recent Trades</h2>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Quantity</th>
                <th>Price</th>
              </tr>
            </thead>
            <tbody>{trades_rows}</tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Stale Live Orders</h2>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Status</th>
                <th>Age Minutes</th>
              </tr>
            </thead>
            <tbody>{stale_orders_rows}</tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Notification Delivery Filters</h2>
          <p>{notification_filter_summary}</p>
          <form method="get" action="/reports" class="filter-form">
            <input
              type="hidden"
              name="recovery_order_status"
              value="{recovery_order_status_value}"
            />
            <input
              type="hidden"
              name="recovery_event_type"
              value="{recovery_event_type_value}"
            />
            <input
              type="hidden"
              name="recovery_search"
              value="{recovery_search_value}"
            />
            <input
              type="hidden"
              name="recovery_requires_review"
              value="{recovery_requires_review_query_value}"
            />
            <label>
              <span>Status</span>
              <input
                type="text"
                name="notification_status"
                value="{notification_status_value}"
              />
            </label>
            <label>
              <span>Channel</span>
              <input
                type="text"
                name="notification_channel"
                value="{notification_channel_value}"
              />
            </label>
            <label>
              <span>Related Event Type</span>
              <input
                type="text"
                name="notification_related_event_type"
                value="{notification_related_event_type_value}"
              />
            </label>
            <div class="filter-actions">
              <button type="submit">Apply Filters</button>
              <a href="/reports">Clear</a>
            </div>
          </form>
        </div>
        <div class="panel">
          <h2>Recovery Filters</h2>
          <p>{recovery_filter_summary}</p>
          <form method="get" action="/reports" class="filter-form">
            <label>
              <span>Order Status</span>
              <input
                type="text"
                name="recovery_order_status"
                value="{recovery_order_status_value}"
              />
            </label>
            <label>
              <span>Event Type</span>
              <input
                type="text"
                name="recovery_event_type"
                value="{recovery_event_type_value}"
              />
            </label>
            <label>
              <span>Review Mode</span>
              <select name="recovery_requires_review">
                <option value="" {recovery_any_selected}>Any</option>
                <option value="true" {recovery_review_selected}>Review Required</option>
                <option value="false" {recovery_non_review_selected}>No Review Required</option>
              </select>
            </label>
            <label>
              <span>Search</span>
              <input
                type="text"
                name="recovery_search"
                value="{recovery_search_value}"
              />
            </label>
            <div class="filter-actions">
              <button type="submit">Apply Filters</button>
              <a href="/reports">Clear</a>
            </div>
          </form>
        </div>
        <div class="panel">
          <h2>Recovery Queue</h2>
          <table>
            <thead>
              <tr>
                <th>Order ID</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Status</th>
                <th>Review Required</th>
                <th>Next Action</th>
              </tr>
            </thead>
            <tbody>{recovery_order_rows}</tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Recovery Timeline</h2>
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Event</th>
                <th>Source</th>
                <th>Status</th>
                <th>Detail</th>
                <th>Context</th>
              </tr>
            </thead>
            <tbody>{recovery_event_rows}</tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Notification Delivery</h2>
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Status</th>
                <th>Channel</th>
                <th>Related Event</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>{notification_delivery_rows}</tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Recent Audit Events</h2>
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Event</th>
                <th>Source</th>
                <th>Status</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>{audit_rows}</tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Daily Performance</h2>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Mode</th>
                <th>Trades</th>
                <th>Closed Trades</th>
                <th>Net PnL</th>
              </tr>
            </thead>
            <tbody>{performance_daily_rows}</tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Backtest Snapshot</h2>
          <table>
            <tbody>
              <tr><th>Status</th><td>{dashboard.backtest.status}</td></tr>
              <tr><th>Detail</th><td>{dashboard.backtest.detail}</td></tr>
              <tr><th>Candle Count</th><td>{dashboard.backtest.candle_count}</td></tr>
              <tr><th>Required Candles</th><td>{dashboard.backtest.required_candles}</td></tr>
              <tr><th>Ending Equity</th><td>{dashboard.backtest.ending_equity or "-"}</td></tr>
              <tr><th>Realized PnL</th><td>{dashboard.backtest.realized_pnl or "-"}</td></tr>
              <tr><th>Return %</th><td>{dashboard.backtest.total_return_pct or "-"}</td></tr>
              <tr><th>Max Drawdown %</th><td>{dashboard.backtest.max_drawdown_pct or "-"}</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>
  </body>
</html>"""


@router.get("", response_class=HTMLResponse)
def reports_dashboard(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
    recovery_order_status: str | None = None,
    recovery_requires_review: bool | None = None,
    recovery_event_type: str | None = None,
    recovery_search: str | None = None,
    notification_status: str | None = None,
    notification_channel: str | None = None,
    notification_related_event_type: str | None = None,
) -> HTMLResponse:
    recovery_filters = _build_recovery_filters(
        order_status=recovery_order_status,
        requires_review=recovery_requires_review,
        event_type=recovery_event_type,
        search=recovery_search,
    )
    notification_filters = _build_notification_filters(
        status=notification_status,
        channel=notification_channel,
        related_event_type=notification_related_event_type,
    )
    content = _render_dashboard(
        ReportingDashboardService(
            session,
            settings,
            session_factory=session_factory,
            recovery_filters=recovery_filters,
            notification_filters=notification_filters,
        )
    )
    return _html_response(content)


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
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> Response:
    content = ReportingExportService(
        session,
        settings,
        session_factory=session_factory,
    ).export_backtest_summary_csv()
    return _csv_response("backtest-summary.csv", content)


@router.get("/audit.csv")
def export_audit_events(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Response:
    content = ReportingExportService(
        session,
        settings,
        session_factory=session_factory,
    ).export_audit_events_csv(limit=limit)
    return _csv_response("audit.csv", content)


@router.get("/notification-delivery.csv")
def export_notification_delivery(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    notification_status: str | None = None,
    notification_channel: str | None = None,
    notification_related_event_type: str | None = None,
) -> Response:
    filters = _build_notification_filters(
        status=notification_status,
        channel=notification_channel,
        related_event_type=notification_related_event_type,
    )
    content = ReportingExportService(
        session,
        settings,
        session_factory=session_factory,
    ).export_notification_delivery_csv(limit=limit, filters=filters)
    return _csv_response("notification-delivery.csv", content)


@router.get("/live-recovery.csv")
def export_live_recovery(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
    recovery_order_status: str | None = None,
    recovery_requires_review: bool | None = None,
    recovery_event_type: str | None = None,
    recovery_search: str | None = None,
) -> Response:
    filters = _build_recovery_filters(
        order_status=recovery_order_status,
        requires_review=recovery_requires_review,
        event_type=recovery_event_type,
        search=recovery_search,
    )
    content = ReportingExportService(
        session,
        settings,
        session_factory=session_factory,
    ).export_live_recovery_csv(filters=filters)
    return _csv_response("live-recovery.csv", content)
