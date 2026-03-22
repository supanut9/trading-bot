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

## 2026-03-18

### Decision

Add a dedicated operator paper-trading console in the FastAPI app that reuses the existing bounded control services instead of introducing a separate UI stack or ad hoc action handlers.

### Reason

The reporting deck already covers operational visibility, but local paper-trading workflows still require manual API calls to trigger market sync, a single worker cycle, and a backtest. A small server-rendered console shortens that operator loop without widening the architecture or bypassing the current control boundaries.

### Consequence

Operators can use `/console` for one-click market sync, worker-cycle, and backtest actions with inline result feedback, while the existing `OperationalControlService` remains the single path for those actions.

## 2026-03-18

### Decision

Load operator demo market states through named local candle presets instead of ad hoc JSON examples.

### Reason

The new operator console and bounded worker controls are easier to verify when the repository can load a known no-action, buy-crossover, or sell-crossover market shape without hand-building candle payloads each time. Reusing the existing market-data persistence path keeps the feature deterministic and avoids adding a second bootstrap mechanism.

### Consequence

Operators can call a dedicated demo-scenario endpoint to load repeatable candle sets into the configured market stream, and the returned metadata states the expected EMA signal outcome for that preset.

## 2026-03-18

### Decision

Extend the operator console with live reconcile and live cancel controls instead of keeping richer live operations available only through JSON endpoints.

### Reason

The console already reduces operator friction for paper workflows, but live incident handling still required manual API calls even though the bounded service paths already existed. Reusing those same control methods in the console improves operator feedback without adding any new automatic execution behavior.

### Consequence

Operators can trigger live reconcile and live cancel actions from `/console`, and the UI shows completed, skipped, and failed outcomes using the same control results already persisted to audit events.

## 2026-03-18

### Decision

Promote a compact session summary to the top of the reporting deck using existing operational and audit data.

### Reason

Operators now have more controls and more state to inspect, but the reporting page still emphasized raw tables over scan-friendly session status. The latest worker outcome, PnL, trade count, open positions, and stale live state already exist in current services, so the right next step is to summarize them instead of introducing new summary persistence.

### Consequence

`/reports` now shows a session summary with the latest worker-cycle result and key operational counts before the detailed tables, while the underlying source of truth remains the existing operational, audit, and backtest services.

## 2026-03-18

### Decision

Expose the computed performance equity curve through the reporting deck and a CSV export, rather than keeping it limited to the JSON API response.

### Reason

The analytics core already derives equity-curve points at request time, but operators and reviewers still lacked a dashboard view and an offline artifact for the same data. Extending the existing reporting surface keeps the feature bounded and makes the curve usable without adding a charting stack or new persistence.

### Consequence

`/reports` now includes an equity-curve section grouped by mode, and `/performance/equity.csv` exports the same live-computed curve points for offline inspection.

## 2026-03-18

### Decision

Implement performance analytics as a live-computed service over existing trades, orders, and positions before introducing any dedicated summary table.

### Reason

The operator surfaces now need durable performance meaning such as win rate, expectancy, drawdown, and daily rollups, but the current schema already contains enough information to derive a first useful analytics layer. Adding a new persistence model now would widen the feature boundary before the usefulness of the metrics has been validated.

### Consequence

Performance summary, equity curve, and daily rollups are now computed from persisted trading records at request time and exposed through reporting and API surfaces, while future features can still add persisted run or snapshot models if the live-computed layer proves insufficient.

## 2026-03-19

### Decision

Introduce an in-repo Next.js operator UI instead of splitting frontend work into a separate repository.

### Reason

The project is still a single-product v1 system with one developer-facing delivery flow and a Python backend that owns all trading, execution, and safety logic. A separate UI repo would add release coordination, API contract drift risk, and extra CI and deployment overhead before frontend ownership or scale justifies that cost. Next.js provides a mature operator-dashboard stack with routing, TypeScript support, and a broad ecosystem while remaining easy to keep inside the current repository boundary.

### Consequence

Frontend work should land under a dedicated repo folder such as `web/` and consume FastAPI JSON endpoints rather than embedding business logic in the UI. The existing FastAPI server-rendered console and reporting pages remain the short-term baseline until the Next.js replacement reaches parity, after which those HTML routes can be retired deliberately.

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

## 2026-03-18

### Decision

Add a dedicated live order recovery report before introducing alerting or further operator automation.

### Reason

Once stale live orders are visible, operators still need a compact view that combines unresolved live orders with the latest reconciliation and cancel context. That review surface improves incident handling without adding new mutation paths or alert noise prematurely.

### Consequence

Reporting now includes unresolved live order recovery context in the dashboard and a dedicated `live-recovery.csv` export, giving operators a single read-only surface for recent recovery activity and unresolved live state.

## 2026-03-18

### Decision

Emit live-operations alerts from startup and scheduled job boundaries instead of from manual controls or lower-level services.

### Reason

The alerting need is operational, not user-driven. Startup sync failure, scheduled reconciliation failure, and stale-order detection are the specific unattended cases that need escalation, while manual controls should remain quiet unless an operator explicitly inspects them.

### Consequence

Notification handling now emits warning events for startup sync failure, scheduled reconciliation failure, and stale live order detection, while manual API controls remain read-only or operator-triggered without additional alert noise.

## 2026-03-18

### Decision

Treat production readiness for live-capable operation as an explicit runbook requirement, not an implicit code-complete milestone.

### Reason

The system now has bounded live controls, reconciliation, stale-order review, and alerting, but those pieces are only safe if operators know the required startup, restart, rollback, backup, and incident-response workflow. Code alone does not guarantee recoverable live operation.

### Consequence

The repository now documents a concrete readiness checklist and recovery workflow, and live-capable operation should be considered incomplete unless PostgreSQL persistence, backups, startup sync, scheduled reconciliation, and alert routing are all in place.

## 2026-03-19

### Decision

Set the current production target to deployed paper trading and document live trading as a separate non-ready boundary.

### Reason

The repository now has enough packaging, controls, reporting, smoke checks, and startup validation to support a controlled paper deployment, but the presence of live execution code paths would be easy to misread as approval for real-money use. Operators need an explicit boundary that distinguishes production paper operation from live-capable operation.

### Consequence

The runbook and product spec now describe deployed paper trading as the current production target, add a paper-production go-live checklist, and keep live trading behind a separate checklist and explicit non-readiness rule until the higher operational bar is satisfied.

## 2026-03-19

### Decision

Expose parameterized backtest inputs through the operator console and control API instead of forcing all replays to use the current runtime defaults.

### Reason

The original console made backtesting feel static because operators could only click one fixed action and then infer why a run skipped or produced no trades. The next bounded improvement was to reuse the existing service layer while allowing explicit replay inputs such as symbol, timeframe, EMA periods, and starting equity.

### Consequence

`/console` now includes a real backtest form, `/controls/backtest` accepts explicit replay options, and backtest results show the chosen inputs plus execution rows so operators can understand what actually ran without leaving the FastAPI app.

## 2026-03-18

### Decision

Package deployment runtime as one repository image with an explicit runtime role selector instead of separate per-role images.

### Reason

The API, worker, and backtest entrypoints already exist as clean Python module boundaries. A single image keeps the packaging surface smaller and makes it easier to deploy the same build artifact in different roles without duplicating dependency installation logic.

### Consequence

Deployment packaging now uses one image with `APP_RUNTIME` selecting `api`, `worker`, or `backtest`, while environment-specific configuration remains external and role-specific smoke checks can be added later without changing the image boundary.

## 2026-03-18

### Decision

Keep separate environment baselines for local development, deployed API runtime, and deployed worker runtime.

### Reason

The repository now has a shared deployable image, but API and worker roles still have different operational defaults. Reusing one local `.env` file across all roles would keep deployment setup ambiguous and make it easier to carry the wrong host binding or worker scheduling defaults into production.

### Consequence

The repository now ships role-specific deployment env examples, local development keeps its own template, and future smoke-check or deployment automation can assume clearer per-role configuration inputs.

## 2026-03-18

### Decision

Implement post-deploy verification as a bounded smoke-check script that inspects health, status, and configuration without triggering execution workflows.

### Reason

Deployment verification needs to confirm that API and worker roles are reachable and correctly configured, but using worker-cycle or reconciliation controls as a smoke check would widen the verification path into real operational mutations.

### Consequence

The repository now provides role-aware smoke checks for deployed API and worker runtimes, and the verification path stays read-only so deploy and rollback validation can happen before any manual controls or scheduled jobs are trusted.

## 2026-03-18

### Decision

Fail runtime startup early on deployment-critical misconfiguration instead of relying on later operational errors.

### Reason

The system now has deployment packaging, env baselines, and smoke checks, but those are weaker if API, worker, or backtest startup can proceed with obviously invalid runtime settings such as SQLite in production or loopback-only API binding. Those failures should surface immediately and with explicit diagnostics.

### Consequence

Runtime startup now validates configuration and database connectivity before normal API, worker, or backtest operation continues, and startup logs include a stable runtime summary for operator troubleshooting.

## 2026-03-18

### Decision

Add latest price visibility to status and reporting before building the broader operator console.

### Reason

The next UX phase needs the system to feel connected to current market context without introducing a separate UI stack or realtime streaming layer. A small read-only latest-price surface adds immediate operator value and gives the later console feature a concrete market context to build on.

### Consequence

Status and reporting now fetch the latest public exchange price when available, while strategy and execution behavior remain based on closed candles rather than realtime ticks.

## 2026-03-18

### Decision

Normalize live-order handling around a canonical local state model and treat uncertain exchange outcomes as explicit operator-review state.

### Reason

Live submission, reconciliation, stale-order detection, and cancel flows were previously reusing raw exchange status values directly. That made the operator surfaces depend on exchange-specific wording and left ambiguous cases such as unknown statuses or filled-without-details responses too easy to flatten into ordinary open-order handling.

### Consequence

Live orders now transition through a shared local state model such as `submitted`, `open`, `partially_filled`, `filled`, `canceled`, `rejected`, and `review_required`. Unknown or detail-incomplete exchange responses are surfaced as `review_required`, and recovery exports now include explicit operator-review hints instead of relying on raw status inspection alone.

## 2026-03-18

### Decision

Add explicit configuration-backed safety gates for live entry instead of relying only on the paper/live mode flag and exchange credentials.

### Reason

The runtime could already submit live orders once credentials and live mode were enabled, but operators still lacked a simple way to halt new entries or cap live order size without disabling the rest of the live-state tooling. Entry safety needed a narrower control boundary than "turn live mode off entirely."

### Consequence

Live entry now respects `LIVE_TRADING_HALTED`, `LIVE_MAX_ORDER_NOTIONAL`, and `LIVE_MAX_POSITION_QUANTITY`. These controls block new live buys while leaving reconcile, cancel, and reporting paths available, and `/status` now exposes the active live safety posture and configured limits.

## 2026-03-18

### Decision

Promote live recovery into explicit queue and timeline panels inside the reporting deck rather than leaving it as counters plus a CSV-only workflow.

### Reason

The system already tracked unresolved live orders, recovery events, `review_required`, and `next_action`, but operators still had to infer the recovery story from summary counts or export data. The safer next step was to expose the same bounded information directly in the reporting UI instead of adding more mutation paths.

### Consequence

`/reports` now shows a recovery queue for unresolved live orders and a recovery timeline for recent live reconcile or live cancel events. Operators can inspect recovery state inline before deciding whether to reconcile again, cancel, or investigate exchange state manually.

## 2026-03-18

### Decision

Tighten deploy verification around the configured live safety posture and include that same posture in unattended runtime logs.

### Reason

The repository already had startup validation and bounded smoke checks, but deploy verification still did not confirm whether the runtime was actually exposing the intended live halt and live limit settings. Operators also needed those same safety signals in background runtime logs so a restart or scheduled job could be interpreted without separately querying status.

### Consequence

Smoke checks now compare the configured live safety fields against `/status` and require startup sync readiness for live worker mode. Worker and scheduled-job logs now include `live_safety_status`, making deploy and incident review less dependent on manual cross-checking.

## 2026-03-18

### Decision

Persist operator-managed live-entry halt state in the database and expose it through bounded API and console controls.

### Reason

`LIVE_TRADING_HALTED` as a startup setting was enough for static safety posture, but it still required a restart or env change to halt new live entries during an incident. Operators needed a faster control that stayed narrow, auditable, and consistent across API status checks and worker execution.

### Consequence

The runtime now stores `live_trading_halted` in `runtime_controls` when operators change it. `POST /controls/live-halt`, the console halt and resume actions, `/status`, and worker-cycle risk evaluation all resolve the same persisted halt state first, while configuration remains the fallback when no override has been written yet.

## 2026-03-18

### Decision

Promote recovery audit payloads into operator-facing timeline context instead of showing only flat event labels.

### Reason

The reporting deck already showed a recovery timeline, but operators still had to infer what a reconcile or cancel event actually changed by reading raw audit JSON or leaving the UI. The missing value was not another control surface but a readable summary of the existing audit payloads.

### Consequence

`/reports` now shows a recovery timeline context column derived from audit payloads, and `/reports/live-recovery.csv` includes the latest recovery event context alongside the existing type and status fields. Reconcile events surface count summaries, while cancel events surface the most relevant identifiers.

## 2026-03-18

### Decision

Reject new live submissions when an unresolved same-side live order already exists for the same market.

### Reason

Paper execution already used candle-derived `client_order_id` values to avoid duplicate signals, but live submission still allowed a second same-side order to be sent while the first one remained unresolved. That weakened the live safety posture during retries, operator-triggered reruns, or overlapping worker cycles.

### Consequence

Live execution now checks for unresolved same-side live orders before submitting to the exchange. When one exists, worker and controls surfaces return `duplicate_live_order` and skip the external submission entirely, leaving reconciliation and cancel workflows to resolve the existing order first.

## 2026-03-18

### Decision

Add server-side recovery filters and search to the reporting deck and recovery export before expanding into broader runtime log tooling.

### Reason

The recovery queue and timeline had become readable, but operators still had to scan the full unresolved backlog and recent recovery activity even when they were only investigating one order or one event class. The next safe improvement was narrower read-only filtering, not more mutation paths.

### Consequence

`/reports` and `/reports/live-recovery.csv` now accept recovery filters for order status, review-required state, event type, and free-text search. The reporting deck preserves those filters in the CSV export link so operators can narrow the same incident slice in both the UI and export path.

## 2026-03-18

### Decision

Add lightweight runtime log correlation through request ids and scheduled-job run ids instead of introducing a heavier observability subsystem.

### Reason

The runtime already emitted structured-ish logs, but API incidents and scheduled worker failures still required manual guessing about which lines belonged to the same request or job run. The next useful step was correlation metadata in the existing logs, not a new storage or query surface.

### Consequence

Standard log lines now include `correlation_id`. API requests preserve `X-Request-ID` when provided or generate one when absent, and scheduled worker, backtest, live-reconcile, and startup-sync jobs each run under a generated correlation id so related log entries can be followed end to end in the existing logs.

## 2026-03-18

### Decision

Preserve the active runtime correlation id in outbound notification payloads and notification-delivery audit records.

### Reason

Runtime log correlation improved traceability inside the process, but alerts and webhook payloads still lost that link once they left the runtime boundary. Operators needed the same identifier in notifications so a failed reconcile alert or stale-order warning could be tied back to one request or one scheduled run immediately.

### Consequence

`NotificationEvent` now carries an optional top-level `correlation_id`. When notifications are emitted inside a correlated API request or scheduled job, the payload and notification-delivery audit record include that id; when they are emitted without an active runtime context, the field stays empty rather than inventing a synthetic value.

## 2026-03-18

### Decision

Promote notification-delivery audit rows into an explicit reporting slice before adding heavier delivery analytics.

### Reason

The system already stored notification-delivery audit events, but operators still had to inspect the generic audit table or raw CSV to understand whether alerts were being sent successfully. The next useful step was a read-only reporting slice over the existing audit data, not new delivery mechanics.

### Consequence

`/reports` now includes notification-delivery summary cards and a recent delivery table, and `/reports/notification-delivery.csv` exports only notification-delivery audit rows with optional filtering by status, channel, and related event type.

## 2026-03-18

### Decision

Promote notification-delivery filtering into the reporting dashboard instead of leaving filtering only on the export route.

### Reason

The dedicated notification-delivery CSV export could already be filtered, but operators still had to leave the dashboard or mentally correlate rows when narrowing delivery failures to one channel or one event type. The next safe improvement was read-only dashboard filtering that reused the same slice as the export.

### Consequence

`/reports` now accepts notification-delivery filters for status, channel, and related event type. The notification-delivery panel and its CSV export link use the same active filter slice, while the generic recent-audit table remains unchanged as a broader context view.

## 2026-03-19

### Decision

Promote filtering into the generic audit reporting slice after narrowing recovery and notification-delivery views.

### Reason

The dashboard still showed the recent audit table as an unfiltered backlog, even though recovery and notification-delivery reporting already supported narrower slices. Operators needed the same read-only narrowing for the broader audit feed so they could isolate one workflow or one failure mode without leaving the reporting deck.

### Consequence

`/reports` and `/reports/audit.csv` now accept audit filters for event type, status, source, and free-text search. The recent-audit table and audit CSV export link use the same active filter slice, while notification-delivery and recovery filters remain independent.

## 2026-03-19

### Decision

Expose explicit metadata columns in the generic audit reporting slice instead of leaving operators to infer them from raw payload JSON.

### Reason

The generic audit table already persisted market, delivery, and payload metadata, but the dashboard still reduced that slice to event, source, status, and free-form detail. Operators needed the same scan-friendly visibility that the recovery and notification slices already had, especially for correlation ids added in recent observability work.

### Consequence

The recent-audit table now shows exchange, symbol, timeframe, channel, related event type, and correlation id columns, and `/reports/audit.csv` exports `correlation_id` as a first-class field alongside the existing audit metadata.

## 2026-03-19

### Decision

Persist paper-runtime operator defaults for market and strategy selection instead of requiring those choices to live only in startup env.

### Reason

The console had become capable of running richer backtests, but the worker cycle, market sync, and status surfaces still depended on env defaults for symbol, timeframe, and EMA periods. That made the product feel static and forced operators to restart or edit env files for ordinary paper-trading adjustments.

### Consequence

The runtime now stores bounded paper defaults for strategy, symbol, timeframe, and EMA periods in the database. `/controls/operator-config` and the console runtime-defaults form update the same persisted values, and worker cycle, market sync, status, reporting, and default backtest behavior resolve those effective runtime values before falling back to env settings.

## 2026-03-19: Add Explicit Market-Data Backfill Mode

The original market-sync control only appended candles newer than the latest stored candle. That kept ordinary sync idempotent, but it also meant increasing the sync limit could not load older history into an already-populated database, which made deeper backtests awkward.

The runtime now keeps append sync as the default behavior and adds an explicit backfill mode through both `/controls/market-sync` and the operator console. Operators can choose a limit and turn on backfill when they need to upsert the full fetched window and load older missing candles without wiping the database first.

## 2026-03-19: Split Backtest Into A Dedicated Page

The operator console had accumulated too many unrelated actions in one place, and the inline backtest section still reduced replay analysis to tables. That made the main page noisy and made backtest review feel cramped.

The runtime now keeps `/console` focused on operational controls and moves replay work to `/console/backtest`. The dedicated backtest page still uses the same bounded control service, but it adds a larger result layout and an SVG chart that visualizes the backtested close-price path with buy and sell markers.

## 2026-03-19: Add A Configurable Backtest Rule Builder

The fixed EMA crossover replay path was useful as a baseline, but it was too rigid for exploratory testing and it pushed every strategy idea toward a new hardcoded Python module. Operators needed a way to combine indicator conditions, share filters across both sides, and keep buy and sell logic separate without widening the live runtime boundary at the same time.

The backtest surface now supports a bounded `rule_builder` strategy alongside the legacy EMA preset. The builder combines reusable indicator conditions into `shared_filters`, `buy_rules`, and `sell_rules`, with `all` or `any` logic per group. The first cut is backtest-only and keeps worker/runtime execution on the existing EMA path, while the control API now accepts a structured rule payload that the Next.js operator UI can evolve around.

The initial UX should stay preset-first even though the underlying rule engine is more flexible. Operators can use curated combinations first, while the bounded JSON payload keeps room for a richer Next.js backtest builder later without widening the live runtime boundary.

## 2026-03-19

### Decision

Remove the backend-rendered `/console` and HTML `/reports` pages after landing the new Next.js operator UI foundation.

### Reason

Keeping both UI stacks in service would duplicate operator workflows, prolong outdated UX, and create confusion about which surface is the real product path. The FastAPI backend should now expose APIs and CSV/report exports only, while the browser UI lives in the in-repo Next.js application.

### Consequence

`/console` and `GET /reports` no longer exist on the backend. FastAPI keeps the bounded JSON control endpoints, status and operations APIs, and `/reports/*.csv` export routes that the Next.js UI can consume or link to directly.

## 2026-03-19: Let Market Sync Accept Explicit Market Selection

The original `POST /controls/market-sync` endpoint only accepted `limit` and `backfill`, which forced any UI to rely on persisted operator defaults for `symbol` and `timeframe`. That was too implicit for the Next.js controls workflow because operators need to target a market window for one sync run without assuming they changed global runtime state.

The market-sync control now accepts optional `symbol` and `timeframe` fields. When omitted, the service still resolves the effective operator defaults, but when supplied it runs the sync against those explicit values for that request only. The new Next.js controls page uses that contract so the operator can choose market, timeframe, candle limit, and append or backfill mode directly.

## 2026-03-20: Move Reporting Back Into The Next.js Operator UI

Once the backend-rendered `/reports` page was removed, operators still had CSV exports and the JSON analytics API, but no richer browser reporting surface. The replacement should stay bounded: reuse the existing performance and export endpoints instead of inventing a second reporting backend.

The new Next.js `/reports` route now reads `GET /status` and `GET /performance/summary`, renders summary metrics and the equity curve in the operator shell, and links directly to the existing CSV exports. Reporting remains API-backed and read-only, while recovery-heavy reporting slices can continue to land as separate features.

## 2026-03-20: Add A Dedicated Next.js Backtest Page

The control API already supported parameterized backtests and the product spec called for a dedicated replay surface, but the new operator UI still lacked a browser route for that workflow. Keeping replay analysis out of the controls page also preserves cleaner feature boundaries between candle intake, worker actions, and historical experimentation.

The operator UI now includes a dedicated `/backtest` route that posts to the existing `POST /controls/backtest` endpoint, hydrates its default market inputs from persisted operator config, and stays preset-first for rule-builder experiments. The page renders backtest outcome metrics, a simple realized-equity curve, and execution detail without introducing a second analytics backend.

## 2026-03-20: Expose Live Recovery Controls In The Next.js UI

The backend already provided bounded live halt, reconcile, and cancel APIs, but operators still had to leave the main UI surface to use them. That gap was operational rather than architectural, so the correct next step was to expose the existing controls in the Next.js app without moving any live policy into frontend code.

The controls route now reads `/status` for the current live posture and adds explicit UI actions for halt or resume, reconcile, and manual cancel. The browser sends only one cancel identifier at a time, while live safety checks, duplicate-order protection, and failure handling remain in the Python backend.

## 2026-03-20: Add Recovery Reporting To The Next.js Reports Route

Recovery exports and backend services already existed, but the reporting route still treated recovery as a future slice and left operators with CSVs for unresolved live-order review. The missing capability was a read-only browser surface for the same bounded recovery data, not more execution logic.

The API now exposes `GET /reports/recovery` as a JSON dashboard slice over the existing reporting and recovery services. The Next.js `/reports` route uses that endpoint to render stale live orders, the unresolved recovery queue, recent reconcile or cancel events, and read-only recovery filters while preserving filtered `live-recovery.csv` exports.

## 2026-03-20: Add Notification Delivery Reporting To The Next.js Reports Route

Notification-delivery audits and filtered CSV exports already existed, but the reporting route still lacked the explicit delivery panel described in the docs. Operators needed the same bounded read-only slice in-browser so delivery failures could be narrowed without leaving the reporting surface.

The API now exposes `GET /reports/notifications` as a JSON dashboard slice over the existing notification-delivery audit data. The Next.js `/reports` route uses that endpoint to render delivery summary cards, recent notification-delivery rows, read-only filters for status, channel, and related event type, and a filtered `notification-delivery.csv` export link.

## 2026-03-20: Add Generic Audit Reporting To The Next.js Reports Route

The reporting route already exposed narrower recovery and notification slices, but the broader audit feed still depended on a CSV export for real filtering. Operators needed the same read-only narrowing in-browser so one workflow or one failure mode could be isolated without leaving the reporting surface.

The API now exposes `GET /reports/audit` as a JSON dashboard slice over the existing recent-audit data. The Next.js `/reports` route uses that endpoint to render audit summary cards, a generic audit filter form, richer audit metadata columns, and a filtered `audit.csv` export link while keeping the slice read-only.

## 2026-03-20: Persist Summary-Level Backtest Run History

The dedicated backtest page now supports richer rule-builder editing, but replay results are still one-off unless the operator captures them manually. A lightweight run-history table gives the UI and exports a stable review surface without widening into full execution-ledger persistence.

Backtest control runs now persist one summary row per replay attempt with the submitted market inputs, summary metrics, and serialized rule-builder payload when present. The API exposes recent-run JSON and CSV reporting, and the Next.js backtest page can hydrate its form from a stored run while keeping replay history separate from audit and execution tables.

## 2026-03-20: Keep Replay Readiness As A Read-Only Market-Data Surface

Operators now have multiple replay inputs and a growing market-sync workflow, but readiness still depends on the same stored candle set rather than a second planning artifact. The missing capability was visibility into stored range, replay minimum, and freshness before running a backtest, not automatic repair or another mutation path.

Replay readiness now lives behind a read-only `GET /market-data/coverage` endpoint that reuses the backend backtest-shape rules to calculate `required_candles`. The Next.js `/backtest` and `/controls` routes consume that endpoint to show candle count, stored range, freshness, and gap-to-ready guidance while keeping all write behavior in the existing sync and backtest controls.

## 2026-03-20: Define Project Completion As Controlled Live Trading, Not Guaranteed Alpha

The repository has now reached the end of the research-first queue, so the next planning step is to define what "done" means before more implementation branches start. For a trading bot, pretending the project is complete only when it can "make money" would be dishonest because profitability depends on market regime, fees, slippage, and ongoing operator judgment rather than code alone.

Project completion is now defined as controlled real-money trading for one approved strategy and one symbol with explicit promotion gates, hard risk controls, exchange-rule enforcement, trustworthy reconciliation, and fail-closed incident handling.

## 2026-03-20: Front-Load Strategy Quality Before Live Deployment Work

The original planned feature queue sequenced safety gates and live deployment infrastructure first, then backtest validation and shadow testing. This ordering is backwards: safely deploying a strategy with inflated backtest metrics, no out-of-sample testing, and market-order fills will still lose money regardless of how robust the deployment is.

The feature plan is revised to front-load three strategy quality features before any live-readiness work begins:

- realistic backtest cost modeling (slippage and fees) so PnL expectations are not inflated
- walk-forward validation so any strategy promoted to live has demonstrated positive expectancy on data it was not optimized against
- signal quality improvements (RSI and volume filters) to reduce false entries that erode edge through repeated fees and small losses

A smart order execution feature is added to the live infrastructure phase to minimize fill costs through limit orders and track actual slippage versus modeled assumptions.

Qualification gates are revised to require cost-adjusted out-of-sample evidence and shadow-versus-backtest drift within bounds rather than in-sample backtest metrics alone.

A strategy iteration workflow closes the feedback loop when live performance falls below walk-forward expectations, defining how the strategy is re-validated and re-promoted rather than left running on a degrading edge.

## 2026-03-22

### Decision

Introduce an explicit live-readiness report and require it to pass before live resume is allowed.

### Reason

Live-capable controls already existed, but operators still had to infer readiness from scattered status fields and manual runbook checks. That is not reliable enough for exchange-facing execution. A single readiness report and a fail-closed resume path reduce the chance of resuming live entry while prerequisites are missing.

### Consequence

The API now exposes `GET /controls/live-readiness`, `/status` includes `live_readiness_status` and `live_readiness_blocking_reasons`, and `POST /controls/live-halt` refuses live resume when readiness is blocked. The initial checks cover live enablement, runtime halt state, exchange credentials, symbol-rule availability, qualification, startup-sync and reconcile scheduling, unresolved review-required or stale live orders, and configured live sizing caps.

## 2026-03-22

### Decision

Add portfolio-level live entry caps to the existing risk evaluation path instead of creating a second portfolio-governor runtime.

### Reason

The worker already computes aggregate portfolio exposure before calling `RiskService`, so the clean extension point is to add portfolio cap fields there. That keeps live entry rejection in one place, preserves existing auto-halt behavior for hard violations, and avoids splitting trade approval between multiple overlapping services.

### Consequence

Live entry can now be blocked on total exposure, per-symbol exposure, per-symbol concentration, and live concurrent-position limits. These caps are surfaced through `/status` so operators can inspect the configured portfolio envelope before enabling live mode, and hard violations continue to fail closed by auto-halting live execution.

## 2026-03-21

### Decision

Add a `live_order_validate_only` setting and support dry-run live order submission through the exchange's test endpoint.

### Reason

Operators need a way to verify that live order signing, parameters, and exchange connectivity are working correctly without actually committing real-money trades. The Binance `/api/v3/order/test` endpoint provides this validation without creating an order ID or executing a fill.

### Consequence

The `LiveExecutionService` now honors the `live_order_validate_only` setting. When enabled, live orders are submitted to the test endpoint, and their status is immediately transitioned to `canceled` (terminal) in the local database to avoid unnecessary reconciliation attempts for orders that do not exist on the exchange.

## 2026-03-20

### Decision

- Persisted `trading_mode` in the operator configuration database and UI.
- Unified backtesting and runtime configuration by incorporating `trading_mode` into `BacktestService`, allowing accurate simulation of both spot and futures environments.

### Reason

The system already supported `trading_mode` as a startup environment variable, but as the operator UI becomes the primary surface for managing runtime defaults (symbol, timeframe, periods), the trading mode also needs to be durable and modifiable without a process restart. This allows operators to switch between spot and futures paper trading seamlessly.

### Consequence

The `OperatorConfigRecord` now includes a `trading_mode` column, and the `OperatorRuntimeConfigService` resolves the effective mode from persisted records before falling back to application settings. The operator UI in `web/components/runtime-page.tsx` now includes a selection for this mode, and all related API schemas and test suites have been updated to support it.

## 2026-03-21

### Decision

Reset the daily loss accumulator per calendar day in the backtest simulation.

### Reason

The backtest was tracking cumulative lifetime losses as the "today" loss figure. After a few losing trades pushed the running total past `max_daily_loss_pct`, the daily loss gate permanently locked out all future entries for the rest of the simulation, making backtests appear to stop trading after the first bad day.

### Consequence

The backtest now resets `daily_loss_today` to zero whenever `candle.open_time.date()` changes, matching the intended per-day risk semantics. Historical backtests that appeared to stop early will now run to completion.

## 2026-03-21

### Decision

Change `DEFAULT_TIMEFRAME` from `4h` to `1h` based on backtest evidence.

### Reason

A full 45-combination batch backtest (5 strategies × 9 timeframes) showed `ema_crossover/1h` returning +11.5% while `ema_crossover/4h` returned −10.9% over the same BTC/USDT window. The 1h timeframe produced more trades, better drawdown, and a positive return across the same period.

### Consequence

The default runtime, backtest, and coverage-readiness check all now operate at 1h unless overridden by operator config or request payload.

## 2026-03-21

### Decision

Implement multi-timeframe confirmation as a fail-open domain filter with look-ahead bias protection in backtest.

### Reason

An HTF filter that errors or blocks when candle history is insufficient would make early backtest windows and live bootstrap fail. Fail-open (pass the signal when HTF data is absent) matches the design of the existing ADX and RSI filters and avoids silent data gaps blocking trades that should be allowed.

### Consequence

`is_htf_trend_aligned()` returns `True` when fewer than `period` HTF candles are available. In the backtest engine, only HTF candles with `open_time <= candle.open_time` are passed to the filter, preventing any future HTF data from influencing historical entry decisions.
