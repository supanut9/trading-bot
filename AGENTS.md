# AGENTS.md

## Project Objective

Operate a paper-trading-first trading platform with deterministic backtesting, operator-facing controls, reporting, deployment hardening, and guarded live-readiness groundwork.

## Use This File For

Use this file for durable repository guidance only. Put repeatable workflows in repo skills under `.agents/skills/`. Put human-facing process detail in `docs/`.

## Current Phase

- monorepo with Python backend plus Next.js operator UI
- production target remains paper trading
- live capabilities remain disabled by default until the runbook checklist is satisfied operationally
- current feature boundaries live in `docs/features.md`

## Architecture Rules

- Keep strategy logic pure and deterministic.
- Do not call exchange APIs from strategy modules.
- Separate domain, application, infrastructure, interface, and web concerns.
- Keep paper trading as the default mode.
- Keep the Next.js UI thin and route runtime actions through FastAPI application services.
- Keep execution mode derived from configuration and persisted operator controls, not ad hoc request flags.
- Treat shadow and live flows as safety-sensitive infrastructure paths, not strategy-layer concerns.
- Do not introduce microservices for v1.

## Coding Rules

- Add type hints to new Python code and keep new frontend code typed.
- Prefer small single-purpose modules.
- Keep side effects in infrastructure and application layers.
- Never hardcode secrets; use environment variables.
- Preserve structured logging and correlation identifiers for runtime, control, and notification flows.
- Keep API handlers thin; validation and orchestration belong in schemas and services.

## Safety Rules

- Live trading must remain disabled unless explicitly enabled by configuration.
- Paper trading is the required default posture.
- Shadow and live trading must never both be enabled at the same time.
- Duplicate-order protection is required before any real execution work.
- Max-loss and position-size controls must exist before live execution is considered.
- Exchange symbol rules and quantity snapping must be enforced before any real order submission.
- Qualification and live-readiness gates must not be bypassed in promotion or operator workflows.
- Failing safely is preferred over attempting recovery with uncertain exchange state.

## Validation Rules

- Add or update tests for strategy and risk changes.
- Add or update frontend tests when operator workflows or report rendering changes materially.
- Run `make format` before finishing implementation work.
- Run `make lint` before finishing implementation work.
- Run `make test` before finishing implementation work.
- Run `make pr-check` before finishing PR preparation when metadata or delivery state changed.
- For execution-related changes, include failure handling and structured logging.
- For live, shadow, worker, startup, reconciliation, and notification changes, validate the affected control and reporting path as well as the service itself.

## Documentation Rules

- Update `docs/product-spec.md` when system behavior changes.
- Update `docs/decisions.md` when architecture or workflow decisions change.
- Update `docs/runbook.md` when startup or operational procedures change.
- Update `docs/features.md` when adding, splitting, or completing a bounded feature.
- Update `docs/roadmap.md` when roadmap sequencing changes.
- Follow `docs/testing.md` when adding or changing tests.
- Add a dedicated strategy document under `docs/strategies/` before implementing a new strategy.

## Delivery Rules

- Break work down by feature first.
- Define the current feature boundary in `docs/features.md` before coding when the work is not already mapped there.
- Prefer one feature branch per bounded unit of work using `feature/<name>`.
- Keep commits small and logically grouped inside the current feature.
- Do not let unrelated runtime, schema, architecture, or UI changes hitchhike on the current feature.
- `main` receives changes through pull requests only.
- Do not merge while required checks are failing or review threads remain unresolved.

## Agent Layout

- `AGENTS.md`: durable repo constraints
- `.agents/skills/`: repo-specific reusable Codex skills
- `.codex/agents/`: optional Codex-specific custom subagent definitions
- `docs/agent-workflow.md`: human-facing explanation of how these pieces fit together

## Key Docs

- `docs/product-spec.md`
- `docs/architecture.md`
- `docs/features.md`
- `docs/roadmap.md`
- `docs/runbook.md`
- `docs/testing.md`
