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
