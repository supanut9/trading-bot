# Architecture

## Target Shape

The system is a single repository and single product with separate API, worker, and operator UI entrypoints.

## Guiding Principles

- Keep trading decisions deterministic and testable.
- Keep side effects isolated from strategy and risk logic.
- Prefer explicit module boundaries over implicit conventions.
- Fail safely when runtime state is uncertain.

## Layers

- `app/domain`: pure trading logic such as strategy, risk, and portfolio rules
- `app/application`: orchestration services and use cases
- `app/infrastructure`: database, exchange, and notification integrations
- `app/interfaces`: HTTP routes and external-facing adapters
- `app/jobs`: scheduled workflows for market sync and strategy execution
- `web`: Next.js operator UI that consumes bounded FastAPI APIs

## Dependency Direction

Dependencies must point inward toward more stable logic:

- `interfaces` may depend on `application` and shared config objects
- `jobs` may depend on `application` and shared config objects
- `application` may depend on `domain` and infrastructure abstractions
- `infrastructure` may depend on `domain` models or contracts when needed
- `web` may depend on HTTP APIs and local UI helpers, but not on Python runtime internals
- `domain` must not depend on `application`, `interfaces`, or `infrastructure`

Practical rule:

- `domain` never imports from `app.infrastructure`
- API routes do not call exchange clients directly
- strategy modules do not touch the database
- exchange-specific types should not leak into domain strategy code
- UI code does not own trading rules, exchange calls, or risk-policy decisions

## Layer Responsibilities

### Domain

The domain layer owns business rules.

Allowed:

- signal generation
- indicator interpretation
- portfolio and risk rules
- pure value objects and domain entities

Not allowed:

- HTTP requests
- database sessions
- logging side effects unless abstracted away
- environment/config access

### Application

The application layer coordinates workflows.

Allowed:

- calling strategies with prepared data
- invoking risk checks before execution
- mapping domain outcomes into execution requests
- transaction boundaries and orchestration
- coordinating repositories through application-facing services such as market data ingestion

Not allowed:

- embedding exchange-specific business logic that belongs in adapters
- placing trading rules directly in route handlers or scheduled jobs

### Infrastructure

The infrastructure layer owns external integrations.

Allowed:

- exchange clients
- persistence implementations
- notification senders
- serialization details for third-party systems

Not allowed:

- owning the core trading decision rules
- bypassing application services to mutate portfolio state ad hoc

### Interfaces

The interface layer exposes the system to external callers.

Allowed:

- HTTP routing
- schema validation
- translating request and response models

Not allowed:

- business logic in route handlers
- direct database orchestration
- direct exchange access

### Web UI

The web layer owns operator-facing presentation and client-side workflow.

Allowed:

- route composition for dashboards, reports, and control screens
- calling bounded FastAPI JSON endpoints
- charting, filtering, and UI state management
- server-side or client-side rendering for presentation needs

Not allowed:

- strategy evaluation logic
- risk-policy decisions
- direct database access
- direct exchange API access
- duplicating application rules already owned by Python services

### Jobs

Jobs trigger workflows on a schedule.

Allowed:

- selecting when a use case runs
- loading runtime configuration needed to start a workflow

Not allowed:

- embedding strategy logic
- bypassing application services

## Module-Level Rules

- One module should have one primary responsibility.
- Strategy implementations return signals or domain decisions, not broker-specific order payloads.
- Risk modules validate whether an action is permitted; they do not send orders.
- Execution modules translate approved actions into exchange or paper-execution requests.
- Repositories and exchange adapters must be replaceable without changing domain code.
- Config access should be centralized and passed downward, not fetched ad hoc in many modules.

## API And Worker Boundaries

- `app/main.py` assembles HTTP routes and shared dependencies.
- `app/worker.py` assembles the runtime loop or scheduler.
- Both entrypoints may build application services.
- Neither entrypoint should contain trading rules.

## Runtime Flow Boundaries

This is the required order of responsibility:

1. Market data is loaded from an external source or repository.
2. Application services prepare domain-friendly inputs.
3. Strategy evaluates the inputs and emits a signal or no-op.
4. Risk policies approve or reject the signal.
5. Execution service converts approved intent into a paper or live order action.
6. Persistence records the decision, order attempt, and resulting state.
7. Notifications report outcomes when configured.

## Runtime Flow

1. Worker fetches market data.
2. Strategy evaluates candles and produces a signal.
3. Risk checks validate whether execution is allowed.
4. Execution service simulates or submits an order based on mode.
5. Results are stored and logged.
6. Notifications are emitted when configured.

## Core Entry Points

- `app/main.py`: FastAPI application
- `app/worker.py`: background worker loop
- `web/`: Next.js operator UI

## Data And Model Rules

- Domain models should represent trading concepts, not database rows.
- Persistence models may mirror storage concerns, but conversion into domain-friendly objects should happen before strategy evaluation.
- Request and response schemas belong at the interface boundary, not in the domain layer.
- Prefer explicit objects over loose dictionaries once the bootstrap phase ends.

## Async And IO Rules

- Use async only where it improves external IO handling.
- Do not introduce async into pure strategy and risk code.
- Keep blocking or network-heavy logic in infrastructure or application layers.
- Worker scheduling may be sync at first; convert to async only when needed by actual IO patterns.

## Error Handling Rules

- Invalid external data should be rejected before domain evaluation.
- When execution state is uncertain, prefer stopping the workflow and logging the failure.
- Do not silently swallow exchange, persistence, or notification failures.
- Surface enough context in logs to reconstruct what the bot attempted to do.

## Logging Rules

Two logging streams are required:

- decision logging in repository documentation
- runtime logging in application code

### Decision Logging

Decision logging lives in `docs/decisions.md`.

Use it for:

- architecture choices
- data model changes
- execution and safety behavior changes
- workflow or developer policy changes

Do not log trivial refactors or ordinary implementation progress there.

### Runtime Logging

Runtime logging must make bot behavior reconstructable.

At minimum, log:

- worker start and stop
- configuration mode relevant to safety, such as paper or live mode
- market data fetch attempts and failures
- signal generation results
- risk approval or rejection
- order submission attempts
- execution results
- position state changes
- unexpected exceptions

Runtime logs should:

- be structured and machine-readable once the logging module is introduced
- avoid leaking secrets
- include enough identifiers to correlate a strategy decision with an order attempt
- prefer explicit failure logs over silent retries

## Data Stores

- PostgreSQL via Docker Compose for normal local development
- SQLite as a fallback for simple bootstrap workflows
- structured logs to stdout

## Persistence Layout

- SQLAlchemy setup belongs in `app/infrastructure/database`
- persistence models belong in `app/infrastructure/database/models`
- repository implementations belong in `app/infrastructure/database/repositories`
- schema overview and durable table intent belong in `docs/data-model.md`

## Logging Layout

- logger setup belongs in `app/core/logger.py`
- application and worker code should use shared logger configuration
- logging should describe runtime events, not replace persistence or decision records

## Safety Defaults

- paper trading enabled
- live trading disabled
- no exchange credentials required for local bootstrap

## UI Boundary Rules

- Treat FastAPI as the source of truth for trading state and control outcomes.
- Prefer JSON endpoints for new UI work instead of expanding server-rendered HTML.
- Keep UI-specific aggregation thin; reusable business logic belongs in Python services.
- Migrate `/console` and `/reports` by feature slice, not by a one-shot rewrite.
