# Decisions

## How To Use This File

Record decisions here when they materially affect architecture, trading behavior, safety controls, developer workflow, or operational handling.

Add a new entry when:

- a core technical choice is made
- a trading rule changes in a non-trivial way
- a safety control is introduced, removed, or redefined
- a workflow or repo policy changes

Do not use this file as a diary. Use it for durable decisions and their consequences.

## 2026-03-15

### Decision

Start with a single-repo monolith and paper trading only.

### Reason

This keeps the architecture small enough to be operated reliably by one developer and an AI agent while the domain model and workflow are still stabilizing.

### Consequence

Execution, API, and worker responsibilities stay in one codebase, but boundaries are enforced through modules instead of separate services.

## 2026-03-16

### Decision

Use PostgreSQL via Docker Compose as the default local development database, while keeping SQLite as a fallback.

### Reason

PostgreSQL provides a closer match to production-style persistence behavior and makes local development and repository integration testing more realistic. SQLite remains useful for simple bootstrap tasks when Docker is not needed.

### Consequence

The repository should prefer PostgreSQL-oriented persistence design, while still allowing local overrides of `DATABASE_URL` for lightweight workflows.

## 2026-03-16

### Decision

Run worker orchestration against persisted closed candles and make execution idempotent per signal candle with `client_order_id`.

### Reason

The project already has strategy, risk, and paper execution layers, so the next safe step is to wire them together without introducing repeated execution when the worker polls unchanged candle data.

### Consequence

The worker can run as a repeatable polling process over stored candles, but the same signal candle will not create duplicate paper orders once it has been executed.

## 2026-03-16

### Decision

Implement backtesting as an in-memory application service that reuses strategy and risk logic while avoiding persistence side effects.

### Reason

Backtests need to evaluate historical candles deterministically without mutating orders, trades, or positions, and they should stay close to the same decision rules used by the runtime worker.

### Consequence

The backtest runner reads persisted candles as input, but trade simulation and summary reporting happen entirely in memory.

## 2026-03-16

### Decision

Add notifications as an optional outbound integration with bounded channels (`none`, `log`, `webhook`) and keep delivery failures non-blocking but explicit in logs.

### Reason

The bot now has meaningful runtime outcomes worth surfacing outside the normal execution logs, but notification delivery should not rewrite trading state or mask the underlying execution result if an outbound channel fails.

### Consequence

Worker executions, worker risk rejections, and backtest completion or skip events can be emitted through a configurable sender, while notification failures are logged with event context instead of silently disappearing.

## 2026-03-16

### Decision

Expose operational controls as bounded API triggers for one worker cycle and one backtest, both executed strictly with the current application configuration.

### Reason

Operators need a safe way to trigger runtime workflows without shell access, but allowing arbitrary request-supplied trade parameters would bypass the normal strategy and risk boundaries and create a broader control surface than v1 needs.

### Consequence

The API can trigger worker and backtest workflows on demand, while strategy periods, market selection, paper/live mode, and risk limits remain controlled by environment configuration rather than request bodies.

## 2026-03-16

### Decision

Provide reporting exports as CSV endpoints generated from the existing operational views and backtest summary path, rather than introducing new persisted reporting tables.

### Reason

Operators and reviewers need download-friendly artifacts, but the current system already has the necessary positions, trades, and on-demand backtest summary data, so adding separate reporting persistence would widen the schema and workflow without a clear v1 need.

### Consequence

The API can export positions, recent trades, and backtest summary data in CSV form, while the source of truth remains the existing operational repositories and deterministic backtest service.

## 2026-03-17

### Decision

Do not rely on Codex review automation as a required PR merge gate.

### Reason

The repository no longer uses Codex review as part of its normal delivery workflow, so keeping dedicated trigger and status-check automation would add maintenance cost without supporting an active process.

### Consequence

PR merge readiness is now based on normal CI results and resolved review feedback without Codex-specific automation.

## 2026-03-17

### Decision

Represent recurring runtime work as explicit interval-driven job modules, and keep recurring backtest summaries disabled by default.

### Reason

The worker already had recurring behavior, but it was embedded directly in the entrypoint loop. Pulling that timing into `app/jobs` makes scheduled behavior easier to reason about and test, while leaving the optional backtest schedule off by default avoids adding surprising extra runtime cost to the normal worker path.

### Consequence

The worker cycle now runs through an explicit scheduled job path, the worker can optionally run recurring backtest summaries on a separate interval, and the default runtime remains a single worker cycle unless polling mode is enabled.

## 2026-03-17

### Decision

Add market-data sync through an exchange adapter as an opt-in worker behavior.

### Reason

The worker needed a real path to refresh candles from an exchange adapter, but making public-network fetches mandatory would make local bootstrap and isolated tests brittle.

### Consequence

The worker can now sync recent closed Binance candles before strategy evaluation when `MARKET_DATA_SYNC_ENABLED=true`, while stored-candle-only behavior remains available by default.

## 2026-03-17

### Decision

Serve reporting UI directly from the FastAPI application instead of introducing a separate frontend app.

### Reason

The system already exposes the required reporting data through application services and CSV exports, so a lightweight server-rendered dashboard adds operator usability without widening the stack or creating a second deployment path.

### Consequence

Reporting now includes an HTML dashboard at `/reports` alongside the existing CSV exports, while reporting logic continues to reuse the existing operational and backtest services.

## 2026-03-17

### Decision

Treat outbound webhook notifications as failed unless the receiver returns an HTTP `2xx`, and extend notification coverage to market-sync outcomes.

### Reason

The system now exposes a manual market-sync control and optional pre-worker sync behavior, so those outcomes need the same operator visibility as worker and backtest paths. Separately, a network request completing without raising is not enough to trust delivery if the webhook target returned a rejection status.

### Consequence

Market sync completion and failure can now emit notifications, and webhook senders log `notification_delivery_failed` for non-`2xx` responses instead of treating them as successful delivery.

## 2026-03-17

### Decision

Persist a lightweight audit feed for control outcomes and notification delivery, and expose it through the reporting surface.

### Reason

The system now has multiple operator-triggered and scheduled workflows, plus outbound notifications whose success or failure matters operationally. Runtime logs alone are not a stable operator review surface, but a full log-ingestion subsystem would be too heavy for v1.

### Consequence

The database now stores compact audit events for worker-cycle, backtest, market-sync, and notification-delivery outcomes, and operators can review recent entries through the reporting dashboard and audit CSV export.

## 2026-03-17

### Decision

Treat execution mode as an explicit configuration state and refuse live-mode execution until a dedicated live executor exists.

### Reason

The system already exposed both `PAPER_TRADING` and `LIVE_TRADING_ENABLED`, but without stricter semantics the worker could enter a misleading live-mode path and fail only when it reached the paper executor. That is too implicit for a trading safety boundary.

### Consequence

Configuration now rejects contradictory mode combinations, the status surface exposes a single derived execution mode, and the worker returns `execution_unavailable` instead of attempting unsupported live execution.

## 2026-03-17

### Decision

Resolve worker execution through a replaceable adapter boundary instead of hard-coding the paper executor inside orchestration.

### Reason

The system still only supports paper execution, but the worker now needs a stable seam where a future exchange order adapter can be introduced without rewriting orchestration, risk, or control logic.

### Consequence

Worker orchestration now builds execution through a factory, paper mode uses the current paper adapter, and the live execution path can be swapped independently without rewriting orchestration logic.

## 2026-03-17

### Decision

Add signed exchange order routing as an infrastructure client before wiring live execution into worker state updates.

### Reason

Live execution needs a real exchange-facing order path, but persisting fills and reconciling positions safely is a separate concern from signing and submitting order requests. Splitting those steps keeps the codebase moving without pretending live runtime state handling is solved.

### Consequence

The Binance integration now includes a signed live order client and factory support for validate-only or submitted order requests, establishing the infrastructure boundary needed for a dedicated live execution service.

## 2026-03-17

### Decision

Persist live order submissions locally without updating trades or positions until exchange fills are separately reconciled.

### Reason

Submitting a live order and observing a confirmed fill are different runtime events. Updating local positions on submission alone would invent state the exchange has not yet confirmed and would weaken the safety model.

### Consequence

Live execution now writes local `orders` rows with live mode and exchange order ids after successful submission, while local `trades` and `positions` remain unchanged until a later fill-reconciliation workflow is introduced.
