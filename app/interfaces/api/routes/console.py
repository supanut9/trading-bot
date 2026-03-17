from html import escape

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, sessionmaker

from app.application.services.operational_control_service import (
    BacktestControlResult,
    MarketSyncControlResult,
    OperationalControlService,
    WorkerControlResult,
)
from app.application.services.reporting_dashboard_service import (
    ReportingDashboard,
    ReportingDashboardService,
)
from app.config import Settings, get_settings
from app.infrastructure.database.session import get_session_factory_dependency

router = APIRouter(prefix="/console", tags=["console"])
settings_dependency = Depends(get_settings)
session_factory_dependency = Depends(get_session_factory_dependency)


def _html_response(content: str) -> HTMLResponse:
    return HTMLResponse(content=content)


def _build_dashboard(
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> ReportingDashboard:
    with session_factory() as session:
        return ReportingDashboardService(
            session,
            settings,
            session_factory=session_factory,
        ).build_dashboard()


def _render_metric_card(label: str, value: str, *, accent: bool = False) -> str:
    card_class = "metric accent" if accent else "metric"
    return (
        f'<div class="{card_class}">'
        f'<div class="metric-label">{escape(label)}</div>'
        f'<div class="metric-value">{escape(value)}</div>'
        "</div>"
    )


def _render_action_form(action: str, label: str, note: str) -> str:
    return f"""
        <form method="post" action="/console/actions/{escape(action)}" class="action-form">
          <button type="submit">{escape(label)}</button>
          <p>{escape(note)}</p>
        </form>
    """


def _render_action_result(
    action_name: str,
    result: WorkerControlResult | BacktestControlResult | MarketSyncControlResult,
) -> str:
    rows: list[tuple[str, str]] = [
        ("Status", result.status),
        ("Detail", result.detail),
    ]
    if isinstance(result, WorkerControlResult):
        rows.extend(
            [
                ("Signal Action", result.signal_action or "-"),
                ("Client Order ID", result.client_order_id or "-"),
                ("Order ID", str(result.order_id) if result.order_id is not None else "-"),
                ("Trade ID", str(result.trade_id) if result.trade_id is not None else "-"),
                (
                    "Position Quantity",
                    str(result.position_quantity) if result.position_quantity is not None else "-",
                ),
            ]
        )
    elif isinstance(result, BacktestControlResult):
        rows.extend(
            [
                ("Candle Count", str(result.candle_count)),
                ("Required Candles", str(result.required_candles)),
                ("Ending Equity", str(result.ending_equity or "-")),
                ("Realized PnL", str(result.realized_pnl or "-")),
                ("Total Trades", str(result.total_trades or 0)),
                ("Winning Trades", str(result.winning_trades or 0)),
                ("Losing Trades", str(result.losing_trades or 0)),
            ]
        )
    else:
        rows.extend(
            [
                ("Fetched Count", str(result.fetched_count)),
                ("Stored Count", str(result.stored_count)),
                (
                    "Latest Open Time",
                    result.latest_open_time.isoformat() if result.latest_open_time else "-",
                ),
            ]
        )

    rendered_rows = "".join(
        f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>" for label, value in rows
    )
    return f"""
      <section class="panel result-panel">
        <div class="panel-kicker">Last Action</div>
        <h2>{escape(action_name)}</h2>
        <table>
          <tbody>{rendered_rows}</tbody>
        </table>
      </section>
    """


def _render_positions_rows(dashboard: ReportingDashboard) -> str:
    return (
        "".join(
            (
                "<tr>"
                f"<td>{escape(position.symbol)}</td>"
                f"<td>{escape(position.side)}</td>"
                f"<td>{escape(str(position.quantity))}</td>"
                f"<td>{escape(str(position.average_entry_price or '-'))}</td>"
                f"<td>{escape(str(position.realized_pnl))}</td>"
                f"<td>{escape(str(position.unrealized_pnl))}</td>"
                "</tr>"
            )
            for position in dashboard.positions
        )
        or '<tr><td colspan="6">No positions recorded.</td></tr>'
    )


def _render_trades_rows(dashboard: ReportingDashboard) -> str:
    return (
        "".join(
            (
                "<tr>"
                f"<td>{trade.id}</td>"
                f"<td>{escape(trade.symbol)}</td>"
                f"<td>{escape(trade.side)}</td>"
                f"<td>{escape(str(trade.quantity))}</td>"
                f"<td>{escape(str(trade.price))}</td>"
                "</tr>"
            )
            for trade in dashboard.trades
        )
        or '<tr><td colspan="5">No trades recorded.</td></tr>'
    )


def _render_audit_rows(dashboard: ReportingDashboard) -> str:
    return (
        "".join(
            (
                "<tr>"
                f"<td>{escape(event.created_at.isoformat())}</td>"
                f"<td>{escape(event.event_type)}</td>"
                f"<td>{escape(event.source)}</td>"
                f"<td>{escape(event.status)}</td>"
                f"<td>{escape(event.detail)}</td>"
                "</tr>"
            )
            for event in dashboard.audit_events
        )
        or '<tr><td colspan="5">No audit events recorded.</td></tr>'
    )


def _render_console_page(
    dashboard: ReportingDashboard,
    *,
    action_name: str | None = None,
    action_result: (
        WorkerControlResult | BacktestControlResult | MarketSyncControlResult | None
    ) = None,
) -> str:
    latest_price_label = dashboard.latest_price or dashboard.latest_price_status
    mode_label = "Paper" if dashboard.paper_trading else "Live"
    cards = "".join(
        [
            _render_metric_card("Execution Mode", mode_label, accent=True),
            _render_metric_card("Latest Price", latest_price_label),
            _render_metric_card("Open Positions", str(dashboard.position_count)),
            _render_metric_card("Recent Trades", str(dashboard.trade_count)),
            _render_metric_card("Realized PnL", str(dashboard.total_realized_pnl)),
            _render_metric_card("Unrealized PnL", str(dashboard.total_unrealized_pnl)),
            _render_metric_card("Database", dashboard.database_status),
            _render_metric_card("Backtest Status", dashboard.backtest.status),
        ]
    )
    action_result_section = ""
    if action_name is not None and action_result is not None:
        action_result_section = _render_action_result(action_name, action_result)

    mode_note = (
        "This console is tuned for local paper-trading workflows."
        if dashboard.paper_trading
        else "Paper mode is disabled. Actions still use current runtime configuration."
    )

    market_label = (
        f"{escape(dashboard.exchange)} {escape(dashboard.symbol)} {escape(dashboard.timeframe)}"
    )
    action_forms = "".join(
        [
            _render_action_form(
                "market-sync",
                "Sync Market Data",
                "Fetch and store recent closed candles for the configured market.",
            ),
            _render_action_form(
                "worker-cycle",
                "Run Worker Cycle",
                "Evaluate the latest candle set, apply risk checks, and execute once "
                "with current mode.",
            ),
            _render_action_form(
                "backtest",
                "Run Backtest",
                "Replay stored candles with the configured strategy and risk parameters.",
            ),
        ]
    )
    empty_result_section = (
        '<section class="panel result-panel">'
        '<div class="panel-kicker">Last Action</div>'
        "<h2>No action run yet</h2>"
        "<p>Run a bounded action from the deck to inspect immediate operator feedback.</p>"
        "</section>"
    )
    action_section = action_result_section or empty_result_section

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(dashboard.app_name)} Operator Console</title>
    <style>
      :root {{
        --ink: #0f172a;
        --muted: #475569;
        --line: rgba(15, 23, 42, 0.12);
        --panel: rgba(255, 255, 255, 0.9);
        --panel-strong: #ffffff;
        --accent: #cb5c32;
        --accent-soft: rgba(203, 92, 50, 0.14);
        --accent-dark: #7c2d12;
        --bg-top: #f4efe6;
        --bg-bottom: #d9edf4;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Avenir Next", "Segoe UI", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(203, 92, 50, 0.16), transparent 32%),
          radial-gradient(circle at top right, rgba(15, 23, 42, 0.08), transparent 26%),
          linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
      }}
      main {{
        max-width: 1280px;
        margin: 0 auto;
        padding: 28px 18px 42px;
      }}
      .hero {{
        display: grid;
        gap: 18px;
        padding: 24px;
        border: 1px solid var(--line);
        border-radius: 28px;
        background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(255,247,240,0.92));
        box-shadow: 0 18px 60px rgba(15, 23, 42, 0.09);
      }}
      .hero-top {{
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: start;
        flex-wrap: wrap;
      }}
      .eyebrow {{
        font-size: 12px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--accent-dark);
      }}
      h1 {{
        margin: 8px 0 0;
        font-size: clamp(2.2rem, 5vw, 4.6rem);
        line-height: 0.94;
      }}
      .hero-copy {{
        max-width: 760px;
        color: var(--muted);
        font-size: 1rem;
      }}
      .pill {{
        padding: 10px 14px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.72);
        font-size: 0.92rem;
      }}
      .hero-links {{
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }}
      .hero-links a {{
        text-decoration: none;
        color: var(--ink);
        border-bottom: 2px solid var(--accent);
      }}
      .section-grid {{
        display: grid;
        gap: 18px;
        margin-top: 22px;
      }}
      .controls-grid {{
        grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
      }}
      .metrics {{
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      }}
      .tables {{
        grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      }}
      .panel, .metric {{
        border: 1px solid var(--line);
        border-radius: 24px;
        background: var(--panel);
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
      }}
      .panel {{
        padding: 20px;
      }}
      .panel-kicker {{
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: var(--accent-dark);
      }}
      .panel h2 {{
        margin: 8px 0 10px;
        font-size: 1.2rem;
      }}
      .panel p {{
        margin: 0;
        color: var(--muted);
      }}
      .metric {{
        padding: 18px;
      }}
      .metric.accent {{
        background: linear-gradient(160deg, rgba(203, 92, 50, 0.14), rgba(255,255,255,0.95));
      }}
      .metric-label {{
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: var(--muted);
      }}
      .metric-value {{
        margin-top: 10px;
        font-size: 1.9rem;
      }}
      .action-list {{
        display: grid;
        gap: 12px;
        margin-top: 16px;
      }}
      .action-form {{
        display: grid;
        gap: 6px;
        padding: 14px;
        border-radius: 18px;
        border: 1px solid var(--line);
        background: var(--panel-strong);
      }}
      .action-form button {{
        justify-self: start;
        border: 0;
        border-radius: 999px;
        padding: 12px 16px;
        font: inherit;
        font-weight: 700;
        color: white;
        background: linear-gradient(135deg, #cb5c32, #8a3422);
        cursor: pointer;
      }}
      .action-form p {{
        font-size: 0.92rem;
      }}
      .result-panel {{
        background: linear-gradient(180deg, rgba(203, 92, 50, 0.08), rgba(255,255,255,0.96));
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
        vertical-align: top;
      }}
      th {{
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
      }}
      @media (max-width: 920px) {{
        .controls-grid {{
          grid-template-columns: 1fr;
        }}
      }}
      @media (max-width: 700px) {{
        main {{
          padding: 18px 12px 30px;
        }}
        .hero, .panel, .metric {{
          border-radius: 20px;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="hero-top">
          <div>
            <div class="eyebrow">Operator Console</div>
            <h1>{escape(dashboard.app_name)}</h1>
          </div>
          <div class="pill">{market_label}</div>
        </div>
        <div class="hero-copy">
          Local workflow surface for one market sync, one worker cycle, and one
          backtest against the current configuration.
          {escape(mode_note)}
        </div>
        <div class="hero-links">
          <a href="/reports">Open reporting deck</a>
          <a href="/reports/positions.csv">Positions CSV</a>
          <a href="/reports/trades.csv">Trades CSV</a>
          <a href="/status">Raw status JSON</a>
        </div>
      </section>
      <section class="section-grid controls-grid">
        <div class="panel">
          <div class="panel-kicker">Action Deck</div>
          <h2>Paper Trading Actions</h2>
          <p>
            Each action reuses the existing bounded control services and current
            runtime settings.
          </p>
          <div class="action-list">{action_forms}</div>
        </div>
        {action_section}
      </section>
      <section class="section-grid metrics">{cards}</section>
      <section class="section-grid tables">
        <div class="panel">
          <div class="panel-kicker">Portfolio</div>
          <h2>Open Positions</h2>
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
            <tbody>{_render_positions_rows(dashboard)}</tbody>
          </table>
        </div>
        <div class="panel">
          <div class="panel-kicker">Execution Feed</div>
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
            <tbody>{_render_trades_rows(dashboard)}</tbody>
          </table>
        </div>
        <div class="panel">
          <div class="panel-kicker">Review Trail</div>
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
            <tbody>{_render_audit_rows(dashboard)}</tbody>
          </table>
        </div>
      </section>
    </main>
  </body>
</html>"""


@router.get("", response_class=HTMLResponse)
def operator_console(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> HTMLResponse:
    dashboard = _build_dashboard(settings, session_factory)
    return _html_response(_render_console_page(dashboard))


@router.post("/actions/worker-cycle", response_class=HTMLResponse)
def run_console_worker_cycle(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> HTMLResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_worker_cycle(source="api.console")
    dashboard = _build_dashboard(settings, session_factory)
    return _html_response(
        _render_console_page(
            dashboard,
            action_name="Worker Cycle",
            action_result=result,
        )
    )


@router.post("/actions/market-sync", response_class=HTMLResponse)
def run_console_market_sync(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> HTMLResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_market_sync(source="api.console")
    dashboard = _build_dashboard(settings, session_factory)
    return _html_response(
        _render_console_page(
            dashboard,
            action_name="Market Sync",
            action_result=result,
        )
    )


@router.post("/actions/backtest", response_class=HTMLResponse)
def run_console_backtest(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> HTMLResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_backtest(source="api.console")
    dashboard = _build_dashboard(settings, session_factory)
    return _html_response(
        _render_console_page(
            dashboard,
            action_name="Backtest",
            action_result=result,
        )
    )
