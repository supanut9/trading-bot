from decimal import Decimal
from html import escape
from typing import Annotated

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, sessionmaker

from app.application.services.market_data_service import MarketDataService
from app.application.services.operational_control_service import (
    BacktestControlResult,
    BacktestRunOptions,
    LiveCancelControlResult,
    LiveHaltControlResult,
    LiveReconcileControlResult,
    MarketSyncControlResult,
    OperationalControlService,
    OperatorConfigControlResult,
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


def _render_live_price_metric_card(value: str) -> str:
    return (
        '<div class="metric">'
        '<div class="metric-label">Latest Price</div>'
        f'<div class="metric-value" id="latest-price-value">{escape(value)}</div>'
        '<div class="metric-note" id="latest-price-note">Updates every 5s</div>'
        "</div>"
    )


def _render_dynamic_metric_card(
    label: str,
    value: str,
    *,
    value_id: str,
    note_id: str,
    note: str,
) -> str:
    return (
        '<div class="metric">'
        f'<div class="metric-label">{escape(label)}</div>'
        f'<div class="metric-value" id="{escape(value_id)}">{escape(value)}</div>'
        f'<div class="metric-note" id="{escape(note_id)}">{escape(note)}</div>'
        "</div>"
    )


def _render_action_form(action: str, label: str, note: str) -> str:
    return f"""
        <form method="post" action="/console/actions/{escape(action)}" class="action-form">
          <button type="submit" data-busy-label="Running...">{escape(label)}</button>
          <p>{escape(note)}</p>
        </form>
    """


def _render_navigation_card(url: str, label: str, note: str) -> str:
    return f"""
        <div class="action-form action-nav-card">
          <a href="{escape(url)}" class="nav-button">{escape(label)}</a>
          <p>{escape(note)}</p>
        </div>
    """


def _render_market_sync_form(
    settings: Settings,
    result: MarketSyncControlResult | None = None,
) -> str:
    limit = str(result.limit if result is not None else settings.market_data_sync_limit)
    backfill_checked = " checked" if result is not None and result.backfill else ""
    return f"""
        <form method="post" action="/console/actions/market-sync" class="action-form">
          <button type="submit" data-busy-label="Syncing...">Sync Market Data</button>
          <p>
            Fetch recent closed candles for the active market. Turn on backfill to load older
            candles into an existing database instead of only appending newer ones.
          </p>
          <label class="field">
            <span>Limit</span>
            <input type="text" name="limit" inputmode="numeric" value="{escape(limit)}" />
          </label>
          <label class="checkbox-field">
            <input type="checkbox" name="backfill" value="true"{backfill_checked} />
            <span>Backfill older candles</span>
          </label>
        </form>
    """


def _render_backtest_form(
    defaults: OperatorConfigControlResult,
    result: BacktestControlResult | None = None,
) -> str:
    strategy_name = result.strategy_name if result is not None else defaults.strategy_name
    symbol = result.symbol if result is not None else defaults.symbol
    timeframe = result.timeframe if result is not None else defaults.timeframe
    fast_period = str(result.fast_period if result is not None else defaults.fast_period)
    slow_period = str(result.slow_period if result is not None else defaults.slow_period)
    starting_equity = _format_money(
        result.starting_equity_input if result is not None else Decimal("100")
    )
    return f"""
        <form method="post" action="/console/actions/backtest" class="action-form">
          <button type="submit" data-busy-label="Running Backtest...">Run Backtest</button>
          <p>
            Choose market and EMA inputs, then replay stored candles with the
            current paper-risk model.
          </p>
          <label class="field">
            <span>Strategy</span>
            <select name="strategy_name">
              <option
                value="ema_crossover"
                {" selected" if strategy_name == "ema_crossover" else ""}
              >
                EMA Crossover
              </option>
            </select>
          </label>
          <label class="field">
            <span>Symbol</span>
            <input type="text" name="symbol" value="{escape(symbol)}" />
          </label>
          <label class="field">
            <span>Timeframe</span>
            <input type="text" name="timeframe" value="{escape(timeframe)}" />
          </label>
          <label class="field">
            <span>Fast Period</span>
            <input
              type="text"
              name="fast_period"
              inputmode="numeric"
              value="{escape(fast_period)}"
            />
          </label>
          <label class="field">
            <span>Slow Period</span>
            <input
              type="text"
              name="slow_period"
              inputmode="numeric"
              value="{escape(slow_period)}"
            />
          </label>
          <label class="field">
            <span>Starting Equity</span>
            <input
              type="text"
              name="starting_equity"
              inputmode="decimal"
              value="{escape(starting_equity)}"
            />
          </label>
        </form>
    """


def _render_operator_config_form(
    dashboard: ReportingDashboard,
    result: OperatorConfigControlResult | None = None,
) -> str:
    strategy_name = result.strategy_name if result is not None else dashboard.strategy_name
    symbol = result.symbol if result is not None else dashboard.symbol
    timeframe = result.timeframe if result is not None else dashboard.timeframe
    fast_period = str(result.fast_period if result is not None else dashboard.fast_period)
    slow_period = str(result.slow_period if result is not None else dashboard.slow_period)
    return f"""
        <form method="post" action="/console/actions/operator-config" class="action-form">
          <button type="submit" data-busy-label="Saving...">Save Runtime Defaults</button>
          <p>
            Update the paper-runtime market and strategy defaults used by worker cycle,
            market sync, status, and the backtest form.
          </p>
          <label class="field">
            <span>Strategy</span>
            <select name="strategy_name">
              <option
                value="ema_crossover"
                {" selected" if strategy_name == "ema_crossover" else ""}
              >
                EMA Crossover
              </option>
            </select>
          </label>
          <label class="field">
            <span>Symbol</span>
            <input type="text" name="symbol" value="{escape(symbol)}" />
          </label>
          <label class="field">
            <span>Timeframe</span>
            <input type="text" name="timeframe" value="{escape(timeframe)}" />
          </label>
          <label class="field">
            <span>Fast Period</span>
            <input
              type="text"
              name="fast_period"
              inputmode="numeric"
              value="{escape(fast_period)}"
            />
          </label>
          <label class="field">
            <span>Slow Period</span>
            <input
              type="text"
              name="slow_period"
              inputmode="numeric"
              value="{escape(slow_period)}"
            />
          </label>
        </form>
    """


def _render_live_toggle_form(action: str, label: str, note: str) -> str:
    return _render_action_form(action, label, note)


def _render_live_cancel_form() -> str:
    return """
        <form method="post" action="/console/actions/live-cancel" class="action-form">
          <button type="submit" data-busy-label="Cancelling...">Cancel Live Order</button>
          <p>Cancel one live order by exactly one identifier. Leave unrelated fields blank.</p>
          <label class="field">
            <span>Order ID</span>
            <input type="text" name="order_id" inputmode="numeric" />
          </label>
          <label class="field">
            <span>Client Order ID</span>
            <input type="text" name="client_order_id" />
          </label>
          <label class="field">
            <span>Exchange Order ID</span>
            <input type="text" name="exchange_order_id" />
          </label>
        </form>
    """


def _format_money(value: Decimal | str | None) -> str:
    if value in {None, ""}:
        return "-"
    try:
        return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")
    except Exception:
        return str(value)


def _format_amount(quantity: Decimal | None, price: Decimal | None) -> str:
    if quantity is None or price is None:
        return "-"
    return _format_money(quantity * price)


def _load_backtest_candles(
    session_factory: sessionmaker[Session],
    *,
    exchange: str,
    symbol: str,
    timeframe: str,
) -> list[object]:
    with session_factory() as session:
        return list(
            MarketDataService(session).list_historical_candles(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
            )
        )


def _render_backtest_chart(
    candles: list[object],
    result: BacktestControlResult,
) -> str:
    if not candles:
        return '<div class="chart-empty">No candles available for chart rendering.</div>'

    width = 1280
    height = 380
    closes = [Decimal(str(candle.close_price)) for candle in candles]
    minimum = min(closes)
    maximum = max(closes)
    if minimum == maximum:
        minimum -= Decimal("1")
        maximum += Decimal("1")
    span = maximum - minimum
    steps = max(len(closes) - 1, 1)

    points: list[tuple[Decimal, Decimal]] = []
    for index, close in enumerate(closes):
        x = (Decimal(index) / Decimal(steps)) * Decimal(width)
        normalized = (close - minimum) / span
        y = Decimal(height) - (normalized * Decimal(height))
        points.append((x, y))

    path_data = " ".join(
        f"{'M' if index == 0 else 'L'} {x:.2f} {y:.2f}" for index, (x, y) in enumerate(points)
    )

    markers: list[str] = []
    search_start = 0
    for execution in result.executions:
        marker_index = None
        for index in range(search_start, len(candles)):
            if Decimal(str(candles[index].close_price)) == execution.price:
                marker_index = index
                search_start = index + 1
                break
        if marker_index is None:
            marker_index = min(search_start, len(candles) - 1)
            search_start = marker_index + 1

        x, y = points[marker_index]
        marker_class = "buy-marker" if execution.action == "buy" else "sell-marker"
        markers.append(
            f'<circle class="{marker_class}" cx="{x:.2f}" cy="{y:.2f}" r="5">'
            f"<title>{escape(execution.action)} {escape(_format_money(execution.price))}"
            f" qty {escape(str(execution.quantity))}</title>"
            "</circle>"
        )

    return (
        '<section class="panel chart-panel">'
        '<div class="panel-kicker">Visualization</div>'
        "<h2>Backtest Price Chart</h2>"
        "<p>Close-price line with buy and sell markers for the current backtest run.</p>"
        f'<svg class="backtest-chart" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="backtest price chart">'
        f'<path class="chart-line" d="{path_data}"></path>'
        f"{''.join(markers)}"
        "</svg>"
        '<div class="chart-legend">'
        '<span><i class="legend-dot buy-marker"></i>Buy</span>'
        '<span><i class="legend-dot sell-marker"></i>Sell</span>'
        f"<span>Min {_format_money(minimum)}</span>"
        f"<span>Max {_format_money(maximum)}</span>"
        "</div>"
        "</section>"
    )


def _render_action_result(
    action_name: str,
    result: (
        WorkerControlResult
        | BacktestControlResult
        | MarketSyncControlResult
        | LiveReconcileControlResult
        | LiveHaltControlResult
        | LiveCancelControlResult
        | OperatorConfigControlResult
    ),
) -> str:
    status_tone = f"status-{result.status}"
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
                ("Strategy", result.strategy_name),
                ("Exchange", result.exchange),
                ("Symbol", result.symbol),
                ("Timeframe", result.timeframe),
                ("Fast Period", str(result.fast_period)),
                ("Slow Period", str(result.slow_period)),
                ("Starting Equity Input", _format_money(result.starting_equity_input)),
                ("Candle Count", str(result.candle_count)),
                ("Required Candles", str(result.required_candles)),
                ("Ending Equity", _format_money(result.ending_equity)),
                ("Realized PnL", _format_money(result.realized_pnl)),
                ("Total Trades", str(result.total_trades or 0)),
                ("Winning Trades", str(result.winning_trades or 0)),
                ("Losing Trades", str(result.losing_trades or 0)),
            ]
        )
    elif isinstance(result, MarketSyncControlResult):
        rows.extend(
            [
                ("Sync Mode", "backfill" if result.backfill else "append"),
                ("Limit", str(result.limit)),
                ("Fetched Count", str(result.fetched_count)),
                ("Stored Count", str(result.stored_count)),
                (
                    "Latest Open Time",
                    result.latest_open_time.isoformat() if result.latest_open_time else "-",
                ),
            ]
        )
    elif isinstance(result, LiveReconcileControlResult):
        rows.extend(
            [
                ("Reconciled Count", str(result.reconciled_count)),
                ("Filled Count", str(result.filled_count)),
                ("Review Required Count", str(result.review_required_count)),
            ]
        )
    elif isinstance(result, LiveHaltControlResult):
        rows.extend(
            [
                ("Live Trading Halted", "yes" if result.live_trading_halted else "no"),
                ("Changed", "yes" if result.changed else "no"),
            ]
        )
    elif isinstance(result, OperatorConfigControlResult):
        rows.extend(
            [
                ("Strategy", result.strategy_name),
                ("Exchange", result.exchange),
                ("Symbol", result.symbol),
                ("Timeframe", result.timeframe),
                ("Fast Period", str(result.fast_period)),
                ("Slow Period", str(result.slow_period)),
                ("Source", result.source),
                ("Changed", "yes" if result.changed else "no"),
            ]
        )
    else:
        rows.extend(
            [
                ("Order ID", str(result.order_id) if result.order_id is not None else "-"),
                ("Client Order ID", result.client_order_id or "-"),
                ("Exchange Order ID", result.exchange_order_id or "-"),
                ("Order Status", result.order_status or "-"),
            ]
        )

    rendered_rows = "".join(
        f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>" for label, value in rows
    )
    extra = ""
    if isinstance(result, BacktestControlResult):
        summary_cards = [
            ("Backtest Status", result.status),
            ("Candles", str(result.candle_count)),
            ("Trades", str(result.total_trades or 0)),
            ("Ending Equity", _format_money(result.ending_equity)),
        ]
        no_trade_note = ""
        if result.status == "completed" and not result.executions:
            no_trade_note = (
                '<div class="result-empty-state">'
                "<strong>No trade was triggered.</strong>"
                "<p>"
                "The backtest ran successfully, but this candle set never produced an entry or "
                "exit signal for the selected strategy parameters."
                "</p>"
                '<div class="result-empty-hint">'
                "Try a different symbol, timeframe, or faster EMA settings, or sync more candles."
                "</div>"
                "</div>"
            )
        backtest_summary = (
            '<div class="result-summary-grid">'
            + "".join(
                (
                    '<div class="result-summary-card">'
                    f"<span>{escape(label)}</span>"
                    f"<strong>{escape(value)}</strong>"
                    "</div>"
                )
                for label, value in summary_cards
            )
            + "</div>"
        )
        execution_rows = (
            "".join(
                (
                    "<tr>"
                    f"<td>{escape(execution.action)}</td>"
                    f"<td>{escape(_format_money(execution.price))}</td>"
                    f"<td>{escape(str(execution.quantity))}</td>"
                    f"<td>{escape(_format_amount(execution.quantity, execution.price))}</td>"
                    f"<td>{escape(_format_money(execution.realized_pnl))}</td>"
                    f"<td>{escape(execution.reason)}</td>"
                    "</tr>"
                )
                for execution in result.executions
            )
            or '<tr><td colspan="6">No executions recorded for this run.</td></tr>'
        )
        extra = (
            f"{backtest_summary}"
            f"{no_trade_note}"
            '<h3 class="subtable-title">Executions</h3>'
            "<table><thead><tr><th>Action</th><th>Price</th><th>Quantity</th><th>Amount</th>"
            "<th>Realized PnL</th><th>Reason</th></tr></thead>"
            f"<tbody>{execution_rows}</tbody></table>"
        )
    return f"""
      <section class="panel result-panel {status_tone}" id="action-result" tabindex="-1">
        <div class="panel-kicker">Last Action</div>
        <div class="result-header">
          <h2>{escape(action_name)}</h2>
          <div class="result-status-pill">{escape(result.status)}</div>
        </div>
        <p class="result-lead">{escape(result.detail)}</p>
        <table>
          <tbody>{rendered_rows}</tbody>
        </table>
        {extra}
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
                f"<td>{escape(_format_money(position.average_entry_price))}</td>"
                f"<td>{escape(_format_amount(position.quantity, position.average_entry_price))}"
                "</td>"
                f"<td>{escape(_format_money(position.realized_pnl))}</td>"
                f"<td>{escape(_format_money(position.unrealized_pnl))}</td>"
                "</tr>"
            )
            for position in dashboard.positions
        )
        or '<tr><td colspan="7">No positions recorded.</td></tr>'
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
                f"<td>{escape(_format_money(trade.price))}</td>"
                f"<td>{escape(_format_amount(trade.quantity, trade.price))}</td>"
                "</tr>"
            )
            for trade in dashboard.trades
        )
        or '<tr><td colspan="6">No trades recorded.</td></tr>'
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
    settings: Settings,
    dashboard: ReportingDashboard,
    *,
    action_name: str | None = None,
    action_result: (
        WorkerControlResult
        | BacktestControlResult
        | MarketSyncControlResult
        | LiveReconcileControlResult
        | LiveHaltControlResult
        | LiveCancelControlResult
        | OperatorConfigControlResult
        | None
    ) = None,
) -> str:
    latest_price_label = _format_money(dashboard.latest_price)
    if latest_price_label == "-":
        latest_price_label = dashboard.latest_price_status
    mode_label = "Paper" if dashboard.paper_trading else "Live"
    live_halt_label = "halted" if dashboard.live_trading_halted else "active"
    hero_summary = "".join(
        [
            (
                '<div class="hero-stat">'
                '<div class="hero-stat-label">Execution</div>'
                f'<div class="hero-stat-value">{escape(mode_label)}</div>'
                "</div>"
            ),
            (
                '<div class="hero-stat">'
                '<div class="hero-stat-label">Market</div>'
                f'<div class="hero-stat-value">{escape(dashboard.symbol)}</div>'
                "</div>"
            ),
            (
                '<div class="hero-stat">'
                '<div class="hero-stat-label">Latest Price</div>'
                f'<div class="hero-stat-value hero-price">{escape(latest_price_label)}</div>'
                "</div>"
            ),
            (
                '<div class="hero-stat">'
                '<div class="hero-stat-label">Live Entry</div>'
                f'<div class="hero-stat-value">{escape(live_halt_label)}</div>'
                "</div>"
            ),
        ]
    )
    cards = "".join(
        [
            _render_metric_card("Execution Mode", mode_label, accent=True),
            _render_metric_card("Strategy", dashboard.strategy_name),
            _render_metric_card("Runtime Config", dashboard.operator_config_source),
            _render_metric_card(
                "Live Entry Halt",
                "halted" if dashboard.live_trading_halted else "active",
            ),
            _render_live_price_metric_card(latest_price_label),
            _render_dynamic_metric_card(
                "Open Positions",
                str(dashboard.position_count),
                value_id="position-count-value",
                note_id="position-count-note",
                note="Live table count",
            ),
            _render_dynamic_metric_card(
                "Recent Trades",
                str(dashboard.trade_count),
                value_id="trade-count-value",
                note_id="trade-count-note",
                note="Latest 10 trades",
            ),
            _render_dynamic_metric_card(
                "Realized PnL",
                _format_money(dashboard.total_realized_pnl),
                value_id="realized-pnl-value",
                note_id="realized-pnl-note",
                note="Sum of open-position realized PnL",
            ),
            _render_dynamic_metric_card(
                "Unrealized PnL",
                _format_money(dashboard.total_unrealized_pnl),
                value_id="unrealized-pnl-value",
                note_id="unrealized-pnl-note",
                note="Sum of open-position unrealized PnL",
            ),
            _render_metric_card("Database", dashboard.database_status),
            _render_metric_card("Backtest Status", dashboard.backtest.status),
            _render_metric_card(
                "Unresolved Live Orders",
                str(dashboard.unresolved_live_orders),
            ),
            _render_metric_card(
                "Recovery Events",
                str(dashboard.recovery_event_count),
            ),
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
            _render_operator_config_form(
                dashboard,
                action_result if isinstance(action_result, OperatorConfigControlResult) else None,
            ),
            _render_live_toggle_form(
                "live-halt",
                "Halt Live Entry",
                "Block new live entries while leaving live recovery and "
                "reporting controls available.",
            ),
            _render_live_toggle_form(
                "live-resume",
                "Resume Live Entry",
                "Allow new live entries again using the current runtime configuration.",
            ),
            _render_market_sync_form(
                settings,
                action_result if isinstance(action_result, MarketSyncControlResult) else None,
            ),
            _render_action_form(
                "worker-cycle",
                "Run Worker Cycle",
                "Evaluate the latest candle set, apply risk checks, and execute once "
                "with current mode.",
            ),
            _render_navigation_card(
                "/console/backtest",
                "Open Backtest Lab",
                "Run parameterized backtests on a dedicated page with visual output.",
            ),
            _render_action_form(
                "live-reconcile",
                "Reconcile Live Orders",
                "Check recent live orders against the exchange and persist confirmed fill state.",
            ),
            _render_live_cancel_form(),
        ]
    )
    empty_result_section = (
        '<section class="panel result-panel" id="action-result" tabindex="-1">'
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
        --ink: #f7f0e8;
        --muted: #b2aca4;
        --line: rgba(247, 240, 232, 0.12);
        --panel: rgba(18, 23, 29, 0.88);
        --panel-strong: rgba(22, 28, 35, 0.96);
        --panel-soft: rgba(28, 36, 45, 0.82);
        --accent: #ff7a45;
        --accent-soft: rgba(255, 122, 69, 0.16);
        --accent-dark: #ffb18d;
        --good: #63d2a1;
        --bg-top: #120f12;
        --bg-bottom: #1b2430;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Avenir Next", "Gill Sans", "Trebuchet MS", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(255, 122, 69, 0.24), transparent 22%),
          radial-gradient(circle at top right, rgba(99, 210, 161, 0.12), transparent 18%),
          linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px),
          linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
        background-size: auto, auto, 28px 28px, 28px 28px, auto;
      }}
      main {{
        max-width: 1400px;
        margin: 0 auto;
        padding: 32px 18px 48px;
      }}
      .hero {{
        display: grid;
        gap: 24px;
        padding: 28px;
        border: 1px solid var(--line);
        border-radius: 32px;
        background:
          linear-gradient(135deg, rgba(255,122,69,0.1), transparent 28%),
          linear-gradient(180deg, rgba(19,24,31,0.98), rgba(12,16,22,0.95));
        box-shadow: 0 24px 70px rgba(0, 0, 0, 0.35);
      }}
      .hero-top {{
        display: flex;
        justify-content: space-between;
        gap: 18px;
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
        font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
        font-size: clamp(2.4rem, 5vw, 5rem);
        line-height: 0.92;
        letter-spacing: -0.03em;
      }}
      .hero-copy {{
        max-width: 760px;
        color: var(--muted);
        font-size: 1.02rem;
        line-height: 1.6;
      }}
      .pill {{
        padding: 11px 15px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.06);
        font-size: 0.92rem;
        backdrop-filter: blur(10px);
      }}
      .hero-links {{
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
      }}
      .hero-links a {{
        text-decoration: none;
        color: var(--ink);
        padding: 10px 12px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.04);
      }}
      .hero-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.7fr);
        gap: 18px;
        align-items: stretch;
      }}
      .hero-rail {{
        display: grid;
        gap: 12px;
        padding: 18px;
        border: 1px solid var(--line);
        border-radius: 24px;
        background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02));
      }}
      .hero-rail-title {{
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: var(--accent-dark);
      }}
      .hero-rail-copy {{
        color: var(--muted);
        line-height: 1.5;
      }}
      .hero-stats {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
      }}
      .hero-stat {{
        padding: 14px;
        border: 1px solid var(--line);
        border-radius: 18px;
        background: rgba(255,255,255,0.04);
      }}
      .hero-stat-label {{
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.11em;
        color: var(--muted);
      }}
      .hero-stat-value {{
        margin-top: 8px;
        font-size: 1.25rem;
        font-weight: 700;
      }}
      .hero-price {{
        color: var(--accent-dark);
      }}
      .section-grid {{
        display: grid;
        gap: 18px;
        margin-top: 24px;
      }}
      .controls-grid {{
        grid-template-columns: minmax(360px, 0.95fr) minmax(0, 1.05fr);
      }}
      .metrics {{
        grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
      }}
      .tables {{
        grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      }}
      .panel, .metric {{
        border: 1px solid var(--line);
        border-radius: 26px;
        background: var(--panel);
        box-shadow: 0 18px 36px rgba(0, 0, 0, 0.22);
      }}
      .panel {{
        padding: 22px;
      }}
      .panel-kicker {{
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: var(--accent-dark);
      }}
      .panel h2 {{
        margin: 10px 0 12px;
        font-size: 1.35rem;
        font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
      }}
      .panel p {{
        margin: 0;
        color: var(--muted);
        line-height: 1.55;
      }}
      .metric {{
        position: relative;
        overflow: hidden;
        padding: 18px;
      }}
      .metric.accent {{
        background: linear-gradient(160deg, rgba(255,122,69,0.24), rgba(24,31,39,0.98));
      }}
      .metric::after {{
        content: "";
        position: absolute;
        inset: auto 0 0 0;
        height: 3px;
        background: linear-gradient(90deg, var(--accent), transparent 75%);
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
        font-weight: 700;
      }}
      .metric-note {{
        margin-top: 8px;
        font-size: 0.8rem;
        color: var(--muted);
      }}
      .action-list {{
        display: grid;
        gap: 14px;
        margin-top: 16px;
      }}
      .action-form {{
        display: grid;
        gap: 8px;
        padding: 16px;
        border-radius: 20px;
        border: 1px solid var(--line);
        background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
      }}
      .action-form button {{
        justify-self: start;
        border: 0;
        border-radius: 999px;
        padding: 12px 18px;
        font: inherit;
        font-weight: 700;
        color: #140f0d;
        background: linear-gradient(135deg, #ff9c6e, #ff7a45);
        cursor: pointer;
      }}
      .nav-button {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: fit-content;
        border-radius: 999px;
        padding: 12px 18px;
        font-weight: 700;
        text-decoration: none;
        color: #140f0d;
        background: linear-gradient(135deg, #ff9c6e, #ff7a45);
      }}
      .action-form button[disabled] {{
        opacity: 0.72;
        cursor: wait;
      }}
      .action-form p {{
        font-size: 0.92rem;
      }}
      .field {{
        display: grid;
        gap: 6px;
      }}
      .field span {{
        font-size: 0.82rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--muted);
      }}
      .field input {{
        width: 100%;
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 10px 12px;
        font: inherit;
        color: var(--ink);
        background: rgba(255, 255, 255, 0.06);
      }}
      .field select {{
        width: 100%;
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 10px 12px;
        font: inherit;
        color: var(--ink);
        background: rgba(255, 255, 255, 0.06);
      }}
      .checkbox-field {{
        display: flex;
        gap: 10px;
        align-items: center;
        color: var(--ink);
        font-size: 0.95rem;
      }}
      .checkbox-field input {{
        width: 16px;
        height: 16px;
        accent-color: var(--accent);
      }}
      .result-panel {{
        background:
          linear-gradient(135deg, rgba(255,122,69,0.16), transparent 28%),
          linear-gradient(180deg, rgba(22,28,35,0.98), rgba(15,20,26,0.95));
      }}
      .result-panel.status-completed {{
        box-shadow: 0 18px 38px rgba(99, 210, 161, 0.18);
      }}
      .result-panel.status-skipped {{
        box-shadow: 0 18px 38px rgba(255, 196, 107, 0.16);
      }}
      .result-panel.status-failed {{
        box-shadow: 0 18px 38px rgba(255, 122, 69, 0.22);
      }}
      .result-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }}
      .result-status-pill {{
        padding: 8px 12px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.06);
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: 0.76rem;
        color: var(--accent-dark);
      }}
      .result-lead {{
        margin: 0 0 14px;
        font-size: 1rem;
        color: var(--ink);
      }}
      .result-summary-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 10px;
        margin: 0 0 16px;
      }}
      .result-summary-card {{
        padding: 12px;
        border-radius: 16px;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.04);
      }}
      .result-summary-card span {{
        display: block;
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--muted);
      }}
      .result-summary-card strong {{
        display: block;
        margin-top: 8px;
        font-size: 1.05rem;
      }}
      .result-empty-state {{
        margin: 0 0 16px;
        padding: 14px;
        border-radius: 16px;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.04);
      }}
      .result-empty-state strong {{
        display: block;
        font-size: 1rem;
      }}
      .result-empty-state p {{
        margin: 8px 0 0;
      }}
      .result-empty-hint {{
        margin-top: 10px;
        font-size: 0.88rem;
        color: var(--accent-dark);
      }}
      .subtable-title {{
        margin: 18px 0 8px;
        font-size: 1rem;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.95rem;
        overflow: hidden;
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
        background: rgba(255,255,255,0.02);
      }}
      tbody tr:hover {{
        background: rgba(255,255,255,0.03);
      }}
      .panel-shell {{
        display: grid;
        gap: 18px;
      }}
      @media (max-width: 920px) {{
        .hero-grid,
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
        .hero-stats {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="hero-grid">
          <div class="panel-shell">
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
          </div>
          <aside class="hero-rail">
            <div class="hero-rail-title">Runtime Pulse</div>
            <div class="hero-rail-copy">
              Current operator context, market selection, and live guard state at a glance.
            </div>
            <div class="hero-stats">{hero_summary}</div>
          </aside>
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
                <th>Amount</th>
                <th>Realized PnL</th>
                <th>Unrealized PnL</th>
              </tr>
            </thead>
            <tbody id="positions-table-body">{_render_positions_rows(dashboard)}</tbody>
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
                <th>Amount</th>
              </tr>
            </thead>
            <tbody id="trades-table-body">{_render_trades_rows(dashboard)}</tbody>
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
    <script>
      (() => {{
        const priceValue = document.getElementById("latest-price-value");
        const priceNote = document.getElementById("latest-price-note");
        const positionCountValue = document.getElementById("position-count-value");
        const positionCountNote = document.getElementById("position-count-note");
        const tradeCountValue = document.getElementById("trade-count-value");
        const tradeCountNote = document.getElementById("trade-count-note");
        const realizedPnlValue = document.getElementById("realized-pnl-value");
        const realizedPnlNote = document.getElementById("realized-pnl-note");
        const unrealizedPnlValue = document.getElementById("unrealized-pnl-value");
        const unrealizedPnlNote = document.getElementById("unrealized-pnl-note");
        const positionsTableBody = document.getElementById("positions-table-body");
        const tradesTableBody = document.getElementById("trades-table-body");
        const actionResult = document.getElementById("action-result");
        if (
          !priceValue ||
          !priceNote ||
          !positionCountValue ||
          !positionCountNote ||
          !tradeCountValue ||
          !tradeCountNote ||
          !realizedPnlValue ||
          !realizedPnlNote ||
          !unrealizedPnlValue ||
          !unrealizedPnlNote ||
          !positionsTableBody ||
          !tradesTableBody
        ) {{
          return;
        }}

        const formatValue = (value, fallback = "-") => {{
          if (value === null || value === undefined || value === "") {{
            return fallback;
          }}
          return String(value);
        }};

        const formatMoney = (value, fallback = "-") => {{
          if (value === null || value === undefined || value === "") {{
            return fallback;
          }}
          const numericValue = Number(value);
          if (!Number.isFinite(numericValue)) {{
            return String(value);
          }}
          return numericValue.toFixed(2);
        }};

        const formatAmount = (quantity, price) => {{
          const numericQuantity = Number(quantity);
          const numericPrice = Number(price);
          if (!Number.isFinite(numericQuantity) || !Number.isFinite(numericPrice)) {{
            return "-";
          }}
          return (numericQuantity * numericPrice).toFixed(2);
        }};

        const renderPositions = (positions) => {{
          if (!Array.isArray(positions) || positions.length === 0) {{
            positionsTableBody.innerHTML =
              '<tr><td colspan="7">No positions recorded.</td></tr>';
            return {{
              realizedPnl: "0",
              unrealizedPnl: "0",
            }};
          }}

          let realizedPnl = 0;
          let unrealizedPnl = 0;
          positionsTableBody.innerHTML = positions
            .map((position) => {{
              realizedPnl += Number(position.realized_pnl ?? 0);
              unrealizedPnl += Number(position.unrealized_pnl ?? 0);
              return (
                "<tr>" +
                `<td>${{formatValue(position.symbol)}}</td>` +
                `<td>${{formatValue(position.side)}}</td>` +
                `<td>${{formatValue(position.quantity)}}</td>` +
                `<td>${{formatMoney(position.average_entry_price)}}</td>` +
                `<td>${{formatAmount(position.quantity, position.average_entry_price)}}</td>` +
                `<td>${{formatMoney(position.realized_pnl, "0.00")}}</td>` +
                `<td>${{formatMoney(position.unrealized_pnl, "0.00")}}</td>` +
                "</tr>"
              );
            }})
            .join("");
          return {{
            realizedPnl: realizedPnl.toFixed(2),
            unrealizedPnl: unrealizedPnl.toFixed(2),
          }};
        }};

        const renderTrades = (trades) => {{
          if (!Array.isArray(trades) || trades.length === 0) {{
            tradesTableBody.innerHTML =
              '<tr><td colspan="6">No trades recorded.</td></tr>';
            return;
          }}

          tradesTableBody.innerHTML = trades
            .map(
              (trade) =>
                "<tr>" +
                `<td>${{formatValue(trade.id)}}</td>` +
                `<td>${{formatValue(trade.symbol)}}</td>` +
                `<td>${{formatValue(trade.side)}}</td>` +
                `<td>${{formatValue(trade.quantity)}}</td>` +
                `<td>${{formatMoney(trade.price)}}</td>` +
                `<td>${{formatAmount(trade.quantity, trade.price)}}</td>` +
                "</tr>"
            )
            .join("");
        }};

        const refreshSnapshot = async () => {{
          if (document.visibilityState === "hidden") {{
            return;
          }}

          try {{
            const [statusResponse, positionsResponse, tradesResponse] = await Promise.all([
              fetch("/status", {{
                headers: {{ Accept: "application/json" }},
                cache: "no-store",
              }}),
              fetch("/positions", {{
                headers: {{ Accept: "application/json" }},
                cache: "no-store",
              }}),
              fetch("/trades?limit=10", {{
                headers: {{ Accept: "application/json" }},
                cache: "no-store",
              }}),
            ]);
            if (!statusResponse.ok) {{
              throw new Error(`status ${{statusResponse.status}}`);
            }}
            if (!positionsResponse.ok) {{
              throw new Error(`positions ${{positionsResponse.status}}`);
            }}
            if (!tradesResponse.ok) {{
              throw new Error(`trades ${{tradesResponse.status}}`);
            }}

            const [payload, positions, trades] = await Promise.all([
              statusResponse.json(),
              positionsResponse.json(),
              tradesResponse.json(),
            ]);
            priceValue.textContent =
              payload.latest_price !== null && payload.latest_price !== undefined
                ? formatMoney(payload.latest_price)
                : payload.latest_price_status;
            priceNote.textContent = `Updates every 5s for ${{
              payload.symbol ?? "current symbol"
            }}`;
            positionCountValue.textContent = Array.isArray(positions)
              ? String(positions.length)
              : "0";
            positionCountNote.textContent = "Live table count";
            tradeCountValue.textContent = Array.isArray(trades) ? String(trades.length) : "0";
            tradeCountNote.textContent = "Latest 10 trades";
            const pnl = renderPositions(positions);
            renderTrades(trades);
            realizedPnlValue.textContent = pnl.realizedPnl;
            realizedPnlNote.textContent = "Sum of open-position realized PnL";
            unrealizedPnlValue.textContent = pnl.unrealizedPnl;
            unrealizedPnlNote.textContent = "Sum of open-position unrealized PnL";
          }} catch (_error) {{
            priceNote.textContent = "Price refresh unavailable";
            positionCountNote.textContent = "Position refresh unavailable";
            tradeCountNote.textContent = "Trade refresh unavailable";
            realizedPnlNote.textContent = "PnL refresh unavailable";
            unrealizedPnlNote.textContent = "PnL refresh unavailable";
          }}
        }};

        document.querySelectorAll(".action-form").forEach((form) => {{
          form.addEventListener("submit", () => {{
            const button = form.querySelector('button[type="submit"]');
            if (!(button instanceof HTMLButtonElement)) {{
              return;
            }}
            button.dataset.originalLabel = button.textContent ?? "";
            button.textContent = button.dataset.busyLabel ?? "Running...";
            button.disabled = true;
          }});
        }});

        if (actionResult && actionResult.querySelector(".result-status-pill")) {{
          window.requestAnimationFrame(() => {{
            actionResult.scrollIntoView({{ behavior: "smooth", block: "start" }});
            actionResult.focus({{ preventScroll: true }});
          }});
        }}

        window.setInterval(refreshSnapshot, 5000);
        void refreshSnapshot();
      }})();
    </script>
  </body>
</html>"""


def _render_backtest_page(
    settings: Settings,
    defaults: OperatorConfigControlResult,
    *,
    result: BacktestControlResult | None = None,
    chart_html: str = "",
) -> str:
    result_section = (
        _render_action_result("Backtest", result)
        if result is not None
        else (
            '<section class="panel result-panel" id="action-result" tabindex="-1">'
            '<div class="panel-kicker">Backtest Result</div>'
            "<h2>No run yet</h2>"
            "<p>Choose inputs and run a backtest to see summary, executions, and chart output.</p>"
            "</section>"
        )
    )
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(settings.app_name)} Backtest Lab</title>
    <style>
      :root {{
        --ink: #f7f0e8;
        --muted: #b2aca4;
        --line: rgba(247, 240, 232, 0.12);
        --panel: rgba(18, 23, 29, 0.88);
        --accent: #ff7a45;
        --accent-dark: #ffb18d;
        --good: #63d2a1;
        --bad: #ff8b8b;
        --bg-top: #120f12;
        --bg-bottom: #1b2430;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Avenir Next", "Gill Sans", "Trebuchet MS", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(255, 122, 69, 0.24), transparent 22%),
          radial-gradient(circle at top right, rgba(99, 210, 161, 0.12), transparent 18%),
          linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
      }}
      main {{
        max-width: 1320px;
        margin: 0 auto;
        padding: 30px 18px 42px;
      }}
      .hero, .panel {{
        border: 1px solid var(--line);
        border-radius: 28px;
        background: var(--panel);
        box-shadow: 0 18px 36px rgba(0, 0, 0, 0.22);
      }}
      .hero {{
        padding: 26px;
        background:
          linear-gradient(135deg, rgba(255,122,69,0.16), transparent 26%),
          linear-gradient(180deg, rgba(19,24,31,0.98), rgba(12,16,22,0.95));
      }}
      .hero-top {{
        display: flex;
        justify-content: space-between;
        gap: 14px;
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
        font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
        font-size: clamp(2.3rem, 5vw, 4.7rem);
        line-height: 0.94;
      }}
      .hero-copy {{
        max-width: 760px;
        margin-top: 14px;
        color: var(--muted);
        line-height: 1.6;
      }}
      .hero-links {{
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin-top: 18px;
      }}
      .hero-links a {{
        text-decoration: none;
        color: #140f0d;
        background: linear-gradient(135deg, #ff9c6e, #ff7a45);
        border-radius: 999px;
        padding: 10px 14px;
        font-weight: 700;
      }}
      .stack {{
        display: grid;
        gap: 18px;
        margin-top: 22px;
      }}
      .panel {{
        padding: 22px;
      }}
      .panel-kicker {{
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: var(--accent-dark);
      }}
      .panel h2 {{
        margin: 10px 0 12px;
        font-size: 1.3rem;
        font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
      }}
      .panel p {{
        margin: 0;
        color: var(--muted);
        line-height: 1.55;
      }}
      .action-form {{
        display: grid;
        gap: 8px;
        margin-top: 14px;
      }}
      .action-form button {{
        justify-self: start;
        border: 0;
        border-radius: 999px;
        padding: 12px 18px;
        font: inherit;
        font-weight: 700;
        color: #140f0d;
        background: linear-gradient(135deg, #ff9c6e, #ff7a45);
        cursor: pointer;
      }}
      .action-form button[disabled] {{
        opacity: 0.72;
        cursor: wait;
      }}
      .field {{
        display: grid;
        gap: 6px;
      }}
      .field span {{
        font-size: 0.82rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--muted);
      }}
      .field input, .field select {{
        width: 100%;
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 10px 12px;
        font: inherit;
        color: var(--ink);
        background: rgba(255, 255, 255, 0.06);
      }}
      .result-panel {{
        background:
          linear-gradient(135deg, rgba(255,122,69,0.16), transparent 28%),
          linear-gradient(180deg, rgba(22,28,35,0.98), rgba(15,20,26,0.95));
      }}
      .result-panel.status-completed {{
        box-shadow: 0 18px 38px rgba(99, 210, 161, 0.18);
      }}
      .result-panel.status-skipped {{
        box-shadow: 0 18px 38px rgba(255, 196, 107, 0.16);
      }}
      .result-panel.status-failed {{
        box-shadow: 0 18px 38px rgba(255, 122, 69, 0.22);
      }}
      .result-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }}
      .result-status-pill {{
        padding: 8px 12px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.06);
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: 0.76rem;
        color: var(--accent-dark);
      }}
      .result-lead {{
        margin: 0 0 14px;
        font-size: 1rem;
        color: var(--ink);
      }}
      .result-summary-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 10px;
        margin: 0 0 16px;
      }}
      .result-summary-card {{
        padding: 12px;
        border-radius: 16px;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.04);
      }}
      .result-summary-card span {{
        display: block;
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--muted);
      }}
      .result-summary-card strong {{
        display: block;
        margin-top: 8px;
        font-size: 1.05rem;
      }}
      .result-empty-state {{
        margin: 0 0 16px;
        padding: 14px;
        border-radius: 16px;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.04);
      }}
      .result-empty-hint {{
        margin-top: 10px;
        font-size: 0.88rem;
        color: var(--accent-dark);
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
        background: rgba(255,255,255,0.02);
      }}
      .backtest-chart {{
        display: block;
        width: 100%;
        height: auto;
        margin-top: 16px;
        border-radius: 18px;
        background: rgba(255,255,255,0.03);
        border: 1px solid var(--line);
        min-height: 380px;
      }}
      .chart-line {{
        fill: none;
        stroke: var(--accent-dark);
        stroke-width: 3;
        stroke-linecap: round;
        stroke-linejoin: round;
      }}
      .buy-marker {{
        fill: var(--good);
      }}
      .sell-marker {{
        fill: var(--bad);
      }}
      .chart-legend {{
        display: flex;
        gap: 14px;
        flex-wrap: wrap;
        margin-top: 12px;
        color: var(--muted);
        font-size: 0.9rem;
      }}
      .legend-dot {{
        display: inline-block;
        width: 10px;
        height: 10px;
        margin-right: 6px;
        border-radius: 50%;
      }}
      .chart-empty {{
        margin-top: 16px;
        padding: 14px;
        border-radius: 16px;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.04);
        color: var(--muted);
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="hero-top">
          <div>
            <div class="eyebrow">Backtest Lab</div>
            <h1>{escape(settings.app_name)}</h1>
          </div>
        </div>
        <div class="hero-copy">
          Run a focused backtest outside the main operator console, inspect the summary, and view
          the resulting trade markers on a price chart.
        </div>
        <div class="hero-links">
          <a href="/console">Back To Console</a>
          <a href="/reports">Open Reporting Deck</a>
        </div>
      </section>
      <section class="stack">
        <div class="panel">
          <div class="panel-kicker">Inputs</div>
          <h2>Run Backtest</h2>
          <p>Choose strategy and market inputs, then replay stored candles with visual output.</p>
          {_render_backtest_form(defaults, result)}
        </div>
        {chart_html}
        {result_section}
      </section>
    </main>
    <script>
      (() => {{
        document.querySelectorAll(".action-form").forEach((form) => {{
          form.addEventListener("submit", () => {{
            const button = form.querySelector('button[type="submit"]');
            if (!(button instanceof HTMLButtonElement)) {{
              return;
            }}
            button.textContent = button.dataset.busyLabel ?? "Running...";
            button.disabled = true;
          }});
        }});

        const actionResult = document.getElementById("action-result");
        if (actionResult && actionResult.querySelector(".result-status-pill")) {{
          window.requestAnimationFrame(() => {{
            actionResult.scrollIntoView({{ behavior: "smooth", block: "start" }});
            actionResult.focus({{ preventScroll: true }});
          }});
        }}
      }})();
    </script>
  </body>
</html>"""


@router.get("", response_class=HTMLResponse)
def operator_console(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> HTMLResponse:
    dashboard = _build_dashboard(settings, session_factory)
    return _html_response(_render_console_page(settings, dashboard))


@router.get("/backtest", response_class=HTMLResponse)
def operator_backtest(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> HTMLResponse:
    defaults = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).get_operator_config()
    return _html_response(_render_backtest_page(settings, defaults))


@router.post("/actions/live-halt", response_class=HTMLResponse)
def run_console_live_halt(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> HTMLResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_live_halt(
        halted=True,
        source="api.console",
    )
    dashboard = _build_dashboard(settings, session_factory)
    return _html_response(
        _render_console_page(
            settings,
            dashboard,
            action_name="Live Halt",
            action_result=result,
        )
    )


@router.post("/actions/operator-config", response_class=HTMLResponse)
def run_console_operator_config(
    strategy_name: Annotated[str, Form()] = "ema_crossover",
    symbol: Annotated[str, Form()] = "",
    timeframe: Annotated[str, Form()] = "",
    fast_period: Annotated[int, Form()] = 0,
    slow_period: Annotated[int, Form()] = 0,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> HTMLResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_update_operator_config(
        strategy_name=strategy_name,
        symbol=symbol,
        timeframe=timeframe,
        fast_period=fast_period,
        slow_period=slow_period,
        source="api.console",
    )
    dashboard = _build_dashboard(settings, session_factory)
    return _html_response(
        _render_console_page(
            settings,
            dashboard,
            action_name="Runtime Defaults",
            action_result=result,
        )
    )


@router.post("/actions/live-resume", response_class=HTMLResponse)
def run_console_live_resume(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> HTMLResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_live_halt(
        halted=False,
        source="api.console",
    )
    dashboard = _build_dashboard(settings, session_factory)
    return _html_response(
        _render_console_page(
            settings,
            dashboard,
            action_name="Live Resume",
            action_result=result,
        )
    )


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
            settings,
            dashboard,
            action_name="Worker Cycle",
            action_result=result,
        )
    )


@router.post("/actions/market-sync", response_class=HTMLResponse)
def run_console_market_sync(
    limit: Annotated[int, Form()] = 0,
    backfill: Annotated[str | None, Form()] = None,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> HTMLResponse:
    resolved_limit = limit if limit > 0 else None
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_market_sync(
        limit=resolved_limit,
        backfill=backfill == "true",
        source="api.console",
    )
    dashboard = _build_dashboard(settings, session_factory)
    return _html_response(
        _render_console_page(
            settings,
            dashboard,
            action_name="Market Sync",
            action_result=result,
        )
    )


@router.post("/backtest", response_class=HTMLResponse)
@router.post("/actions/backtest", response_class=HTMLResponse)
def run_console_backtest(
    strategy_name: Annotated[str, Form()] = "ema_crossover",
    symbol: Annotated[str, Form()] = "",
    timeframe: Annotated[str, Form()] = "",
    fast_period: Annotated[int, Form()] = 0,
    slow_period: Annotated[int, Form()] = 0,
    starting_equity: Annotated[Decimal, Form()] = Decimal("0"),
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> HTMLResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_backtest(
        options=BacktestRunOptions(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            fast_period=fast_period,
            slow_period=slow_period,
            starting_equity=starting_equity,
        ),
        source="api.console",
    )
    defaults = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).get_operator_config()
    chart_html = ""
    if result.candle_count > 0:
        chart_html = _render_backtest_chart(
            _load_backtest_candles(
                session_factory,
                exchange=result.exchange,
                symbol=result.symbol,
                timeframe=result.timeframe,
            ),
            result,
        )
    return _html_response(
        _render_backtest_page(
            settings,
            defaults,
            result=result,
            chart_html=chart_html,
        )
    )


@router.post("/actions/live-reconcile", response_class=HTMLResponse)
def run_console_live_reconcile(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> HTMLResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_live_reconcile(source="api.console")
    dashboard = _build_dashboard(settings, session_factory)
    return _html_response(
        _render_console_page(
            settings,
            dashboard,
            action_name="Live Reconcile",
            action_result=result,
        )
    )


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


@router.post("/actions/live-cancel", response_class=HTMLResponse)
def run_console_live_cancel(
    order_id: str | None = Form(default=None),
    client_order_id: str | None = Form(default=None),
    exchange_order_id: str | None = Form(default=None),
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> HTMLResponse:
    parsed_order_id = None
    normalized_order_id = _normalize_optional_text(order_id)
    if normalized_order_id is not None:
        try:
            parsed_order_id = int(normalized_order_id)
        except ValueError:
            parsed_order_id = None
            client_order_id = "__invalid_order_id__"
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_live_cancel(
        order_id=parsed_order_id,
        client_order_id=_normalize_optional_text(client_order_id),
        exchange_order_id=_normalize_optional_text(exchange_order_id),
        source="api.console",
    )
    dashboard = _build_dashboard(settings, session_factory)
    return _html_response(
        _render_console_page(
            settings,
            dashboard,
            action_name="Live Cancel",
            action_result=result,
        )
    )
