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

## 2026-03-17

### Decision

Reconcile live exchange fills into local trades and positions only through an explicit order-status reconciliation step.

### Reason

Live order submission and confirmed exchange fills are separate events, and the system needs a bounded way to pull authoritative fill state back into local runtime records without inventing trades from submission alone. A dedicated reconciliation step also keeps retry and idempotency behavior isolated from the initial execution path.

### Consequence

The exchange adapter now supports signed order-status lookup, recent open live orders can be reconciled through a dedicated service and control endpoint, and local trades or position updates are created only when the exchange reports a confirmed filled status with usable fill details.

## 2026-03-17

### Decision

Expose exchange balance visibility through the existing status surface instead of adding a separate balance control workflow first.

### Reason

The immediate operator need after live submission and fill reconciliation is to confirm that the configured live symbol is funded. That is read-only exchange state, so it fits the existing status surface better than a new mutation-oriented control path.

### Consequence

The authenticated exchange client now supports account-balance lookup, and `/status` reports base and quote asset balances for the configured symbol when live mode is enabled while leaving execution behavior unchanged.

## 2026-03-17

### Decision

Schedule live fill reconciliation as a worker job by reusing the existing control workflow instead of introducing a separate scheduler-only implementation path.

### Reason

The manual live reconciliation path already owns the exchange lookup, local state updates, and audit behavior. Reusing it for recurring execution keeps manual and scheduled reconciliation semantics aligned and reduces the risk of two diverging implementations.

### Consequence

Worker scheduling can now run recurring live reconciliation in live mode through explicit config flags, and reconciliation failures are converted into auditable failed control results instead of escaping as uncategorized scheduler exceptions.

## 2026-03-17

### Decision

Run a one-time startup live state sync before new live worker execution and abort startup when that sync fails.

### Reason

After a restart or deploy, the local database may lag the exchange state for recently submitted or filled live orders. Starting a new live worker cycle without reconciling that state first would weaken duplicate-order protection and position safety.

### Consequence

Live worker startup now runs the existing reconciliation workflow once before any new execution is attempted, and a failed startup sync causes the worker to stop instead of continuing with uncertain live state.

## 2026-03-17

### Decision

Expose live order cancellation as a bounded manual control instead of adding automatic cancel behavior.

### Reason

Order cancellation affects exchange-side state directly and can conflict with fills or partial fills in flight. Keeping it manual and explicit gives operators a recovery tool without introducing implicit cancel heuristics that might race live exchange activity.

### Consequence

The live order client now supports authenticated cancel requests, the controls API can cancel a live order by one explicit identifier, and local order state changes to canceled only after a confirmed exchange cancel response.

## 2026-03-17

### Decision

Detect stale live orders locally from persisted order age and surface them as read-only operator visibility before adding more recovery automation.

### Reason

The next unresolved live-ops risk is orders that remain open long enough to warrant operator review but not automatic action. Exposing those orders first gives operators visibility without introducing heuristics that could race exchange state changes.

### Consequence

The reporting surface now classifies stale live orders by a configured age threshold, shows them separately from ordinary trade history, and keeps stale-order handling read-only until later recovery features are added.
